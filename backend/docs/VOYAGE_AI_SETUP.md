# Voyage AI Setup Guide

## Overview

Voyage AI provides high-quality embedding models optimized for retrieval tasks. The embedding migration endpoints allow you to migrate between OpenAI and Voyage AI embeddings.

## Getting Your Voyage AI API Key

1. **Sign up for Voyage AI**
   - Visit: https://www.voyageai.com/
   - Click "Sign Up" or "Get Started"
   - Create an account or sign in with GitHub/Google

2. **Access the Dashboard**
   - After signing in, navigate to: https://dash.voyageai.com/
   - Go to the "API Keys" section

3. **Create an API Key**
   - Click "Create New API Key"
   - Give it a descriptive name (e.g., "Expert Clone Production")
   - Copy the generated API key (it starts with `pa-` or similar prefix)

## Configuration

### Local Development (.env file)

1. Open `/home/rishikesh/dev/rappo/expert-clone/.env`

2. Find the line with `VOYAGE_API_KEY`:
   ```bash
   VOYAGE_API_KEY=YOUR_VOYAGE_API_KEY_HERE
   ```

3. Replace `YOUR_VOYAGE_API_KEY_HERE` with your actual API key:
   ```bash
   VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

4. (Optional) Set the embedding provider to use Voyage AI:
   ```bash
   EMBEDDING_PROVIDER=voyage
   ```

### Restart Your Application

After updating the `.env` file, restart your application:
```bash
# If running locally
make restart

# Or manually restart the server
pkill -f "uvicorn" && python run_server.py
```

## Using the Migration Endpoints

Once configured, you can use the embedding migration endpoints:

### Check Embedding Statistics
```bash
curl -X GET http://localhost:8000/api/v1/embeddings/stats \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Migrate from OpenAI to Voyage AI
```bash
curl -X POST http://localhost:8000/api/v1/embeddings/migrate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "source_provider": "openai",
    "target_provider": "voyage"
  }'
```

### Migrate Specific User
```bash
curl -X POST http://localhost:8000/api/v1/embeddings/migrate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "source_provider": "openai",
    "target_provider": "voyage",
    "user_id": "your-user-uuid"
  }'
```

### Migrate Specific Persona
```bash
curl -X POST http://localhost:8000/api/v1/embeddings/migrate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "source_provider": "openai",
    "target_provider": "voyage",
    "persona_id": "your-persona-uuid"
  }'
```

## Embedding Models

### OpenAI (text-embedding-3-small)
- **Dimensions**: 1536
- **Table**: `data_llamaindex_embeddings`
- **Cost**: $0.02 per 1M tokens
- **Best for**: General-purpose embeddings

### Voyage AI (voyage-3.5-lite)
- **Dimensions**: 512
- **Table**: `data_llamalite_embeddings`
- **Cost**: $0.02 per 1M tokens
- **Best for**: Retrieval tasks, optimized for RAG

## Switching Between Providers

To switch the default embedding provider for new data:

1. Update `.env`:
   ```bash
   # For OpenAI
   EMBEDDING_PROVIDER=openai
   VECTOR_DIMENSION=1536

   # For Voyage AI
   EMBEDDING_PROVIDER=voyage
   VECTOR_DIMENSION=512
   ```

2. Restart the application

3. (Optional) Migrate existing embeddings using the migration endpoint

## Troubleshooting

### Error: "VOYAGE_API_KEY not configured"

**Solution**: Make sure you've added your API key to the `.env` file and restarted the application.

### Error: "Invalid API key"

**Solution**: Verify your API key is correct:
1. Check for extra spaces or quotes in the `.env` file
2. Ensure the API key hasn't expired
3. Generate a new API key from the Voyage AI dashboard

### Migration takes too long

**Solution**: 
- Migrations run in the background
- Check logs for progress: `tail -f logs/api.log`
- Use `user_id` or `persona_id` filters to migrate smaller batches

## Production Deployment

For production (AWS ECS), configure the API key in AWS Secrets Manager:

1. Create or update the secret for your service
2. Add the `VOYAGE_API_KEY` field
3. Redeploy your ECS service

## API Rate Limits

Voyage AI has the following rate limits (as of 2024):
- **Free tier**: 100 requests/minute
- **Paid tier**: Higher limits based on your plan

If you hit rate limits during migration, the endpoint will automatically retry with exponential backoff.

## Support

- **Voyage AI Docs**: https://docs.voyageai.com/
- **API Reference**: https://docs.voyageai.com/reference/
- **Support**: support@voyageai.com

