import json
import logging
from typing import Any, Dict, List, Optional, Union

from openai import AsyncOpenAI

from shared.config import settings
from shared.generation.reranker import BaseReranker, RerankerFactory

logger = logging.getLogger(__name__)


# --- OpenAI Client Factory ---
def get_openai_client() -> AsyncOpenAI:
    """
    Initializes and returns an async OpenAI client.
    """
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        return client
    except Exception as e:
        logger.error(f"An error occurred while initializing the OpenAI client: {e}")
        raise


# --- Component 1: Conversational Query Rewriter ---
class ConversationalQueryRewriter:
    """
    Uses an LLM to rewrite a user's latest query into a single, optimal, self-contained
    search query based on the conversation history.
    """

    def __init__(self):
        self.system_prompt = """
        You are expert at rewriting questions. You are given a conversation between a human and an assistant and a follow-up query from human, you have to rewrite the message to a standalone question that captures all relevant context from the conversation.

        Your task is to convert a user's latest query into a single, standalone search query using the provided conversation history.

        **Rules:**
        1. **Self-Contained:** Resolve all pronouns (e.g., 'it', 'they') and context from the history. The query must be understandable on its own.
        2. **Optimized:** Enhance the query with specific keywords and details from the chat for better retrieval.
        3. **Format:** Respond ONLY with a JSON object: `{"search_query": "your_generated_query"}`. No other text or explanation.
        5.  **Crucial**: Do not answer the question. Only provide the single, optimized search query.
        """

    async def rewrite_query(self, latest_query: str, chat_history: List[Dict[str, str]]) -> str:
        """
        Takes the latest user query and the chat history, returns a single rewritten query string.
        """
        logger.info(f"\n[1] Rewriting query: '{latest_query}' (using chat history)")
        user_prompt = """
        # Task
        You are a query rewriting assistant for retrieval tasks.
        Given the following conversation history between 'user' and 'assitant' alongwith the most recent latest user query,
        rewrite the latest query so it is a fully standalone, context-rich question
        that can be used to search a knowledge base.
        Respond ONLY with a JSON object: `{"search_query": "rewritten_standalone_query"}` without explanation
        """
        formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])

        user_message_content = f'{user_prompt} \n # Chat History:\n---\n{formatted_history}\n---\n# Input Latest User Query: "{latest_query}"'
        # user_message_content += '\nRespond ONLY with a JSON object: `{"search_query": "rewite_generated_query"}`'

        try:
            client = get_openai_client()
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            result = json.loads(response.choices[0].message.content)
            rewritten_query = result.get("search_query", latest_query)
            logger.info(f" 🔄 -> Rewritten into: '{rewritten_query}'")
            return rewritten_query
        except Exception as e:
            logger.error(f"  -> Error during query rewriting: {e}")
            return latest_query


# --- Component 2: Information Extractor ---
class InformationExtractor:
    def __init__(self):
        self.system_prompt = """
        You are an expert information extraction AI...
        (same as before)
        """

    async def extract(self, original_query: str, retrieved_docs: List[str]) -> str:
        logger.info("\n[3] Extracting and formatting information from retrieved documents...")

        if not retrieved_docs:
            logger.info(" -> No documents to process.")
            return ""

        context_str = "\n\n---\n\n".join(retrieved_docs)
        user_message = f'Original User Question: "{original_query}"\n\nRetrieved Context:\n---\n{context_str}\n---'

        try:
            client = get_openai_client()
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
            )
            formatted_context = response.choices[0].message.content
            logger.info(" -> Extraction and formatting complete.")
            return formatted_context
        except Exception as e:
            logger.error(f"  -> Error during information extraction: {e}")
            return context_str


