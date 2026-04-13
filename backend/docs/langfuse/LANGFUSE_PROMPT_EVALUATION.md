# Langfuse Prompt Evaluation Guide

## Overview

This guide explains how to use Langfuse for prompt evaluation in the expert-clone project. Langfuse provides comprehensive observability and evaluation capabilities for LLM applications.

## What is Langfuse?

Langfuse is an open-source LLM engineering platform that provides:
- **Prompt Management**: Version control and management for prompts
- **Evaluation Tracking**: Track evaluation metrics across prompt versions
- **Observability**: Monitor LLM performance and costs
- **A/B Testing**: Compare different prompt versions
- **Debugging**: Detailed traces of LLM calls

## Setup

### 1. Environment Configuration

Add the following environment variables to your `.env` file:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
LANGFUSE_HOST=https://us.cloud.langfuse.com  # Or your self-hosted instance
```

### 2. Verify Installation

Langfuse is already installed in the project via `pyproject.toml`:

```toml
langfuse = "*"  # Langfuse SDK for observability and tracing
```

## Features Implemented

### 1. Automatic Evaluation Tracking

All RAG evaluation endpoints now automatically track results in Langfuse:

#### A. Full RAG Pipeline Evaluation (`/eval-llama-rag`)

Tracks the following metrics for each query:
- **Faithfulness**: How well the answer is grounded in the context
- **Answer Relevancy**: How relevant the answer is to the question
- **Correctness**: Accuracy compared to ground truth
- **Semantic Similarity**: Similarity to expected answer

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/prompt/eval-llama-rag" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "persona_name": "default",
    "queries": [
      {
        "query": "What is your expertise in machine learning?",
        "ground_truth": "I have 10 years of experience in ML and deep learning."
      },
      {
        "query": "What projects have you worked on?",
        "ground_truth": "I worked on computer vision and NLP projects."
      }
    ],
    "params": {
      "top_k": 5,
      "similarity_threshold": 0.3,
      "include_contexts": true
    }
  }'
```

**What Gets Tracked in Langfuse:**
1. **Trace**: Overall evaluation session with metadata
   - Persona ID and name
   - Total queries
   - Evaluation parameters
2. **Spans**: Individual query evaluations with:
   - Question and ground truth
   - Generated answer
   - Retrieved contexts count
   - Processing time
3. **Scores**: Metric values for each query and overall averages

#### B. Retrieval-Only Evaluation (`/eval-llama-retrieval`)

Tracks retrieval-specific metrics:
- **Context Relevancy**: Relevance of retrieved contexts
- **Retrieval Precision**: Precision of the retrieval system

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/prompt/eval-llama-retrieval" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "persona_name": "default",
    "queries": [
      {
        "query": "What are your technical skills?",
        "ground_truth": "Python, TensorFlow, PyTorch, machine learning"
      }
    ],
    "params": {
      "top_k": 5,
      "similarity_threshold": 0.3
    }
  }'
```

### 2. Langfuse Prompt Management API

New endpoints for managing prompts directly in Langfuse:

#### Create a Prompt
```bash
POST /api/v1/langfuse/prompts/create
```

**Example:**
```json
{
  "name": "persona_chat_v1",
  "prompt": "You are {{persona_name}}, an AI assistant specialized in {{expertise}}. Answer questions based on your knowledge and experience.",
  "config": {
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 500
  },
  "labels": ["persona", "chat"],
  "tags": ["production"]
}
```

#### Retrieve a Prompt
```bash
GET /api/v1/langfuse/prompts/get/{prompt_name}?version=1
```

#### Update a Prompt (Creates New Version)
```bash
PUT /api/v1/langfuse/prompts/update/{prompt_name}
```

**Example:**
```json
{
  "prompt": "You are {{persona_name}}, an expert AI assistant...",
  "config": {
    "temperature": 0.8
  }
}
```

## How to Use Langfuse for Prompt Evaluation

### Step 1: Run Evaluations

Execute evaluation endpoints to generate data:

```python
import requests

# Run full RAG evaluation
response = requests.post(
    "http://localhost:8000/api/v1/prompt/eval-llama-rag",
    json={
        "username": "johndoe",
        "queries": [
            {
                "query": "What is your background?",
                "ground_truth": "10 years in ML and AI"
            }
        ]
    }
)

print(response.json())
```

### Step 2: View Results in Langfuse Dashboard

1. **Navigate to Langfuse Dashboard**: https://us.cloud.langfuse.com (or your host)
2. **Select your project**
3. **View Traces**:
   - Filter by tags: `prompt_evaluation`, `llama_rag`, `batch_eval`
   - See detailed query-by-query results
   - View metrics and scores

### Step 3: Analyze Performance

In the Langfuse dashboard you can:

1. **Compare Metrics Over Time**
   - Track faithfulness, relevancy, correctness trends
   - Identify regressions or improvements

2. **Debug Individual Queries**
   - Inspect input (question, contexts)
   - Review generated answers
   - Analyze why scores are low/high

3. **A/B Test Prompts**
   - Create prompt variants in Langfuse
   - Run evaluations with different prompts
   - Compare metrics side-by-side

### Step 4: Iterate on Prompts

Based on evaluation results:

1. **Identify Issues**: Low faithfulness? Poor retrieval?
2. **Modify Prompts**: Update prompt templates
3. **Re-evaluate**: Run evaluations again
4. **Compare**: Use Langfuse to compare versions

## Advanced Usage

### Custom Evaluation Experiments

You can create more sophisticated evaluation workflows:

```python
from langfuse import Langfuse

# Initialize client
langfuse = Langfuse(
    public_key="pk-lf-...",
    secret_key="sk-lf-...",
    host="https://us.cloud.langfuse.com"
)

