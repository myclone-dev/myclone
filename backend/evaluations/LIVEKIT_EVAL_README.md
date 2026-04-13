# LiveKit Agent Evaluation System

Automated evaluation system for testing LiveKit text-only agents against ground truth test cases.

## Overview

This evaluation system provides three modes:
1. **Single Query Evaluation** - Test individual questions against expected answers
2. **Conversation Evaluation** - Test multi-turn conversations (up to 3 turns) with context retention scoring
3. **Document Evaluation** - Test document-based Q&A with S3 file attachments

All modes:
- Connect to a LiveKit text agent via the `/api/v1/livekit/connection-details` endpoint
- Capture agent responses and citations
- Evaluate responses using LLM-based scoring
- Generate detailed reports with pass/fail status

---

# Part 1: Single Query Evaluation

For testing individual questions against expected answers.

## Quick Start

```bash
# Run evaluation with test cases
python -m evaluations.livekit_text_agent_eval \
    --username rishikesh \
    --persona default \
    --test-file evaluations/test-cases/example_test_cases.json

# With custom options
python -m evaluations.livekit_text_agent_eval \
    --username rishikesh \
    --persona default \
    --test-file my_test_cases.json \
    --api-url http://localhost:8000 \
    --threshold 0.7 \
    --output results/my_eval.json
```

## Test Case JSON Format

```json
{
  "description": "Description of test suite",
  "version": "1.0",
  "test_cases": [
    {
      "id": "unique-id-1",
      "category": "introduction",
      "question": "The question to ask the agent",
      "ground_truth": "The expected correct answer",
      "expected_keywords": ["keyword1", "keyword2"],
      "metadata": {
        "difficulty": "easy",
        "expected_retrieval": true
      }
    }
  ]
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier for the test case |
| `question` | Yes | The question to send to the agent |
| `ground_truth` | Yes | The expected/correct answer |
| `expected_keywords` | No | Keywords that should appear in response |
| `category` | No | Category for grouping results |
| `metadata` | No | Additional metadata (difficulty, etc.) |

## Evaluation Metrics

### 1. Semantic Similarity (35% weight)
Uses GPT-4o-mini to evaluate how well the agent's response captures the same meaning as the ground truth.

- **1.0**: Perfectly captures the same meaning
- **0.8**: Captures most key information
- **0.6**: Some key information but misses points
- **0.4**: Partially related
- **0.0**: Completely unrelated

### 2. Factual Accuracy (35% weight)
Evaluates whether the agent's response contains accurate information compared to ground truth.

- **1.0**: All facts accurate
- **0.8**: Mostly accurate
- **0.6**: Some accurate, some incorrect
- **0.0**: Contradicts ground truth

### 3. Keyword Coverage (15% weight)
Checks what percentage of expected keywords appear in the response.

```
score = found_keywords / total_expected_keywords
```

### 4. Retrieval Relevance (15% weight)
Evaluates if the citations/sources retrieved are relevant to the question.

- **1.0**: All citations highly relevant
- **0.5**: Neutral (no citations returned)
- **0.0**: Citations irrelevant

### Overall Score

```
overall = (semantic * 0.35) + (factual * 0.35) + (keyword * 0.15) + (retrieval * 0.15)
```

Default passing threshold: **0.7**

## Output Report

Reports are saved to `evaluations/results/` with format:
```
eval_{username}_{persona}_{timestamp}.json
```

### Report Structure

```json
{
  "username": "rishikesh",
  "persona": "default",
  "timestamp": "2026-01-06T10:30:00",
  "summary": {
    "total_test_cases": 10,
    "passed_count": 8,
    "failed_count": 2,
    "pass_rate": 0.8
  },
  "average_scores": {
    "semantic_similarity": 0.82,
    "factual_accuracy": 0.78,
    "keyword_coverage": 0.90,
    "retrieval_relevance": 0.75,
    "overall": 0.81,
    "response_time_ms": 2500
  },
  "category_scores": {
    "introduction": 0.85,
    "knowledge": 0.78
  },
  "results": [...]
}
```

## Programmatic Usage

```python
import asyncio
from evaluations.livekit_text_agent_eval import (
    LiveKitAgentEvaluator,
    TestCase,
    print_report,
    save_report
)