# --- The Main Async Pipeline ---
class ContextPipeline:
    def __init__(
        self,
        retriever: Any,
        only_retrival: bool = True,
        use_reranker: bool = False,
        reranker_provider: str = "voyageai",
        reranker: Optional[BaseReranker] = None,
    ):
        self.retriever = retriever
        self.chat_history: List[Dict[str, str]] = []
        self.only_retrival = only_retrival
        self.use_reranker = use_reranker

        self.rewriter = ConversationalQueryRewriter()
        self.extractor = InformationExtractor()

        # Initialize reranker if enabled
        if self.use_reranker:
            self.reranker = reranker or RerankerFactory.create(reranker_provider)
            logger.info(f"📊 Reranker enabled: {reranker_provider}")
        else:
            self.reranker = None
            logger.info("📊 Reranker disabled")

    async def process(
        self,
        user_query: str,
        persona_id: str,
        chat_history: List[Dict[str, str]],
        top_k: int = 5,
        similarity_threshold: float = 0.45,
        return_citations: bool = False,
    ) -> Union[str, Dict[str, Any]]:
        # Step 1: Rewrite query (DISABLED FOR PERFORMANCE)
        # rewritten_query = await self.rewriter.rewrite_query(user_query, chat_history)

        # Step 2: Determine retrieval count based on reranker usage
        # If reranker is enabled, fetch 4x more documents for better reranking
        retrieval_top_k = top_k * 4 if self.use_reranker and self.reranker else top_k

        # Step 3: Retrieve documents
        logger.info(
            f"\n[2] Retrieving documents with query: '{user_query}' "
            f"(fetching {retrieval_top_k}, target: {top_k})"
        )
        retrieved_docs = await self.retriever.retrieve_context(
            persona_id=persona_id,
            query=user_query,
            top_k=retrieval_top_k,
            similarity_threshold=similarity_threshold,
            include_patterns=True,
        )

        # Step 4: Rerank documents if enabled
        chunks = []
        if retrieved_docs and retrieved_docs.get("chunks"):
            chunks = retrieved_docs["chunks"]

            if self.use_reranker and self.reranker and chunks:
                logger.info(f"🎯 Reranking {len(chunks)} documents to select top {top_k}")
                chunks = await self.reranker.rerank(
                    query=user_query,
                    documents=chunks,
                    top_k=top_k,
                )
                logger.info(f"✅ Selected {len(chunks)} documents after reranking")

        # Step 5: Format documents
        docs = []
        if chunks:
            docs = [f"[Source: {chunk['source']}\nContent: {chunk['content']}]" for chunk in chunks]

        unique_docs = list(set(docs))
        logger.info(f" -> Retrieved {len(unique_docs)} unique documents.")

        # Step 6: Generate citation sources if requested
        citation_sources = []
        if return_citations:
            if chunks:
                for chunk in chunks:
                    # Extract URL from metadata (following LlamaRAG pattern)
                    # post_url: LinkedIn posts, tweet_url: Twitter posts, url/website_url: websites
                    metadata = chunk.get("metadata", {})
                    source_url = (
                        metadata.get("post_url")  # LinkedIn posts
                        or metadata.get("tweet_url")  # Twitter tweets
                        or metadata.get("linkedin_url")  # LinkedIn profile
                        or metadata.get("url")  # Generic URL field
                        or metadata.get("website_url")  # Website pages
                        or chunk.get("source_url", "")
                    )

                    source = {
                        "title": self._get_source_title(chunk),
                        "content": chunk["content"],
                        "similarity": chunk.get("similarity", 0.0),
                        "source_url": source_url,
                        "source_type": chunk.get("source_type", "document"),
                        "raw_source": chunk.get("source", "unknown"),
                    }

                    # Add reranking metadata if available
                    if "rerank_score" in chunk:
                        source["rerank_score"] = chunk["rerank_score"]
                        source["original_similarity"] = chunk.get("original_similarity", 0.0)

                    citation_sources.append(source)

            logger.info(f"📚 Generated {len(citation_sources)} citation sources:")
            for i, source in enumerate(citation_sources):
                rerank_info = ""
                if "rerank_score" in source:
                    rerank_info = f", rerank: {source['rerank_score']:.2f}"
                logger.info(
                    f"   [{i + 1}] {source['title']} (similarity: {source['similarity']:.2f}{rerank_info})"
                )
                logger.info(f"       Content preview: {source['content'][:100]}...")

        # Step 7: Extract or just return raw retrieval
        if self.only_retrival:
            formatted_context = "\n\n---\n\n".join(unique_docs)
        else:
            formatted_context = await self.extractor.extract(user_query, unique_docs)

        # Debug logging
        logger.info(f"🔍 [CONTEXT_PIPELINE] formatted_context length: {len(formatted_context)}")
        if formatted_context:
            logger.info(
                f"🔍 [CONTEXT_PIPELINE] formatted_context preview: {formatted_context[:200]}..."
            )

        # Return context and sources if requested
        if return_citations:
            return {
                "context": formatted_context,
                "sources": citation_sources,
            }

        return formatted_context

    def _get_source_title(self, chunk: Dict[str, Any]) -> str:
        """Generate a user-friendly title for the source."""
        source = chunk.get("source", "Unknown Source")
        source_type = chunk.get("source_type", "document")

        # Title mapping for known sources
        SOURCE_TITLE_MAP = {
            "persona_profile": "Persona Profile",
            "linkedin_profile": "LinkedIn Profile",
            "twitter_profile": "Twitter Profile",
            "website_content": "Website Content",
        }

        # Check if source has a direct mapping
        if source in SOURCE_TITLE_MAP:
            return SOURCE_TITLE_MAP[source]
        elif source_type == "document":
            return f"Document: {source}"
        else:
            return source.replace("_", " ").title()