# Create a dataset for testing
dataset = langfuse.create_dataset(
    name="persona_qa_test",
    description="Standard QA test set for persona evaluation"
)

# Add test cases
dataset.create_dataset_item(
    input={"query": "What is your expertise?"},
    expected_output={"answer": "Machine learning and AI"}
)

# Run experiment (requires Langfuse experiment API)
# results = langfuse.run_experiment(
#     dataset_name="persona_qa_test",
#     eval_function=my_eval_function
# )
```

### Tracking Custom Metrics

Add custom scores to your traces:

```python
# In your application code
trace = langfuse_client.trace(
    name="custom_evaluation",
    user_id="test_user"
)

# Add custom score
langfuse_client.score(
    trace_id=trace.id,
    name="custom_metric",
    value=0.85,
    comment="Custom evaluation result"
)
```

## Monitoring and Alerts

### Set Up Monitoring

1. **Create Dashboards**: Build custom dashboards in Langfuse
2. **Track KPIs**: Monitor key metrics (avg faithfulness, costs, latency)
3. **Set Alerts**: Configure alerts for metric thresholds (if supported)

### Best Practices

1. **Tag Consistently**: Use tags to organize traces
   - `environment`: `dev`, `staging`, `production`
   - `feature`: `rag`, `chat`, `evaluation`
   - `version`: `v1.0`, `v1.1`, etc.

2. **Include Metadata**: Add context to traces
   - Persona ID
   - User ID
   - Evaluation parameters

3. **Regular Evaluations**: Run evaluations regularly
   - After prompt changes
   - After data ingestion
   - Weekly/monthly benchmarks

4. **Version Prompts**: Use Langfuse prompt versioning
   - Store prompts centrally
   - Track which version is in production
   - Roll back if needed

## Troubleshooting

### No Data in Langfuse

**Issue**: Evaluation runs but no data appears in Langfuse.

**Solutions**:
1. **Check Credentials**: Verify `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
2. **Check Logs**: Look for Langfuse errors in application logs
3. **Flush Data**: Ensure `langfuse_client.flush()` is called
4. **Network**: Verify connectivity to Langfuse host

### Authentication Errors

```
Authentication error: Langfuse client initialized without public_key
```

**Solution**: Set environment variables:
```bash
export LANGFUSE_PUBLIC_KEY=pk-lf-your-key
export LANGFUSE_SECRET_KEY=sk-lf-your-secret
```

### Import Errors

```
ImportError: No module named 'langfuse'
```

**Solution**: Install Langfuse:
```bash
poetry install  # Installs all dependencies including langfuse
```

## Example: Complete Evaluation Workflow

```python
import asyncio
import requests

async def run_evaluation_workflow():
    # 1. Run baseline evaluation
    print("Running baseline evaluation...")
    baseline = requests.post(
        "http://localhost:8000/api/v1/prompt/eval-llama-rag",
        json={
            "username": "test_user",
            "queries": [
                {"query": "What is your background?", "ground_truth": "ML expert"},
                {"query": "What skills do you have?", "ground_truth": "Python, TensorFlow"}
            ]
        }
    )
    
    baseline_metrics = baseline.json()["metrics_overall"]
    print(f"Baseline Metrics: {baseline_metrics}")
    
    # 2. Update prompt in database
    # (Modify PersonaPrompt via admin interface or API)
    
    # 3. Run new evaluation
    print("\nRunning updated evaluation...")
    updated = requests.post(
        "http://localhost:8000/api/v1/prompt/eval-llama-rag",
        json={
            "username": "test_user",
            "queries": [
                {"query": "What is your background?", "ground_truth": "ML expert"},
                {"query": "What skills do you have?", "ground_truth": "Python, TensorFlow"}
            ]
        }
    )
    
    updated_metrics = updated.json()["metrics_overall"]
    print(f"Updated Metrics: {updated_metrics}")
    
    # 4. Compare results
    print("\nMetric Comparison:")
    for metric in baseline_metrics:
        baseline_val = baseline_metrics[metric]
        updated_val = updated_metrics[metric]
        change = updated_val - baseline_val
        print(f"  {metric}: {baseline_val:.3f} -> {updated_val:.3f} ({change:+.3f})")
    
    # 5. Check Langfuse dashboard for detailed analysis
    print("\nView detailed traces in Langfuse dashboard:")
    print("https://us.cloud.langfuse.com/")

if __name__ == "__main__":
    asyncio.run(run_evaluation_workflow())
```

## Integration with CI/CD

Add evaluation checks to your CI pipeline:

```yaml
# .github/workflows/evaluation.yml
name: Prompt Evaluation

on:
  pull_request:
    paths:
      - 'app/prompts/**'
      - 'shared/rag/**'

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: poetry install
      
      - name: Run evaluations
        env:
          LANGFUSE_PUBLIC_KEY: ${{ secrets.LANGFUSE_PUBLIC_KEY }}
          LANGFUSE_SECRET_KEY: ${{ secrets.LANGFUSE_SECRET_KEY }}
        run: |
          python scripts/run_evaluations.py
      
      - name: Check metrics
        run: |
          # Fail if metrics drop below threshold
          python scripts/check_metrics.py --min-faithfulness 0.7
```

## Resources

- **Langfuse Documentation**: https://langfuse.com/docs
- **Python SDK**: https://langfuse.com/docs/sdk/python
- **Evaluation Guide**: https://langfuse.com/docs/scores/model-based-evals
- **Prompt Management**: https://langfuse.com/docs/prompts

## Support

For issues or questions:
1. Check application logs for Langfuse errors
2. Review Langfuse documentation
3. Contact the development team