async def run_eval():
    # Define test cases
    test_cases = [
        TestCase(
            id="test-1",
            question="Who are you?",
            ground_truth="I am an AI assistant.",
            expected_keywords=["AI", "assistant"]
        ),
        TestCase(
            id="test-2", 
            question="What can you do?",
            ground_truth="I can answer questions and help with information.",
            expected_keywords=["questions", "help", "information"]
        )
    ]
    
    # Create evaluator
    evaluator = LiveKitAgentEvaluator(
        api_url="http://localhost:8000",
        passing_threshold=0.7
    )
    
    # Run evaluation
    report = await evaluator.run_evaluation(
        username="rishikesh",
        persona="default",
        test_cases=test_cases,
        delay_between_questions=2.0
    )
    
    # Print and save
    print_report(report)
    save_report(report, "my_report.json")
    
    return report

# Run
report = asyncio.run(run_eval())
print(f"Pass rate: {report.passed_count}/{report.total_test_cases}")
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--username, -u` | Required | Expert username |
| `--persona, -p` | "default" | Persona name |
| `--test-file, -t` | Required | Path to test cases JSON |
| `--api-url` | http://localhost:8000 | API base URL |
| `--threshold` | 0.7 | Passing score threshold |
| `--delay` | 2.0 | Seconds between questions |
| `--output, -o` | Auto-generated | Output JSON report path |

## Requirements

- Python 3.10+
- `livekit` SDK
- `openai` SDK
- `httpx`

Install dependencies:
```bash
pip install livekit openai httpx
```

## Environment Variables

```bash
OPENAI_API_KEY=sk-...  # Required for LLM-based evaluation
```

## Exit Codes

- **0**: Pass rate >= 80%
- **1**: Pass rate < 80%

## Examples

### Basic Evaluation
```bash
python -m evaluations.livekit_text_agent_eval \
    -u rishikesh \
    -t evaluations/test-cases/example_test_cases.json
```

### Strict Evaluation (90% threshold)
```bash
python -m evaluations.livekit_text_agent_eval \
    -u rishikesh \
    -t my_tests.json \
    --threshold 0.9
```

### Production Environment
```bash
python -m evaluations.livekit_text_agent_eval \
    -u myexpert \
    -p production \
    -t evaluations/test-cases/prod_tests.json \
    --api-url https://your-production-url.com \
    -o evaluations/results/prod_eval.json
```

## Troubleshooting

### No Response from Agent
- Check if the agent worker is running
- Verify the username/persona exists
- Check API logs for errors

### Low Retrieval Scores
- Ensure the persona has knowledge base content
- Check if questions match the knowledge topics

### Timeout Errors
- Increase `--delay` between questions
- Check agent worker performance

---

# Part 2: Conversation Evaluation

For testing multi-turn conversations with context retention across turns (up to 3 follow-up questions).

## Quick Start

```bash
# Run conversation evaluation
python -m evaluations.livekit_conversation_eval \
    --username rishikesh \
    --persona default \
    --test-file evaluations/test-cases/conversation_test_cases.json

# With custom options
python -m evaluations.livekit_conversation_eval \
    --username rishikesh \
    --persona default \
    --test-file my_conversations.json \
    --threshold 0.7 \
    --turn-delay 2.0 \
    --conv-delay 5.0 \
    --output results/conv_eval.json
