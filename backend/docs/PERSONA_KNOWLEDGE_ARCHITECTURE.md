# Persona Management & Knowledge Base Architecture

**Version**: 1.0
**Date**: 2025-10-21
**Status**: Production Implementation

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Data Model & Relationships](#data-model--relationships)
4. [Knowledge Source Management](#knowledge-source-management)
5. [Persona-Knowledge Binding](#persona-knowledge-binding)
6. [RAG Query Pipeline](#rag-query-pipeline)
7. [API Architecture](#api-architecture)
8. [Implementation Details](#implementation-details)
9. [Frontend Integration Patterns](#frontend-integration-patterns)
10. [Performance Considerations](#performance-considerations)

---

## Executive Summary

### What is This System?

The **Persona Management & Knowledge Base Architecture** is a multi-tenant, user-centric system that enables users to:
1. **Aggregate knowledge** from multiple sources (LinkedIn, Twitter, websites, documents, YouTube)
2. **Create multiple personas** (e.g., "Professional Coach", "Tech Expert", "Casual Mentor")
3. **Assign specific knowledge** to each persona from a centralized library
4. **Query personas** with RAG-powered responses using only their assigned knowledge

### Core Innovation: User-Owned Embeddings

Traditional approach (❌):
```
Persona A scrapes LinkedIn → Creates embeddings for Persona A
Persona B scrapes same LinkedIn → Creates duplicate embeddings for Persona B
Result: 2x storage, 2x ingestion cost
```

Our approach (✅):
```
User scrapes LinkedIn → Creates embeddings owned by USER
Persona A uses LinkedIn → References user's embeddings
Persona B uses LinkedIn → References same user's embeddings
Result: 1x storage, 1x ingestion cost, N personas benefit
```

### Key Benefits

| Benefit | Description |
|---------|-------------|
| **Zero Duplication** | Embeddings stored once, shared across personas |
| **Flexible Knowledge** | Each persona can have different knowledge mix |
| **Dynamic Updates** | Enable/disable knowledge without re-ingestion |
| **Cost Efficient** | One scrape, many personas |
| **Scalable** | Add personas instantly, no data copying |

---

## System Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                             USER LAYER                                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  User Account (user_id)                                           │  │
│  │  - email, username, fullname                                      │  │
│  │  - Owns ALL knowledge sources and embeddings                      │  │
│  └───────────┬──────────────────────────────────────────────────────┘  │
└──────────────┼──────────────────────────────────────────────────────────┘
               │
               │ 1:N (One user → Many personas)
               │
┌──────────────┼──────────────────────────────────────────────────────────┐
│              │              PERSONA LAYER                                │
│  ┌───────────▼──────────┐  ┌──────────────────────────────────────┐   │
│  │  Persona A           │  │  Persona B                            │   │
│  │  "Professional"      │  │  "Casual Mentor"                      │   │
│  │  ├─ LinkedIn ✓       │  │  ├─ LinkedIn ✓                        │   │
│  │  ├─ Website A ✓      │  │  ├─ Twitter ✓                         │   │
│  │  └─ Document 1 ✓     │  │  └─ Document 2 ✓                      │   │
│  └──────────────────────┘  └──────────────────────────────────────┘   │
└────────────────┬─────────────────────────┬───────────────────────────────┘
                 │                         │
                 │ M:N via persona_data_sources
                 │                         │
┌────────────────┼─────────────────────────┼───────────────────────────────┐
│                │                         │     KNOWLEDGE LAYER            │
│  ┌─────────────▼─────────────────────────▼──────────────────────────┐  │
│  │              USER'S KNOWLEDGE LIBRARY                             │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │  📊 LinkedIn Sources                                              │  │
│  │    ├─ Profile (headline, summary, experiences)                    │  │
│  │    └─ Posts (all LinkedIn posts)                                  │  │
│  │                                                                    │  │
│  │  🐦 Twitter Sources                                               │  │
│  │    ├─ Profile (@username, bio, followers)                         │  │
│  │    └─ Tweets (all tweets)                                         │  │
│  │                                                                    │  │
│  │  🌐 Website Sources                                               │  │
│  │    ├─ blog.example.com (12 pages)                                 │  │
│  │    └─ portfolio.example.com (5 pages)                             │  │
│  │                                                                    │  │
│  │  📄 Document Sources                                              │  │
│  │    ├─ Resume_2024.pdf                                             │  │
│  │    └─ Research_Paper.pdf                                          │  │
│  │                                                                    │  │
│  │  🎥 YouTube Sources                                               │  │
│  │    └─ "How to Build AI Agents" (video + transcript)              │  │
│  └────────────────────────────┬──────────────────────────────────────┘  │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │
                                  │ Each source → Embeddings
                                  │
┌─────────────────────────────────┼───────────────────────────────────────┐
│                                 │       EMBEDDING LAYER                  │
│  ┌──────────────────────────────▼─────────────────────────────────┐   │
│  │  LlamaIndex Embeddings Table (pgvector)                         │   │
│  │                                                                  │   │
│  │  Custom Columns:                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────┐   │   │
│  │  │ user_id          (FK → users.id)   [OWNER]              │   │   │
│  │  │ source_record_id (Generic FK)      [LINKS TO SOURCE]    │   │   │
│  │  │ source           ('linkedin', 'twitter', 'website')      │   │   │
│  │  │ source_type      ('profile', 'post', 'page', 'pdf')     │   │   │
│  │  │ embedding        (vector[1536])    [SEMANTIC VECTOR]    │   │   │
│  │  │ text             (chunk content)                         │   │   │
│  │  │ posted_at        (timestamp)       [FOR FILTERING]      │   │   │
│  │  └─────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  │  Indexes:                                                        │   │
│  │  - user_id (fast user filtering)                                │   │
│  │  - source_record_id (fast source lookup)                        │   │
│  │  - embedding (HNSW for vector search)                           │   │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: From Ingestion to Query

```
┌────────────────────────────────────────────────────────────────────────┐
│ STEP 1: USER INGESTS KNOWLEDGE                                         │
└────────────────────────────────────────────────────────────────────────┘

User Action: Scrape LinkedIn Profile
    ↓
[LinkedIn API] → Raw Data (profile, posts, experiences)
    ↓
[Ingestion Service]
    ├─ Creates linkedin_basic_info record (source_record_id: profile_uuid)
    ├─ Creates linkedin_posts records (each has own source_record_id)
    └─ Creates linkedin_experiences records (each has own source_record_id)
    ↓
[LlamaIndex RAG System]
    ├─ Chunks content into semantic blocks
    ├─ Generates embeddings (OpenAI text-embedding-3-small)
    └─ Stores in data_llamaindex_embeddings table
    ↓
[ORM Post-Processing]
    ├─ Populates user_id from metadata
    ├─ Populates source_record_id from metadata
    └─ Populates source, source_type, posted_at

Result: Embeddings stored in user's knowledge library


┌────────────────────────────────────────────────────────────────────────┐
│ STEP 2: USER CREATES PERSONA WITH KNOWLEDGE                            │
└────────────────────────────────────────────────────────────────────────┘

User Action: Create "Professional Coach" persona with LinkedIn + Website
    ↓
[Persona Service]
    ├─ Creates persona record (persona_id, user_id, name, role, voice_id)
    └─ Attaches knowledge sources
    ↓
[Knowledge Library Service]
    ├─ Creates persona_data_sources entry:
    │   {
    │     persona_id: persona_uuid,
    │     source_type: "linkedin",
    │     source_record_id: profile_uuid,  ← Root source
    │     enabled: true
    │   }
    └─ Creates persona_data_sources entry:
        {
          persona_id: persona_uuid,
          source_type: "website",
          source_record_id: scrape_uuid,
          enabled: true
        }

Result: Persona linked to knowledge sources (no embedding duplication!)


┌────────────────────────────────────────────────────────────────────────┐
│ STEP 3: USER QUERIES PERSONA                                           │
└────────────────────────────────────────────────────────────────────────┘

User Query: "What's your experience with Python?"
    ↓
[RAG Query Pipeline]
    ├─ Step 1: Get Persona's Enabled Sources
    │   query persona_data_sources WHERE persona_id = ? AND enabled = true
    │   → Returns: [linkedin:profile_uuid, website:scrape_uuid]
    │
    ├─ Step 2: Expand Sources to Include Related Content
    │   expand_linkedin_source(profile_uuid)
    │     → [profile_uuid, post_uuid_1, post_uuid_2, exp_uuid_1, exp_uuid_2, ...]
    │   expand_website_source(scrape_uuid)
    │     → [scrape_uuid, page_uuid_1, page_uuid_2, ...]
    │
    │   Combined source_record_ids: [profile_uuid, post_uuid_1, ..., page_uuid_1, ...]
    │
    ├─ Step 3: Query LlamaIndex with Filters
    │   filters:
    │     - user_id = user_uuid  (only user's embeddings)
    │     - source_record_id IN (expanded_list)  (only persona's sources)
    │
    │   query_engine.query("What's your experience with Python?")
    │     → Returns top-k most relevant chunks (hybrid search: semantic + keyword)
    │
    └─ Step 4: Generate Response
        [LLM Context]
          System Prompt: Persona's cached system prompt
          RAG Context: Retrieved chunks about Python experience
          User Query: "What's your experience with Python?"

        [OpenAI GPT-4o] → "I have 5 years of experience with Python..."

Result: Response powered by only the persona's assigned knowledge


┌────────────────────────────────────────────────────────────────────────┐
│ STEP 4: USER MANAGES KNOWLEDGE DYNAMICALLY                             │
└────────────────────────────────────────────────────────────────────────┘

User Action: Disable LinkedIn for "Professional Coach" persona
    ↓
[Knowledge Library Service]
    UPDATE persona_data_sources
    SET enabled = false, disabled_at = NOW()
    WHERE persona_id = ? AND source_record_id = profile_uuid

Result: Next query won't use LinkedIn (no re-ingestion needed!)

User Action: Re-enable LinkedIn
    ↓
[Knowledge Library Service]
    UPDATE persona_data_sources
    SET enabled = true, enabled_at = NOW()
    WHERE persona_id = ? AND source_record_id = profile_uuid

Result: LinkedIn knowledge available again (instant toggle!)
```

---

## Data Model & Relationships

### Entity-Relationship Diagram

```sql
┌────────────────────────────────────────────────────────────────────────┐
│                         CORE ENTITIES                                   │
└────────────────────────────────────────────────────────────────────────┘

users
├─ id (UUID, PK)
├─ email (unique)
├─ username (unique)
├─ fullname
└─ onboarding_status

    │ 1:N
    ↓

personas
├─ id (UUID, PK)
├─ user_id (FK → users.id)  ✅ OWNERSHIP
├─ persona_name (unique per user, default: "default")
├─ name (display name)
├─ role (e.g., "Executive Coach")
├─ company
├─ description
├─ voice_id (ElevenLabs voice ID)
└─ created_at, updated_at

    │ M:N via persona_data_sources
    ↓

┌────────────────────────────────────────────────────────────────────────┐
│                    JUNCTION TABLE (KEY!)                                │
└────────────────────────────────────────────────────────────────────────┘

persona_data_sources
├─ id (UUID, PK)
├─ persona_id (FK → personas.id)
├─ source_type (enum: 'linkedin', 'twitter', 'website', 'document', 'youtube')
├─ source_record_id (UUID)  ✅ GENERIC FK to any source
├─ enabled (boolean)  ✅ QUICK TOGGLE
├─ source_filters (JSONB)  ← Future: advanced filtering
├─ created_at, updated_at
├─ enabled_at (timestamp)
└─ disabled_at (timestamp)

UNIQUE CONSTRAINT: (persona_id, source_type, source_record_id)
INDEXES: persona_id, enabled, source_type, source_record_id

    │ Links to various source types
    ↓

┌────────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE SOURCE TABLES                              │
└────────────────────────────────────────────────────────────────────────┘

linkedin_basic_info (LinkedIn Profile)
├─ id (UUID, PK)  ← source_record_id
├─ user_id (FK → users.id)  ✅ OWNERSHIP
├─ headline
├─ summary
├─ skills (JSONB array)
├─ location
└─ last_synced_at

linkedin_posts (LinkedIn Posts)
├─ id (UUID, PK)  ← source_record_id
├─ user_id (FK → users.id)
├─ linkedin_post_id (external ID)
├─ post_text
├─ num_likes, num_comments
└─ posted_at

linkedin_experiences (Work History)
├─ id (UUID, PK)  ← source_record_id
├─ user_id (FK → users.id)
├─ company_name
├─ title
├─ description
├─ start_date, end_date
└─ created_at

twitter_profiles (Twitter Profile)
├─ id (UUID, PK)  ← source_record_id
├─ user_id (FK → users.id)
├─ twitter_id (external ID)
├─ username
├─ display_name
├─ bio
├─ verified
├─ followers_count, following_count
└─ last_scraped_at

twitter_posts (Tweets)
├─ id (UUID, PK)  ← source_record_id
├─ twitter_profile_id (FK → twitter_profiles.id)
├─ tweet_id (external ID)
├─ content
├─ num_likes, num_retweets
└─ posted_at

website_scrape_metadata (Website Scrape Job)
├─ id (UUID, PK)  ← source_record_id
├─ user_id (FK → users.id)
├─ website_url (root URL)
├─ scraper (e.g., "firecrawl")
├─ title, description
├─ pages_crawled, max_pages_crawled
├─ scraping_status
└─ scraped_at

website_scrape_content (Individual Pages)
├─ id (UUID, PK)  ← source_record_id
├─ scrape_id (FK → website_scrape_metadata.id)
├─ page_url
├─ page_title
├─ content_markdown
└─ created_at

documents (PDFs, DOCX, etc.)
├─ id (UUID, PK)  ← source_record_id
├─ user_id (FK → users.id)
├─ filename
├─ document_type (pdf, xlsx, pptx, docx, csv, txt, md)
├─ file_size
├─ content_text (extracted)
├─ metadata (JSONB)
├─ page_count (computed)
└─ uploaded_at

youtube_videos (YouTube Videos)
├─ id (UUID, PK)  ← source_record_id
├─ user_id (FK → users.id)
├─ video_id (YouTube ID)
├─ title, description
├─ channel_name
├─ transcript (full transcript)
├─ duration_seconds
└─ published_at

    │ All sources → Embeddings
    ↓

┌────────────────────────────────────────────────────────────────────────┐
│                    EMBEDDING STORAGE (VECTOR DB)                        │
└────────────────────────────────────────────────────────────────────────┘

data_llamaindex_embeddings
├─ id (serial, PK)
│
├─ LlamaIndex Standard Columns:
│  ├─ text (chunk content)
│  ├─ metadata_ (JSONB) ← LlamaIndex internal metadata
│  ├─ node_id (LlamaIndex node identifier)
│  └─ embedding (vector[1536]) ← pgvector
│
├─ Custom Columns (for filtering):
│  ├─ user_id (UUID, FK → users.id)  ✅ OWNERSHIP
│  ├─ source_record_id (UUID)  ✅ LINKS TO SOURCE
│  ├─ source (text) → Platform: 'linkedin', 'twitter', 'website', 'document'
│  ├─ source_type (text) → Content type: 'profile', 'post', 'page', 'pdf'
│  ├─ posted_at (timestamp) → When content was created
│  └─ created_at (timestamp) → When embedding was created
│
└─ text_search_tsv (tsvector) ← Full-text search index

INDEXES:
- embedding (HNSW for fast vector similarity search)
- user_id (fast user filtering)
- source_record_id (fast source lookup)
- posted_at (temporal filtering)
- text_search_tsv (GIN for keyword search)
```

### How Source Record ID Works

The `source_record_id` is a **generic foreign key** pattern that allows `persona_data_sources` to link to any type of knowledge source:

```python
# Example 1: LinkedIn Profile
persona_data_sources:
  source_type: "linkedin"
  source_record_id: "550e8400-e29b-41d4-a716-446655440000"
                    ↑
                    Links to linkedin_basic_info.id

# When querying, expands to:
source_record_ids = [
  "550e8400-e29b-41d4-a716-446655440000",  # Profile
  "660e8400-e29b-41d4-a716-446655440001",  # Post 1
  "660e8400-e29b-41d4-a716-446655440002",  # Post 2
  "770e8400-e29b-41d4-a716-446655440003",  # Experience 1
  ...
]

# Example 2: Website Scrape
persona_data_sources:
  source_type: "website"
  source_record_id: "880e8400-e29b-41d4-a716-446655440000"
                    ↑
                    Links to website_scrape_metadata.id

# When querying, expands to:
source_record_ids = [
  "880e8400-e29b-41d4-a716-446655440000",  # Metadata
  "990e8400-e29b-41d4-a716-446655440001",  # Page 1
  "990e8400-e29b-41d4-a716-446655440002",  # Page 2
  ...
]

# Example 3: Document (no expansion needed)
persona_data_sources:
  source_type: "document"
  source_record_id: "aa0e8400-e29b-41d4-a716-446655440000"
                    ↑
                    Links to documents.id (single file)

# No expansion needed - document is atomic
source_record_ids = ["aa0e8400-e29b-41d4-a716-446655440000"]
```

---

## Knowledge Source Management

### Knowledge Library Abstraction

Each knowledge source has a **unified representation** across all platforms:

```python
@dataclass
class KnowledgeSource:
    """Unified knowledge source representation"""

    id: UUID                      # source_record_id
    type: SourceType              # linkedin, twitter, website, document, youtube
    display_name: str             # Human-readable name
    embeddings_count: int         # Number of chunks
    used_by_personas_count: int   # How many personas use it
    created_at: datetime
    updated_at: datetime

    # Platform-specific metadata
    metadata: Dict[str, Any]      # Varies by source type
```

### Source Type Handlers

Each source type has a dedicated handler for aggregation and expansion:

#### 1. LinkedIn Handler

```python
class LinkedInSourceHandler:
    """Handles LinkedIn profile aggregation"""

    async def get_source_metadata(self, profile_id: UUID) -> LinkedInKnowledgeSource:
        """Get LinkedIn profile with stats"""
        profile = await get_linkedin_profile(profile_id)
        posts_count = await count_linkedin_posts(user_id)
        experiences_count = await count_linkedin_experiences(user_id)
        embeddings_count = await count_embeddings(profile_id)

        return LinkedInKnowledgeSource(
            id=profile.id,
            display_name=profile.headline or "LinkedIn Profile",
            headline=profile.headline,
            summary=profile.summary,
            posts_count=posts_count,
            experiences_count=experiences_count,
            embeddings_count=embeddings_count,
            ...
        )

    async def expand_source(self, profile_id: UUID) -> List[UUID]:
        """Expand LinkedIn profile to include all related content"""
        # Get user_id from profile
        user_id = await get_user_id_from_profile(profile_id)

        # Collect all record IDs
        record_ids = [profile_id]  # Root profile

        # Add all posts
        posts = await get_all_linkedin_posts(user_id)
        record_ids.extend([post.id for post in posts])

        # Add all experiences
        experiences = await get_all_linkedin_experiences(user_id)
        record_ids.extend([exp.id for exp in experiences])

        return record_ids
```

#### 2. Website Handler

```python
class WebsiteSourceHandler:
    """Handles website scrape aggregation"""

    async def get_source_metadata(self, scrape_id: UUID) -> WebsiteKnowledgeSource:
        """Get website scrape with stats"""
        scrape = await get_website_scrape(scrape_id)
        pages_count = await count_website_pages(scrape_id)
        embeddings_count = await count_embeddings(scrape_id)

        return WebsiteKnowledgeSource(
            id=scrape.id,
            display_name=scrape.title or scrape.website_url,
            website_url=scrape.website_url,
            pages_crawled=pages_count,
            embeddings_count=embeddings_count,
            ...
        )

    async def expand_source(self, scrape_id: UUID) -> List[UUID]:
        """Expand website scrape to include all pages"""
        record_ids = [scrape_id]  # Root metadata

        # Add all pages
        pages = await get_all_website_pages(scrape_id)
        record_ids.extend([page.id for page in pages])

        return record_ids
```

#### 3. Document Handler

```python
class DocumentSourceHandler:
    """Handles document sources (PDFs, etc.)"""

    async def get_source_metadata(self, document_id: UUID) -> DocumentKnowledgeSource:
        """Get document with stats"""
        doc = await get_document(document_id)
        embeddings_count = await count_embeddings(document_id)

        return DocumentKnowledgeSource(
            id=doc.id,
            display_name=doc.filename,
            filename=doc.filename,
            document_type=doc.document_type,
            page_count=doc.page_count,
            embeddings_count=embeddings_count,
            ...
        )

    async def expand_source(self, document_id: UUID) -> List[UUID]:
        """No expansion needed for documents - atomic source"""
        return [document_id]
```

### Knowledge Library Service Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│             KnowledgeLibraryService                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Public Methods:                                                    │
│  ├─ get_user_knowledge_library(user_id)                           │
│  ├─ get_persona_knowledge_sources(persona_id)                     │
│  ├─ get_available_knowledge_sources(persona_id)                   │
│  ├─ attach_sources_to_persona(persona_id, sources)               │
│  ├─ detach_source_from_persona(persona_id, source_record_id)     │
│  ├─ toggle_source(persona_id, source_record_id)                  │
│  ├─ delete_knowledge_source(source_type, source_record_id)       │
│  └─ get_personas_using_source(source_record_id)                  │
│                                                                     │
│  Private Helpers:                                                   │
│  ├─ _get_linkedin_sources(user_id)                               │
│  ├─ _get_twitter_sources(user_id)                                │
│  ├─ _get_website_sources(user_id)                                │
│  ├─ _get_document_sources(user_id)                               │
│  ├─ _get_youtube_sources(user_id)                                │
│  ├─ _get_source_embeddings_count(source_record_id)               │
│  ├─ _get_personas_using_source_count(source_record_id)           │
│  └─ _expand_source_record_ids(persona_id)                        │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## Persona-Knowledge Binding

### Persona Data Sources Junction Table

The `persona_data_sources` table is the heart of the knowledge management system:

```sql
CREATE TABLE persona_data_sources (
    id UUID PRIMARY KEY,
    persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,
    source_record_id UUID NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    source_filters JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    enabled_at TIMESTAMP,
    disabled_at TIMESTAMP,

    UNIQUE (persona_id, source_type, source_record_id)
);

CREATE INDEX idx_persona_data_sources_persona ON persona_data_sources(persona_id);
CREATE INDEX idx_persona_data_sources_enabled ON persona_data_sources(enabled);
CREATE INDEX idx_persona_data_sources_source ON persona_data_sources(source_record_id);
```

### Lifecycle Operations

#### 1. Attach Knowledge Source to Persona

```python
async def attach_sources_to_persona(
    persona_id: UUID,
    sources: List[KnowledgeSourceAttachment]
) -> List[PersonaDataSource]:
    """
    Attach multiple knowledge sources to a persona.

    If source already attached but disabled, re-enable it.
    If source already attached and enabled, no-op.
    """
    for source_attachment in sources:
        # Check if already attached
        existing = await get_persona_data_source(
            persona_id=persona_id,
            source_record_id=source_attachment.source_record_id
        )

        if existing:
            if not existing.enabled:
                # Re-enable
                existing.enabled = True
                existing.enabled_at = datetime.now(timezone.utc)
                existing.disabled_at = None
                await session.commit()
        else:
            # Create new attachment
            pds = PersonaDataSource(
                persona_id=persona_id,
                source_type=source_attachment.source_type,
                source_record_id=source_attachment.source_record_id,
                enabled=True,
                enabled_at=datetime.now(timezone.utc)
            )
            session.add(pds)
            await session.commit()
```

#### 2. Detach Knowledge Source from Persona

```python
async def detach_source_from_persona(
    persona_id: UUID,
    source_record_id: UUID
) -> bool:
    """
    Completely remove knowledge source from persona.

    This deletes the persona_data_sources entry.
    The source and embeddings remain in user's library.
    """
    stmt = delete(PersonaDataSource).where(
        PersonaDataSource.persona_id == persona_id,
        PersonaDataSource.source_record_id == source_record_id
    )
    result = await session.execute(stmt)
    await session.commit()

    return result.rowcount > 0
```

#### 3. Toggle Knowledge Source (Enable/Disable)

```python
async def toggle_source(
    persona_id: UUID,
    source_record_id: UUID
) -> bool:
    """
    Toggle enabled state without removing attachment.

    Useful for temporarily disabling knowledge without losing configuration.
    """
    pds = await get_persona_data_source(persona_id, source_record_id)

    if not pds:
        return False

    pds.enabled = not pds.enabled
    if pds.enabled:
        pds.enabled_at = datetime.now(timezone.utc)
        pds.disabled_at = None
    else:
        pds.disabled_at = datetime.now(timezone.utc)

    await session.commit()
    return True
```

#### 4. Delete Knowledge Source (Cascade)

```python
async def delete_knowledge_source(
    source_type: str,
    source_record_id: UUID
) -> Tuple[int, int]:
    """
    Delete knowledge source and all its embeddings.

    Steps:
    1. Remove from all personas (persona_data_sources)
    2. Delete embeddings
    3. Delete source record

    Returns:
        (embeddings_deleted, personas_affected)
    """
    # Step 1: Count and remove persona attachments
    personas_stmt = select(PersonaDataSource).where(
        PersonaDataSource.source_record_id == source_record_id
    )
    personas = (await session.execute(personas_stmt)).scalars().all()
    personas_affected = len(personas)

    delete_personas_stmt = delete(PersonaDataSource).where(
        PersonaDataSource.source_record_id == source_record_id
    )
    await session.execute(delete_personas_stmt)

    # Step 2: Delete embeddings (expanded to include related content)
    expanded_ids = await expand_source_record_ids(source_record_id, source_type)

    delete_embeddings_stmt = delete(LlamaIndexEmbedding).where(
        LlamaIndexEmbedding.source_record_id.in_(expanded_ids)
    )
    embeddings_result = await session.execute(delete_embeddings_stmt)
    embeddings_deleted = embeddings_result.rowcount

    # Step 3: Delete source record(s)
    if source_type == "linkedin":
        await delete_linkedin_source(source_record_id)
    elif source_type == "twitter":
        await delete_twitter_source(source_record_id)
    # ... etc

    await session.commit()

    return (embeddings_deleted, personas_affected)
```

---

## RAG Query Pipeline

### Query Flow with Persona Filtering

```
User Query: "What's your experience with machine learning?"
Persona: "Professional Coach" (persona_id: abc-123)

┌────────────────────────────────────────────────────────────────────┐
│ PHASE 1: Get Persona's Enabled Sources                             │
└────────────────────────────────────────────────────────────────────┘

Query:
  SELECT source_type, source_record_id
  FROM persona_data_sources
  WHERE persona_id = 'abc-123' AND enabled = true

Result:
  [
    {source_type: "linkedin", source_record_id: "550e8400..."},
    {source_type: "website", source_record_id: "880e8400..."}
  ]

┌────────────────────────────────────────────────────────────────────┐
│ PHASE 2: Expand Sources to Include Related Content                 │
└────────────────────────────────────────────────────────────────────┘

For each source, call expansion logic:

expand_linkedin_source("550e8400..."):
  - Get user_id from linkedin_basic_info
  - Collect: profile_id, all post IDs, all experience IDs
  → ["550e8400...", "660e8400...", "660e8401...", "770e8400...", ...]

expand_website_source("880e8400..."):
  - Get all pages from website_scrape_content
  → ["880e8400...", "990e8400...", "990e8401...", ...]

Combined:
  source_record_ids = [
    "550e8400...",  # LinkedIn profile
    "660e8400...",  # LinkedIn post 1
    "660e8401...",  # LinkedIn post 2
    "770e8400...",  # LinkedIn experience 1
    "880e8400...",  # Website metadata
    "990e8400...",  # Website page 1
    "990e8401...",  # Website page 2
    ...
  ]

┌────────────────────────────────────────────────────────────────────┐
│ PHASE 3: Query LlamaIndex with Filters                             │
└────────────────────────────────────────────────────────────────────┘

# Build metadata filters
filters = MetadataFilters(filters=[
    ExactMatchFilter(key="user_id", value="user-uuid-789"),
    MetadataFilter(
        key="source_record_id",
        value=source_record_ids,
        operator=FilterOperator.IN
    )
])

# Query with hybrid search (semantic + keyword)
query_engine = index.as_query_engine(
    filters=filters,
    similarity_top_k=10,
    vector_store_query_mode="hybrid"
)

response = await query_engine.aquery(
    "What's your experience with machine learning?"
)

Result:
  Retrieved Chunks:
    1. [LinkedIn Experience] "Led ML team at TechCorp..."
    2. [LinkedIn Post] "Just published paper on neural networks..."
    3. [Website Page] "My approach to machine learning is..."
    4. [LinkedIn Experience] "Implemented deep learning models..."
    5. ...

┌────────────────────────────────────────────────────────────────────┐
│ PHASE 4: Generate Response with LLM                                 │
└────────────────────────────────────────────────────────────────────┘

Context for LLM:
  [System Prompt]
    You are Professional Coach, an Executive Coach helping leaders...
    <persona's cached system prompt>

  [RAG Context]
    Retrieved information about your experience:
    - Led ML team at TechCorp for 3 years
    - Published paper on neural networks
    - Implemented deep learning models for computer vision
    ...

  [User Query]
    What's your experience with machine learning?

[OpenAI GPT-4o] → Generate Response
  "I have extensive experience with machine learning, having led
   an ML team at TechCorp where we focused on deep learning for
   computer vision. I've also published research on neural networks
   and applied ML to solve complex business problems..."

Response sent to user.
```

### Code Implementation

```python
async def query_persona_with_rag(
    persona_id: UUID,
    user_query: str,
    session_id: Optional[str] = None
) -> str:
    """
    Query persona with RAG-powered response.

    Args:
        persona_id: Persona UUID
        user_query: User's question
        session_id: Optional conversation session ID

    Returns:
        LLM response powered by persona's knowledge
    """
    # Phase 1: Get persona's enabled sources
    enabled_sources = await get_enabled_persona_sources(persona_id)

    if not enabled_sources:
        return "I don't have any knowledge sources enabled. Please attach some knowledge to me first."

    # Phase 2: Expand sources to include related content
    source_record_ids = []
    for source in enabled_sources:
        expanded_ids = await expand_source(
            source_type=source.source_type,
            source_record_id=source.source_record_id
        )
        source_record_ids.extend(expanded_ids)

    # Phase 3: Query LlamaIndex with filters
    rag_system = get_rag_system()

    filters = MetadataFilters(filters=[
        ExactMatchFilter(key="user_id", value=str(persona.user_id)),
        MetadataFilter(
            key="source_record_id",
            value=[str(sid) for sid in source_record_ids],
            operator=FilterOperator.IN
        )
    ])

    query_engine = rag_system.index.as_query_engine(
        filters=filters,
        similarity_top_k=10,
        vector_store_query_mode="hybrid"
    )

    # Phase 4: Generate response
    response = await query_engine.aquery(user_query)

    return response.response
```

---

## API Architecture

### RESTful Endpoint Design

```
┌────────────────────────────────────────────────────────────────────┐
│ Knowledge Library Management                                        │
└────────────────────────────────────────────────────────────────────┘

GET    /api/v1/knowledge-library/users/{user_id}
       → Get user's complete knowledge library

GET    /api/v1/knowledge-library/{source_type}/{source_id}
       → Get detailed info about specific knowledge source

DELETE /api/v1/knowledge-library/{source_type}/{source_id}
       → Delete knowledge source (cascade to embeddings, persona attachments)

POST   /api/v1/knowledge-library/{source_type}/{source_id}/re-ingest
       → Re-ingest knowledge source (TODO)


┌────────────────────────────────────────────────────────────────────┐
│ Persona Knowledge Management                                        │
└────────────────────────────────────────────────────────────────────┘

GET    /api/v1/personas/{persona_id}/knowledge-sources
       → Get all knowledge sources for persona

GET    /api/v1/personas/{persona_id}/knowledge-sources/available
       → Get available sources to attach (user's library)

POST   /api/v1/personas/{persona_id}/knowledge-sources
       → Attach knowledge sources to persona

DELETE /api/v1/personas/{persona_id}/knowledge-sources/{source_record_id}
       → Detach knowledge source from persona

PATCH  /api/v1/personas/{persona_id}/knowledge-sources/{source_record_id}/toggle
       → Toggle knowledge source enabled/disabled


┌────────────────────────────────────────────────────────────────────┐
│ Enhanced Persona CRUD                                               │
└────────────────────────────────────────────────────────────────────┘

POST   /api/v1/personas/with-knowledge?user_id={uuid}
       → Create persona with knowledge sources in one request

PATCH  /api/v1/personas/{persona_id}/with-knowledge
       → Update persona and optionally replace knowledge sources

GET    /api/v1/personas/users/{user_id}/personas
       → List all personas for user with knowledge stats
```

### Response Schema Hierarchy

```
KnowledgeLibraryResponse
├─ linkedin: List[LinkedInKnowledgeSource]
│  ├─ id, display_name, headline, summary
│  ├─ posts_count, experiences_count, skills_count
│  ├─ embeddings_count, used_by_personas_count
│  └─ last_synced_at, created_at, updated_at
│
├─ twitter: List[TwitterKnowledgeSource]
│  ├─ id, display_name, username, bio
│  ├─ tweets_count, followers_count, following_count
│  ├─ embeddings_count, used_by_personas_count
│  └─ last_scraped_at, created_at, updated_at
│
├─ websites: List[WebsiteKnowledgeSource]
│  ├─ id, display_name, website_url
│  ├─ pages_crawled, max_pages_crawled, scraper
│  ├─ embeddings_count, used_by_personas_count
│  └─ scraped_at, created_at, updated_at
│
├─ documents: List[DocumentKnowledgeSource]
│  ├─ id, display_name, filename, document_type
│  ├─ file_size, page_count, sheet_count, slide_count
│  ├─ embeddings_count, used_by_personas_count
│  └─ uploaded_at, created_at, updated_at
│
├─ youtube: List[YouTubeKnowledgeSource]
│  ├─ id, display_name, video_id, title
│  ├─ channel_name, duration_seconds, has_transcript
│  ├─ embeddings_count, used_by_personas_count
│  └─ published_at, created_at, updated_at
│
├─ total_sources: int
└─ total_embeddings: int
```

---

## Implementation Details

### Service Layer: `KnowledgeLibraryService`

**Location**: `app/services/knowledge_library_service.py` (759 lines)

**Key Methods**:

```python
class KnowledgeLibraryService:
    async def get_user_knowledge_library(user_id: UUID) -> KnowledgeLibraryResponse
    async def get_persona_knowledge_sources(persona_id: UUID) -> List[PersonaKnowledgeSource]
    async def get_available_knowledge_sources(persona_id: UUID) -> AvailableKnowledgeSourcesResponse
    async def attach_sources_to_persona(persona_id: UUID, sources: List[KnowledgeSourceAttachment])
    async def detach_source_from_persona(persona_id: UUID, source_record_id: UUID) -> bool
    async def toggle_source(persona_id: UUID, source_record_id: UUID) -> bool
    async def delete_knowledge_source(source_type: str, source_record_id: UUID) -> Tuple[int, int]
    async def get_personas_using_source(source_record_id: UUID) -> List[Dict]
```

### API Routes

**Knowledge Library**: `app/api/knowledge_library_routes.py` (178 lines)
**Persona Knowledge**: `app/api/persona_knowledge_routes.py` (577 lines)

### Schemas

**Location**: `app/schemas/knowledge_library.py` (335 lines)

**Key Models**:
- `KnowledgeLibraryResponse`: User's complete knowledge library
- `PersonaKnowledgeResponse`: Persona's knowledge sources
- `AvailableKnowledgeSourcesResponse`: Available sources for persona selection
- `PersonaWithKnowledgeResponse`: Persona with knowledge stats
- `AttachKnowledgeRequest`: Request to attach sources
- `PersonaCreateWithKnowledge`: Create persona with knowledge
- Platform-specific models: `LinkedInKnowledgeSource`, `TwitterKnowledgeSource`, etc.

---

## Frontend Integration Patterns

### 1. Knowledge Library Dashboard

```typescript
interface KnowledgeLibraryDashboard {
  // Fetch user's knowledge library
  async function loadKnowledgeLibrary(userId: string) {
    const response = await fetch(`/api/v1/knowledge-library/users/${userId}`)
    const library: KnowledgeLibraryResponse = await response.json()

    // Display grouped sources
    renderLinkedInSources(library.linkedin)
    renderTwitterSources(library.twitter)
    renderWebsiteSources(library.websites)
    renderDocumentSources(library.documents)
    renderYouTubeSources(library.youtube)

    // Show statistics
    displayStats({
      totalSources: library.total_sources,
      totalEmbeddings: library.total_embeddings
    })
  }

  // Delete knowledge source
  async function deleteSource(sourceType: string, sourceId: string) {
    const confirmed = confirm(
      "This will delete the source and all its embeddings. " +
      "All personas using this source will lose access. Continue?"
    )

    if (confirmed) {
      const response = await fetch(
        `/api/v1/knowledge-library/${sourceType}/${sourceId}`,
        { method: 'DELETE' }
      )
      const result = await response.json()

      alert(`Deleted ${result.embeddings_deleted} embeddings, ` +
            `detached from ${result.personas_affected} personas`)

      // Reload library
      await loadKnowledgeLibrary(userId)
    }
  }
}
```

### 2. Persona Creation/Edit Form

```typescript
interface PersonaKnowledgeSelector {
  // Load available sources
  async function loadAvailableSources(personaId?: string) {
    let url: string

    if (personaId) {
      // Editing existing persona
      url = `/api/v1/personas/${personaId}/knowledge-sources/available`
    } else {
      // Creating new persona - use user's library
      url = `/api/v1/knowledge-library/users/${userId}`
    }

    const response = await fetch(url)
    const data = await response.json()

    // Render multi-select checkboxes
    renderSourceSelector(data)
  }

  // Create persona with knowledge
  async function createPersonaWithKnowledge(formData: PersonaForm) {
    const payload = {
      persona_name: formData.personaName,
      name: formData.name,
      role: formData.role,
      description: formData.description,
      voice_id: formData.voiceId,
      knowledge_sources: selectedSources.map(s => ({
        source_type: s.type,
        source_record_id: s.id
      }))
    }

    const response = await fetch(
      `/api/v1/personas/with-knowledge?user_id=${userId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }
    )

    const persona = await response.json()

    console.log(`Created persona with ${persona.enabled_sources_count} sources`)
    console.log(`Total embeddings: ${persona.total_embeddings}`)

    // Navigate to persona detail page
    router.push(`/personas/${persona.id}`)
  }
}
```

### 3. Persona Management Dashboard

```typescript
interface PersonaManagementDashboard {
  // Load user's personas
  async function loadPersonas(userId: string) {
    const response = await fetch(`/api/v1/personas/users/${userId}/personas`)
    const data: UserPersonasResponse = await response.json()

    // Render persona cards
    data.personas.forEach(persona => {
      renderPersonaCard({
        id: persona.id,
        name: persona.name,
        role: persona.role,
        knowledgeSources: `${persona.enabled_sources_count}/${persona.knowledge_sources_count}`,
        totalEmbeddings: persona.total_embeddings,
        createdAt: persona.created_at
      })
    })
  }

  // Quick toggle knowledge source
  async function toggleKnowledgeSource(
    personaId: string,
    sourceRecordId: string
  ) {
    const response = await fetch(
      `/api/v1/personas/${personaId}/knowledge-sources/${sourceRecordId}/toggle`,
      { method: 'PATCH' }
    )

    if (response.ok) {
      // Reload persona to show updated state
      await loadPersonaKnowledge(personaId)
    }
  }

  // Load persona's knowledge sources
  async function loadPersonaKnowledge(personaId: string) {
    const response = await fetch(
      `/api/v1/personas/${personaId}/knowledge-sources`
    )
    const data: PersonaKnowledgeResponse = await response.json()

    // Display sources with enable/disable toggles
    data.sources.forEach(source => {
      renderKnowledgeSourceRow({
        displayName: source.display_name,
        type: source.source_type,
        enabled: source.enabled,
        embeddingsCount: source.embeddings_count,
        onToggle: () => toggleKnowledgeSource(personaId, source.source_record_id)
      })
    })
  }
}
```

---

## Performance Considerations

### 1. Indexing Strategy

```sql
-- Fast user filtering
CREATE INDEX idx_embeddings_user_id ON data_llamaindex_embeddings(user_id);

-- Fast source lookup
CREATE INDEX idx_embeddings_source_record_id ON data_llamaindex_embeddings(source_record_id);

-- Fast persona source lookup
CREATE INDEX idx_persona_data_sources_persona ON persona_data_sources(persona_id);
CREATE INDEX idx_persona_data_sources_enabled ON persona_data_sources(enabled);

-- Fast vector similarity search
CREATE INDEX idx_embeddings_vector ON data_llamaindex_embeddings
USING hnsw (embedding vector_cosine_ops);

-- Fast full-text search
CREATE INDEX idx_embeddings_text_search ON data_llamaindex_embeddings
USING gin(text_search_tsv);
```

### 2. Query Optimization

**Efficient Source Expansion**:
```python
# ❌ Inefficient: N+1 queries
for source in persona_sources:
    expanded = expand_source(source.source_record_id)
    all_ids.extend(expanded)

# ✅ Efficient: Bulk expansion
user_id = get_user_id_from_persona(persona_id)
all_linkedin_posts = get_all_linkedin_posts(user_id)  # Single query
all_linkedin_experiences = get_all_linkedin_experiences(user_id)  # Single query
```

**Parallel Fetching**:
```python
# ✅ Fetch all source types in parallel
linkedin, twitter, websites, documents, youtube = await asyncio.gather(
    _get_linkedin_sources(session, user_id),
    _get_twitter_sources(session, user_id),
    _get_website_sources(session, user_id),
    _get_document_sources(session, user_id),
    _get_youtube_sources(session, user_id)
)
```

### 3. Caching Strategy

```python
# Cache source expansions (rarely change)
@lru_cache(maxsize=1000)
async def expand_source(source_type: str, source_record_id: UUID) -> List[UUID]:
    ...

# Cache persona system prompts (change infrequently)
@lru_cache(maxsize=100)
async def get_persona_system_prompt(persona_id: UUID) -> str:
    ...

# Invalidate cache on source changes
async def attach_source_to_persona(...):
    ...
    expand_source.cache_clear()  # Invalidate
```

### 4. Database Connection Pooling

```python
# app/database/models/database.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # Connection pool size
    max_overflow=10,       # Additional connections
    pool_pre_ping=True,    # Test connections before use
    pool_recycle=3600,     # Recycle connections hourly
    echo=False             # Disable SQL logging in prod
)
```

---

## Summary

This architecture provides:
- ✅ **User-centric knowledge ownership** with zero duplication
- ✅ **Flexible persona management** with granular knowledge control
- ✅ **Efficient RAG queries** with proper filtering and source expansion
- ✅ **Frontend-ready APIs** for building modern dashboards
- ✅ **Scalable design** supporting unlimited personas per user
- ✅ **Type-safe implementation** with Pydantic validation
- ✅ **Clean separation of concerns** (routes → service → repository)

**Total Implementation**:
- **8 files modified**: +1967 lines
- **12 API endpoints**: Complete RESTful interface
- **17 Pydantic models**: Type-safe request/response
- **25 service methods**: Comprehensive business logic

---

**Document Version**: 1.0
**Last Updated**: 2025-10-21
**Status**: Production-ready