```

## Conversation Test Case JSON Format

```json
{
  "test_cases": [
    {
      "id": "conv-context-basic",
      "category": "context_retention",
      "description": "Tests if agent remembers previous context",
      "turns": [
        {
          "query": "What are the main benefits of using React?",
          "ground_truth": "React offers component-based architecture, virtual DOM...",
          "expected_keywords": ["component", "virtual DOM"]
        },
        {
          "query": "Can you elaborate on the component-based architecture you mentioned?",
          "ground_truth": "Component-based architecture allows reusable, self-contained pieces...",
          "expected_keywords": ["reusable", "state"],
          "context_check": "Should reference the previous discussion about React benefits"
        },
        {
          "query": "How does this compare to traditional approaches?",
          "ground_truth": "Traditional approaches use monolithic structures...",
          "expected_keywords": ["separation", "traditional"],
          "context_check": "Should understand 'this' refers to React's component approach"
        }
      ]
    }
  ]
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier for the conversation |
| `turns` | Yes | Array of conversation turns (max 3) |
| `category` | No | Category for grouping (context_retention, clarification, etc.) |
| `description` | No | Description of what the conversation tests |

### Turn Fields

| Field | Required | Description |
|-------|----------|-------------|
| `query` | Yes | The user's question/message |
| `ground_truth` | Yes | Expected correct response |
| `expected_keywords` | No | Keywords that should appear in response |
| `context_check` | No | Description of what context should be retained from previous turns |

## Conversation Evaluation Metrics

### Per-Turn Metrics

#### 1. Semantic Similarity (25% weight)
Same as single query evaluation - measures meaning match.

#### 2. Factual Accuracy (25% weight)
Same as single query evaluation - measures correctness.

#### 3. Keyword Coverage (10% weight)
Same as single query evaluation - checks for expected keywords.

#### 4. Context Retention (25% weight) ⭐ NEW
Evaluates if the agent appropriately uses context from previous turns.

- **1.0**: Perfectly uses and builds upon previous context
- **0.8**: Good use of context with minor gaps
- **0.6**: Uses some context but misses important references
- **0.4**: Limited context usage
- **0.2**: Barely uses previous context
- **0.0**: Completely ignores previous conversation

### Conversation-Level Metrics

#### 5. Conversation Coherence (15% weight) ⭐ NEW
Evaluates overall conversation flow and consistency across all turns.

- **1.0**: Perfectly coherent, natural flow, maintains context throughout
- **0.8**: Good coherence with minor inconsistencies
- **0.6**: Some coherence issues, occasionally loses track
- **0.4**: Noticeable problems, responses feel disconnected
- **0.0**: No coherence, each response is independent

### Overall Score

```
overall = (semantic * 0.25) + (factual * 0.25) + (keyword * 0.10) + (context * 0.25) + (coherence * 0.15)
```

## Conversation CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--username, -u` | Required | Expert username |
| `--persona, -p` | "default" | Persona name |
| `--test-file, -t` | Required | Path to conversation test cases JSON |
| `--api-url` | http://localhost:8000 | API base URL |
| `--threshold` | 0.7 | Passing score threshold |
| `--turn-delay` | 2.0 | Seconds between turns in a conversation |
| `--conv-delay` | 5.0 | Seconds between conversations (fresh connection) |
| `--output, -o` | Auto-generated | Output JSON report path |

## Conversation Report Structure

```json
{
  "username": "rishikesh",
  "persona": "default",
  "timestamp": "2026-01-07T10:30:00",
  "summary": {
    "total_conversations": 5,
    "passed_count": 4,
    "failed_count": 1,
    "pass_rate": 0.8
  },
  "average_scores": {
    "semantic_similarity": 0.82,
    "factual_accuracy": 0.78,
    "keyword_coverage": 0.90,
    "context_retention": 0.85,
    "conversation_coherence": 0.88,
    "overall": 0.83
  },
  "category_scores": {
    "context_retention": 0.85,
    "clarification": 0.80
  },
  "results": [
    {
      "test_case_id": "conv-context-basic",
      "turns": [...],
      "conversation_scores": {
        "avg_semantic_similarity": 0.82,
        "conversation_coherence": 0.88,
        "overall": 0.83
      },
      "passed": true
    }
  ]
}
```

## Programmatic Usage (Conversations)

```python
import asyncio
from evaluations.livekit_conversation_eval import (
    ConversationEvaluator,
    ConversationTestCase,
    ConversationTurn,
    print_report,
    save_report
)

async def run_conv_eval():
    # Define conversation test cases
    test_cases = [
        ConversationTestCase(
            id="conv-1",
            category="context_retention",
            description="Test basic follow-up questions",
            turns=[
                ConversationTurn(
                    query="What is Python?",
                    ground_truth="Python is a high-level programming language.",
                    expected_keywords=["programming", "language"]
                ),
                ConversationTurn(
                    query="What are its main features?",
                    ground_truth="Python features include readability, dynamic typing...",
                    expected_keywords=["readability", "dynamic"],
                    context_check="Should understand 'its' refers to Python"
                ),
                ConversationTurn(
                    query="How does it compare to Java?",
                    ground_truth="Python is dynamically typed while Java is statically typed...",
                    expected_keywords=["typed", "Java"],
                    context_check="Should compare Python (from context) with Java"
                )
            ]
        )
    ]
    
    # Create evaluator
    evaluator = ConversationEvaluator(
        api_url="http://localhost:8000",
        passing_threshold=0.7
    )
    
    # Run evaluation
    report = await evaluator.run_evaluation(
        username="rishikesh",
        persona="default",
        test_cases=test_cases,
        delay_between_turns=2.0,
        delay_between_conversations=5.0
    )
    
    # Print and save
    print_report(report)
    save_report(report, "conv_report.json")
    
    return report

# Run
report = asyncio.run(run_conv_eval())
print(f"Pass rate: {report.passed_count}/{report.total_conversations}")
```

## Conversation Test Categories

Example categories for organizing tests:

| Category | Description |
|----------|-------------|
| `context_retention` | Tests if agent remembers previous context |
| `pronoun_resolution` | Tests if agent resolves "it", "this", "that" correctly |
| `clarification` | Tests handling of "Actually, I meant..." corrections |
| `depth_exploration` | Tests progressive deep-dives into a topic |
| `topic_switching` | Tests context when referencing earlier topics after a switch |

## Conversation Examples

### Basic Context Test
```bash
python -m evaluations.livekit_conversation_eval \
    -u rishikesh \
    -t evaluations/test-cases/conversation_test_cases.json
```

### Strict Multi-Turn Evaluation
```bash
python -m evaluations.livekit_conversation_eval \
    -u rishikesh \
    -t my_conv_tests.json \
    --threshold 0.85 \
    --turn-delay 3.0
```

---

# Part 3: Document Evaluation

For testing document-based Q&A where an S3 file is uploaded and questions are asked about its content.

## Quick Start

```bash
# Run document evaluation
python -m evaluations.livekit_document_eval \
    --username rishikesh \
    --persona default \
    --test-file evaluations/test-cases/document_test_cases.json

# With custom options
python -m evaluations.livekit_document_eval \
    --username rishikesh \
    --persona default \
    --test-file my_documents.json \
    --threshold 0.7 \
    --doc-timeout 180.0 \
    --output results/doc_eval.json
```

## Document Test Case JSON Format

```json
{
  "test_cases": [
    {
      "id": "doc-pdf-report",
      "document_url": "https://your-s3-bucket.s3.amazonaws.com/documents/report.pdf",
      "document_name": "quarterly_report_2025.pdf",
      "document_type": "pdf",
      "category": "business_report",
      "description": "Test Q&A on a quarterly business report",
      "questions": [
        {
          "query": "What is the total revenue mentioned in this report?",
          "ground_truth": "The total revenue for Q4 2025 was $12.5 million.",
          "expected_keywords": ["revenue", "million", "Q4"],
          "requires_specific_section": "Financial Summary"
        },
        {
          "query": "What were the key challenges?",
          "ground_truth": "Supply chain disruptions and increased costs.",
          "expected_keywords": ["supply chain", "costs"]
        }
      ]
    }
  ]
}
```

### Document Test Case Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier for the test case |
| `document_url` | Yes | S3 URL or presigned URL to the document |
| `document_name` | Yes | Filename for display and logging |
| `document_type` | No | File type (pdf, txt, docx) - default: "pdf" |
| `questions` | Yes | Array of questions about the document |
| `category` | No | Category for grouping results |
| `description` | No | Description of what the document tests |

### Question Fields

| Field | Required | Description |
|-------|----------|-------------|
| `query` | Yes | The question to ask about the document |
| `ground_truth` | Yes | Expected correct answer |
| `expected_keywords` | No | Keywords that should appear in response |
| `requires_specific_section` | No | Which section of doc should be referenced |

## Document Evaluation Metrics

### Per-Question Metrics

#### 1. Semantic Similarity (25% weight)
Same as other evaluations - measures meaning match.

#### 2. Factual Accuracy (25% weight)
Same as other evaluations - measures correctness.

#### 3. Keyword Coverage (10% weight)
Same as other evaluations - checks for expected keywords.

#### 4. Document Grounding (40% weight) ⭐ NEW
Evaluates if the response is properly grounded in the uploaded document content.

- **1.0**: Response clearly references and is based on document content
- **0.8**: Well-grounded with minor generic additions
- **0.6**: Partially uses document but adds unsupported information
- **0.4**: Loosely related to document, mostly generic
- **0.2**: Barely references document content
- **0.0**: Appears unrelated to document or hallucinates

### Overall Score

```
overall = (semantic * 0.25) + (factual * 0.25) + (keyword * 0.10) + (grounding * 0.40)
```

Note: Document grounding has the highest weight (40%) since it's most important for document Q&A.

## Document CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--username, -u` | Required | Expert username |
| `--persona, -p` | "default" | Persona name |
| `--test-file, -t` | Required | Path to document test cases JSON |
| `--api-url` | http://localhost:8000 | API base URL |
| `--threshold` | 0.7 | Passing score threshold |
| `--question-delay` | 2.0 | Delay between questions (seconds) |
| `--doc-delay` | 5.0 | Delay between documents (seconds) |
| `--doc-timeout` | 120.0 | Document processing timeout (seconds) |
| `--output, -o` | Auto-generated | Output JSON report path |

## Document Report Structure

```json
{
  "username": "rishikesh",
  "persona": "default",
  "timestamp": "2026-01-07T10:30:00",
  "summary": {
    "total_documents": 5,
    "passed_count": 4,
    "failed_count": 1,
    "pass_rate": 0.8
  },
  "average_scores": {
    "semantic_similarity": 0.82,
    "factual_accuracy": 0.78,
    "keyword_coverage": 0.90,
    "document_grounding": 0.85,
    "overall": 0.83,
    "document_processing_time_ms": 3500
  },
  "category_scores": {
    "business_report": 0.85,
    "technical": 0.80
  },
  "document_type_scores": {
    "pdf": 0.83,
    "txt": 0.80
  },
  "results": [...]
}
```

## Programmatic Usage (Documents)

```python
import asyncio
from evaluations.livekit_document_eval import (
    DocumentEvaluator,
    DocumentTestCase,
    DocumentQuestion,
    print_report,
    save_report
)

async def run_doc_eval():
    # Define document test cases
    test_cases = [
        DocumentTestCase(
            id="doc-1",
            document_url="https://s3.amazonaws.com/bucket/report.pdf",
            document_name="annual_report.pdf",
            document_type="pdf",
            category="business",
            description="Annual report Q&A test",
            questions=[
                DocumentQuestion(
                    query="What was the total revenue?",
                    ground_truth="Total revenue was $50 million.",
                    expected_keywords=["revenue", "million"]
                ),
                DocumentQuestion(
                    query="Who is the CEO?",
                    ground_truth="John Smith is the CEO.",
                    expected_keywords=["CEO", "John"]
                )
            ]
        )
    ]
    
    # Create evaluator
    evaluator = DocumentEvaluator(
        api_url="http://localhost:8000",
        passing_threshold=0.7
    )
    
    # Run evaluation
    report = await evaluator.run_evaluation(
        username="rishikesh",
        persona="default",
        test_cases=test_cases,
        delay_between_questions=2.0,
        delay_between_documents=5.0,
        document_processing_timeout=120.0
    )
    
    # Print and save
    print_report(report)
    save_report(report, "doc_report.json")
    
    return report

# Run
report = asyncio.run(run_doc_eval())
print(f"Pass rate: {report.passed_count}/{report.total_documents}")
```

## Document Test Categories

Example categories for organizing document tests:

| Category | Description |
|----------|-------------|
| `business_report` | Financial reports, quarterly reports |
| `technical` | API docs, specifications, technical guides |
| `legal` | Contracts, agreements, policies |
| `research` | Research papers, studies, whitepapers |
| `meeting_notes` | Meeting minutes, action items |

## Document Examples

### Basic Document Q&A
```bash
python -m evaluations.livekit_document_eval \
    -u rishikesh \
    -t evaluations/test-cases/document_test_cases.json
```

### Large Document with Extended Timeout
```bash
python -m evaluations.livekit_document_eval \
    -u rishikesh \
    -t large_documents.json \
    --doc-timeout 300.0 \
    --question-delay 5.0
```

## Document Flow

1. **Connect** - Fresh connection per document for clean agent state
2. **Upload** - Send document URL via `document` topic
3. **Wait** - Wait for processing confirmation (up to `--doc-timeout`)
4. **Query** - Ask each question and evaluate responses
5. **Score** - Calculate document-level and question-level scores
6. **Report** - Generate comprehensive report

---

# Comparison: All Three Eval Modes

| Aspect | Single Query | Conversation | Document |
|--------|--------------|--------------|----------|
| Module | `livekit_text_agent_eval` | `livekit_conversation_eval` | `livekit_document_eval` |
| Test unit | Questions | Multi-turn convos | Documents with Q&A |
| Input | Question + ground truth | Turns array | S3 URL + questions |
| Max turns | 1 | Up to 3 | Multiple questions |
| Connection | Shared | Fresh per convo | Fresh per document |
| Context metric | ❌ | ✅ Context Retention | ❌ |
| Coherence metric | ❌ | ✅ Conversation Coherence | ❌ |
| Grounding metric | ❌ | ❌ | ✅ Document Grounding |
| Retrieval metric | ✅ | ❌ | ❌ |
| Use case | Fact-checking, Q&A | Chatbot flow | Document analysis |

---

# Part 4: API Endpoints

REST API endpoints for running evaluations programmatically. All endpoints are available under `/api/v1/evaluations/`.

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/evaluations/health` | GET | Health check |
| `/api/v1/evaluations/query` | POST | Run query evaluation (JSON body) |
| `/api/v1/evaluations/query/upload` | POST | Run query evaluation (file upload) |
| `/api/v1/evaluations/conversation` | POST | Run conversation evaluation (JSON body) |
| `/api/v1/evaluations/conversation/upload` | POST | Run conversation evaluation (file upload) |
| `/api/v1/evaluations/document` | POST | Run document evaluation (JSON body) |
| `/api/v1/evaluations/document/upload` | POST | Run document evaluation (file upload) |

## Query Evaluation API

### JSON Body Request
```bash
curl -X POST http://localhost:8000/api/v1/evaluations/query \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "username": "rishikesh",
      "persona": "default",
      "threshold": 0.7
    },
    "test_cases": [
      {
        "id": "test-1",
        "question": "What are your main services?",
        "ground_truth": "I provide consulting, training, and support services.",
        "expected_keywords": ["consulting", "training", "support"]
      }
    ],
    "delay_between_questions": 2.0
  }'
```

### File Upload Request
```bash
curl -X POST http://localhost:8000/api/v1/evaluations/query/upload \
  -F "username=rishikesh" \
  -F "persona=default" \
  -F "threshold=0.7" \
  -F "test_file=@evaluations/test-cases/example_test_cases.json"
```

## Conversation Evaluation API

### JSON Body Request
```bash
curl -X POST http://localhost:8000/api/v1/evaluations/conversation \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "username": "rishikesh",
      "persona": "default",
      "threshold": 0.7
    },
    "test_cases": [
      {
        "id": "conv-1",
        "category": "context_retention",
        "turns": [
          {"query": "What is your name?", "ground_truth": "My name is Rishikesh"},
          {"query": "How do you spell it?", "ground_truth": "R-I-S-H-I-K-E-S-H", "context_check": "name"}
        ]
      }
    ],
    "delay_between_turns": 2.0,
    "delay_between_conversations": 5.0
  }'
```

### File Upload Request
```bash
curl -X POST http://localhost:8000/api/v1/evaluations/conversation/upload \
  -F "username=rishikesh" \
  -F "persona=default" \
  -F "threshold=0.7" \
  -F "turn_delay=2.0" \
  -F "conv_delay=5.0" \
  -F "test_file=@evaluations/test-cases/conversation_test_cases.json"
```

## Document Evaluation API

### JSON Body Request
```bash
curl -X POST http://localhost:8000/api/v1/evaluations/document \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "username": "rishikesh",
      "persona": "default",
      "threshold": 0.7
    },
    "test_cases": [
      {
        "id": "doc-1",
        "document_url": "https://s3.amazonaws.com/bucket/document.pdf",
        "document_name": "report.pdf",
        "document_type": "pdf",
        "questions": [
          {"query": "What is the main topic?", "ground_truth": "The document discusses...", "expected_keywords": ["topic", "main"]}
        ]
      }
    ],
    "delay_between_questions": 2.0,
    "delay_between_documents": 5.0,
    "document_processing_timeout": 120.0
  }'
```

### File Upload Request
```bash
curl -X POST http://localhost:8000/api/v1/evaluations/document/upload \
  -F "username=rishikesh" \
  -F "persona=default" \
  -F "threshold=0.7" \
  -F "question_delay=2.0" \
  -F "doc_delay=5.0" \
  -F "doc_timeout=120.0" \
  -F "test_file=@evaluations/test-cases/document_test_cases.json"
```

## Response Format

All evaluation endpoints return a consistent response structure:

```json
{
  "status": "completed",
  "summary": {
    "total": 5,
    "passed": 4,
    "failed": 1,
    "pass_rate": 0.8,
    "evaluation_errors": 0
  },
  "average_scores": {
    "semantic_similarity": 0.85,
    "factual_accuracy": 0.82,
    "keyword_coverage": 0.75,
    "overall": 0.81,
    "response_time_ms": 1250.5
  },
  "category_scores": {
    "introduction": 0.9,
    "technical": 0.75
  },
  "results": [
    {
      "test_case_id": "test-1",
      "question": "...",
      "ground_truth": "...",
      "agent_response": "...",
      "scores": {
        "semantic_similarity": 0.85,
        "factual_accuracy": 0.9,
        "keyword_coverage": 0.8,
        "overall": 0.86
      },
      "response_time_ms": 1100,
      "passed": true,
      "failure_reason": null,
      "evaluation_error": false
    }
  ],
  "timestamp": "2024-01-15T10:30:00.000000"
}
```

## Config Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | string | required | Expert username |
| `persona` | string | "default" | Persona name |
| `threshold` | float | 0.7 | Passing score threshold (0.0-1.0) |
| `api_url` | string | "http://localhost:8000" | API base URL |

## Python Client Example

```python
import httpx
import asyncio

async def run_query_eval():
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Using file upload
        with open("test_cases.json", "rb") as f:
            response = await client.post(
                "http://localhost:8000/api/v1/evaluations/query/upload",
                data={
                    "username": "rishikesh",
                    "persona": "default",
                    "threshold": "0.7"
                },
                files={"test_file": f}
            )
        
        result = response.json()
        print(f"Pass rate: {result['summary']['pass_rate']:.1%}")
        return result

asyncio.run(run_query_eval())
```

## Error Handling

API returns appropriate HTTP status codes:

| Code | Description |
|------|-------------|
| 200 | Evaluation completed successfully |
| 400 | Invalid request (bad JSON, missing fields) |
| 500 | Server error during evaluation |

Error response format:
```json
{
  "detail": "Error message describing the issue"
}
```
