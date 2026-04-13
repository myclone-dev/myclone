# 🔌 Digital Clone POC - API Documentation

## Overview

This documentation covers all API endpoints for the Digital Clone POC system, including streaming capabilities with LlamaIndex and Letta Cloud memory integration.

## Related Documentation

- **[LiveKit Agent System](./livekit-agent-workflow/)** - Voice chat agent architecture and implementation details
- **[Architecture Overview](./architecture/ARCHITECTURE.md)** - System architecture and data flow
- **[Voice Processing](./voice-processing/)** - Voice extraction and processing documentation

## Base URL
```
http://localhost:8000/api/v1
```

## 🔐 **Authentication**

The Expert Clone API supports API key authentication for secure service-to-service communication.

### API Key Configuration
Set the following environment variables:
```bash
# Required: Your API key for authentication
EXPERT_CLONE_API_KEY=your_secure_api_key_here

# Optional: Enable/disable API key requirement (default: false)
EXPERT_CLONE_REQUIRE_API_KEY=true
```

### Using API Keys
Include your API key in requests using one of these methods:

**Method 1: Authorization Header (Recommended)**
```bash
curl -H "Authorization: Bearer your_api_key_here" \
     -X GET http://localhost:8000/api/v1/expert/johndoe
```

**Method 2: X-API-Key Header**
```bash
curl -H "X-API-Key: your_api_key_here" \
     -X GET http://localhost:8000/api/v1/expert/johndoe
```

**Method 3: Query Parameter (Development Only)**
```bash
curl "http://localhost:8000/api/v1/expert/johndoe?api_key=your_api_key_here"
```

### Protected Endpoints
The following endpoints require API key authentication when `EXPERT_CLONE_REQUIRE_API_KEY=true`:
- `GET /api/v1/expert/{username}` - Expert lookup
- `POST /api/v1/ingestion/create-persona-with-data` - Create persona with data  
- `POST /api/v1/ingestion/process-raw-data` - Process raw data

### Go Backend Integration
```go
type ExpertCloneConfig struct {
    BaseURL    string `env:"EXPERT_CLONE_SERVICE_URL"`
    APIKey     string `env:"EXPERT_CLONE_API_KEY"`
    Enabled    bool   `env:"EXPERT_CLONE_ENABLED,default=true"`
    TimeoutSec int    `env:"EXPERT_CLONE_TIMEOUT_SEC,default=30"`
}

func (c *ExpertCloneConfig) makeRequest(endpoint string, body io.Reader) (*http.Response, error) {
    req, err := http.NewRequest("POST", c.BaseURL+endpoint, body)
    if err != nil {
        return nil, err
    }
    
    // Add API key authentication
    req.Header.Set("Authorization", "Bearer "+c.APIKey)
    req.Header.Set("Content-Type", "application/json")
    
    client := &http.Client{Timeout: time.Duration(c.TimeoutSec) * time.Second}
    return client.Do(req)
}
```

### Authentication Management Endpoints

#### Get API Key Info
```http
GET /auth/info
```

**Response:**
```json
{
  "is_configured": true,
  "is_required": true,
  "validation_endpoints": [
    "/api/v1/expert/{username}",
    "/api/v1/ingestion/create-persona-with-data",
    "/api/v1/ingestion/process-raw-data"
  ]
}
```

#### Generate API Key (Development)
```http
POST /auth/generate-key
```

**Response:**
```json
{
  "api_key": "ec_AbC123XyZ789...",
  "message": "API key generated successfully. Store this securely - it cannot be retrieved again.",
  "expires_at": null
}
```

#### Validate API Key
```http
POST /auth/validate-key
```

**Request Body:**
```json
{
  "api_key": "ec_your_api_key_here"
}
```

**Response:**
```json
{
  "valid": true,
  "message": "API key is valid"
}
```

## Authentication
Currently using API keys for external services. Set in environment variables:
- `OPENAI_API_KEY` - Required for embeddings and LLM
- `EXA_API_KEY` - Optional for web enrichment

## 📊 Core API Endpoints

### Personas Management

#### Create Persona
```http
POST /personas
```

**Request Body:**
```json
{
  "name": "John Doe",
  "role": "Software Engineer",
  "company": "Tech Corp",
  "description": "Experienced AI/ML engineer"
}
```

**Response:**
```json
{
  "id": "uuid-here",
  "name": "John Doe",
  "role": "Software Engineer",
  "company": "Tech Corp",
  "description": "Experienced AI/ML engineer",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### List Personas
```http
GET /personas
```

#### Get Persona
```http
GET /personas/{persona_id}
```

#### Update Persona
```http
PUT /personas/{persona_id}
```

#### Delete Persona
```http
DELETE /personas/{persona_id}
```

### Chat with Personas

#### Regular Chat
```http
POST /personas/{persona_id}/chat
```

**Request Body:**
```json
{
  "message": "How do you approach machine learning problems?"
}
```

**Response:**
```json
{
  "response": "I typically start by understanding the problem domain...",
  "persona_id": "uuid-here",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🚀 **NEW: Streaming API Endpoints**

### Streaming Query (Real-time Response)
```http
POST /personas/{persona_id}/stream-query
```

**Request Body:**
```json
{
  "query": "What's your approach to system architecture?",
  "include_patterns": true,
  "similarity_top_k": 5,
  "use_memory": true
}
```

**Response:** Server-Sent Events (SSE)
```
data: {"chunk": "I typically", "type": "content"}

data: {"chunk": " approach system", "type": "content"}

data: {"chunk": " architecture by...", "type": "content"}

data: {"type": "complete"}
```

**JavaScript Client:**
```javascript
const eventSource = new EventSource('/api/v1/personas/uuid/stream-query');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  if (data.type === 'content') {
    console.log('Chunk:', data.chunk);
    // Append to UI
  } else if (data.type === 'complete') {
    console.log('Stream complete');
    eventSource.close();
  }
};
```

### Streaming Chat (Conversation Context) - Updated with User Email
```http
POST /personas/{persona_id}/stream-chat
```

**Request Body:**
```json
{
  "message": "Can you explain your previous point in more detail?",
  "user_email": "user@example.com",
  "session_id": "optional-session-id",
  "chat_history": [
    {
      "role": "user",
      "content": "How do you handle microservices?"
    },
    {
      "role": "assistant", 
      "content": "I prefer a domain-driven approach..."
    }
  ],
  "similarity_top_k": 5,
  "use_memory": true
}
```

**Response:** Server-Sent Events (SSE)
```
data: {"chunk": "I can elaborate", "type": "content", "session_id": "session_abc123"}

data: {"chunk": " on that approach...", "type": "content", "session_id": "session_abc123"}

data: {"type": "complete", "session_id": "session_abc123"}
```

### Get Conversation History
```http
GET /personas/{persona_id}/conversation-history?limit=50
```

**Response:**
```json
{
  "persona_id": "uuid-here",
  "conversation_history": [
    {
      "role": "user",
      "content": "How do you handle microservices?",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "role": "assistant",
      "content": "I prefer a domain-driven approach...",
      "timestamp": "2024-01-15T10:30:15Z"
    }
  ],
  "total_messages": 45
}
```

### Cleanup Memory Agent
```http
DELETE /personas/{persona_id}/memory
```

**Response:**
```json
{
  "success": true,
  "message": "Memory agent cleanup completed"
}
```

## 🎯 **NEW: Expert Lookup by Username**

### Get Expert by Username
```http
GET /expert/{username}
```

**Description:** Get persona information by username for `/expert/{username}` routing. This endpoint is designed for your Go backend to lookup experts by their unique username.

**Path Parameters:**
- `username` (string): The unique username of the expert

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "johndoe",
  "name": "John Doe", 
  "role": "Software Engineer",
  "company": "Tech Corp",
  "description": "Senior developer with expertise in Python and AI",
  "created_at": "2025-08-27T14:00:00.000Z",
  "updated_at": "2025-08-27T14:00:00.000Z"
}
```

**Error Responses:**
```json
// 404 Not Found
{
  "detail": "Expert 'johndoe' not found"
}
```

**Integration Example for Go Backend:**
```go
// When user visits /expert/{username}
func getExpertHandler(w http.ResponseWriter, r *http.Request) {
    username := mux.Vars(r)["username"]
    
    // Call Python service to get expert data
    expertData, err := pythonService.GetExpertByUsername(username)
    if err != nil {
        // Handle expert not found
        http.Error(w, "Expert not found", 404)
        return
    }
    
    // Render expert profile page with expertData
    renderExpertProfile(w, expertData)
}
```

## 📡 **NEW: Data Ingestion & Persona Creation**

### 🎯 Create Persona with Data (One-Call Solution)
```http
POST /ingestion/create-persona-with-data
```

**Description:** Creates a new persona and processes all associated data in a single call. Returns the persona ID and processing results.

**Request Body:**
```json
{
  "persona_info": {
    "username": "johndoe", 
    "name": "John Doe",
    "role": "Software Engineer",
    "company": "Tech Corp",
    "description": "Senior developer with expertise in Python and AI"
  },
  "user_id": "creator123",
  "linkedin_data": {
    "name": "John Doe",
    "headline": "Senior Software Engineer at Tech Corp",
    "about": "Passionate about AI and machine learning with 10+ years experience...",
    "experience": [
      {
        "title": "Senior Software Engineer",
        "company": "Tech Corp",
        "duration": "2021-present",
        "description": "Leading AI initiatives and ML pipeline development..."
      }
    ],
    "education": [
      {
        "school": "MIT",
        "degree": "BS Computer Science"
      }
    ],
    "skills": ["Python", "Machine Learning", "FastAPI", "Docker"],
    "posts": [
      {
        "content": "Just launched our new AI model with 95% accuracy..."
      }
    ]
  },
  "website_data": {
    "title": "John Doe - Personal Website",
    "description": "Software engineer and AI researcher",
    "content": "Welcome to my website. I share insights about AI, ML, and software engineering...",
    "about_content": "I'm a passionate software engineer with expertise in building scalable AI systems...",
    "blog_posts": [
      {
        "title": "Building Scalable AI Systems",
        "content": "In this post I'll discuss the key principles for designing robust AI architectures..."
      }
    ]
  },
  "transcript_data": {
    "content": "Interviewer: Tell me about your background\nJohn: I've been working in tech for 10 years, specializing in AI and machine learning..."
  }
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "John Doe",
  "role": "Software Engineer",
  "company": "Tech Corp",
  "description": "Senior developer with expertise in Python and AI",
  "communication_style": null,
  "created_at": "2025-08-27T14:00:00.000Z",
  "updated_at": "2025-08-27T14:00:00.000Z",
  "processing_info": {
    "persona_id": "550e8400-e29b-41d4-a716-446655440000",
    "sources_processed": ["linkedin", "website", "transcript"],
    "content_chunks_created": 15,
    "patterns_extracted": {
      "communication_style": {
        "formality_score": 0.72,
        "avg_sentence_length": 18.5,
        "common_phrases": ["in my experience", "I typically approach"]
      },
      "thinking_patterns": {
        "approach": "systematic",
        "evidence_usage": "data-driven"
      }
    },
    "errors": []
  }
}
```

### Process Raw Data for Existing Persona
```http
POST /ingestion/process-raw-data
```

**Description:** Processes raw data for an existing persona.

**Request Body:**
```json
{
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user123",
  "linkedin_data": {...},
  "website_data": {...},
  "transcript_data": {...}
}
```

**Response:**
```json
{
  "success": true,
  "message": "Data processed successfully",
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "sources_processed": ["linkedin", "website", "transcript"],
  "content_chunks_created": 12,
  "patterns_extracted": {...},
  "errors": []
}
```

### Get Persona Data Sources
```http
GET /ingestion/persona/{persona_id}/data-sources
```

**Response:**
```json
{
  "persona_id": "550e8400-e29b-41d4-a716-446655440000",
  "data_sources": [
    {
      "id": "uuid",
      "source_type": "linkedin",
      "processed": true,
      "created_at": "2025-08-27T14:00:00.000Z",
      "processed_at": "2025-08-27T14:05:00.000Z"
    }
  ]
}
```

## 📡 External Data Ingestion

### Ingest External Data
```http
POST /external-data/ingest
```

**Request Body (LinkedIn Example):**
```json
{
  "persona_id": "uuid-here",
  "data_type": "linkedin",
  "linkedin_data": {
    "name": "John Doe",
    "headline": "Senior Software Engineer",
    "about": "Passionate about AI/ML systems...",
    "experience": [
      {
        "company": "TechCorp",
        "title": "Senior Engineer",
        "description": "Led development of ML pipelines..."
      }
    ],
    "skills": ["Python", "Machine Learning", "Docker"],
    "posts": [
      {
        "text": "Just deployed a new RAG system...",
        "date": "2024-01-15"
      }
    ]
  },
  "process_immediately": true
}
```

**Request Body (Custom Data Example):**
```json
{
  "persona_id": "uuid-here",
  "data_type": "custom",
  "custom_data": {
    "source_name": "blog_posts",
    "content_type": "articles",
    "data": {
      "articles": [
        {
          "title": "Building Scalable AI Systems",
          "content": "In this article, I'll discuss...",
          "date": "2024-01-10"
        }
      ]
    }
  },
  "process_immediately": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Data from linkedin successfully ingested",
  "data_id": "uuid-here",
  "persona_id": "uuid-here",
  "processing_status": "completed"
}
```

### Get External Data Status
```http
GET /external-data/{persona_id}/status
```

**Response:**
```json
{
  "persona_id": "uuid-here",
  "total_sources": 3,
  "processed": 2,
  "pending": 1,
  "sources": [
    {
      "id": "uuid-here",
      "source_type": "linkedin",
      "processed": true,
      "created_at": "2024-01-15T10:00:00Z",
      "processed_at": "2024-01-15T10:05:00Z"
    }
  ]
}
```

## 📊 Pattern Analysis

### Get Persona Patterns
```http
GET /personas/{persona_id}/patterns
```

**Response:**
```json
{
  "persona_id": "uuid-here",
  "patterns": {
    "communication_style": {
      "avg_sentence_length": 18.5,
      "vocabulary_complexity": 0.73,
      "formality_score": 0.68,
      "common_phrases": ["let me explain", "in my experience"]
    },
    "thinking_patterns": {
      "approach": "top-down",
      "evidence_usage": "data-driven",
      "reasoning_style": "deductive"
    }
  }
}
```

## 🔄 **NEW: Enhanced Session Tracking with Email Prompting**

### Initialize Anonymous Session
```http
POST /personas/username/{username}/init-session
```

**Description:** Initialize an anonymous session for a persona. Creates a temporary session that can later be converted to an identified session when user provides email.

**Response:**
```json
{
  "session_token": "550e8400-e29b-41d4-a716-446655440000",
  "persona_id": "persona-uuid-456",
  "username": "johndoe",
  "is_anonymous": true
}
```

### Stream Chat with Session Tracking
```http
POST /personas/username/{username}/stream-chat
```

**Description:** Stream chat with automatic session tracking and email prompting after 3 messages.

**Request Body:**
```json
{
  "message": "Hello, I have a question about your experience",
  "session_token": "550e8400-e29b-41d4-a716-446655440000",
  "context_window": 5,
  "temperature": 0.7
}
```

**Response:** Server-Sent Events (SSE)
```
data: {"type": "content", "chunk": "Thank you for your message! "}

data: {"type": "content", "chunk": "I understand you're asking about..."}

# After 3rd message, email prompt is automatically triggered
data: {"type": "email_prompt", "message": "💌 Want to save your conversation? Provide your email to continue later!", "message_count": 3}

data: {"type": "complete", "session_token": "550e8400-e29b-41d4-a716-446655440000"}
```

### Provide Email (Convert Anonymous Session)
```http
POST /sessions/{session_token}/provide-email
```

**Description:** Convert anonymous session to identified session and merge any previous conversations.

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "email": "user@example.com",
  "previous_conversations": true,
  "merged_sessions": 2
}
```

### Get Session Status
```http
GET /sessions/{session_token}/status
```

**Description:** Get current session status and tracking information.

**Response:**
```json
{
  "session_token": "550e8400-e29b-41d4-a716-446655440000",
  "user_email": "user@example.com",
  "persona_id": "persona-uuid-456",
  "is_active": true,
  "is_valid": true,
  "is_anonymous": false,
  "message_count": 5,
  "email_prompted": true,
  "email_provided": true,
  "created_at": "2025-08-27T14:00:00.000Z",
  "last_accessed": "2025-08-27T14:30:00.000Z",
  "expires_at": "2025-09-03T14:00:00.000Z"
}
```

### Integration Flow for Frontend
```javascript
// 1. Initialize session when user visits expert page
const initSession = async (username) => {
  const response = await fetch(`/api/v1/personas/username/${username}/init-session`, {
    method: 'POST'
  });
  const sessionData = await response.json();
  localStorage.setItem('session_token', sessionData.session_token);
  return sessionData;
};

// 2. Send messages with session tracking
const sendMessage = async (username, message) => {
  const sessionToken = localStorage.getItem('session_token');
  
  const eventSource = new EventSource('/api/v1/personas/username/' + username + '/stream-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: message,
      session_token: sessionToken
    })
  });
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'email_prompt') {
      // Show email collection modal
      showEmailPrompt(data.message, data.message_count);
    } else if (data.type === 'content') {
      // Display chat content
      appendToChatUI(data.chunk);
    }
  };
};

// 3. Handle email provision
const provideEmail = async (email) => {
  const sessionToken = localStorage.getItem('session_token');
  
  const response = await fetch(`/api/v1/sessions/${sessionToken}/provide-email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email })
  });
  
  const result = await response.json();
  if (result.previous_conversations) {
    // Notify user about merged conversations
    showMergeNotification(result.merged_sessions);
  }
};
```

## 👤 **NEW: User Management Endpoints**

### Get User Conversations
```http
GET /users/{user_email}/conversations?persona_id={uuid}&limit=10&offset=0
```

**Description:** Get all conversations for a specific user by email, with optional persona filtering.

**Query Parameters:**
- `persona_id` (optional): Filter conversations by specific persona
- `limit` (optional): Number of conversations to return (1-100, default: 10)
- `offset` (optional): Offset for pagination (default: 0)

**Response:**
```json
{
  "user_email": "user@example.com",
  "conversations": [
    {
      "id": "conv-uuid-123",
      "persona_id": "persona-uuid-456", 
      "session_id": "session_abc123",
      "user_email": "user@example.com",
      "messages": [
        {
          "role": "user",
          "content": "How do you approach system design?",
          "timestamp": "2025-08-27T14:00:00.000Z"
        },
        {
          "role": "assistant",
          "content": "I typically start by understanding the requirements...",
          "timestamp": "2025-08-27T14:00:15.000Z"
        }
      ],
      "metadata": {
        "user_email": "user@example.com",
        "similarity_top_k": 5,
        "use_memory": true
      },
      "extracted_fields": {
        "contact_name": {"value": "Sarah Michelle", "confidence": 1.0},
        "contact_email": {"value": "sarah@mitchell.com", "confidence": 1.0},
        "client_type": {"value": "Individual - Tax Planning", "confidence": 1.0}
      },
      "result_data": {
        "lead_score": 85,
        "lead_quality": "hot",
        "priority_level": "high",
        "lead_summary": {
          "contact": {"name": "Sarah Michelle", "email": "sarah@mitchell.com"},
          "service_need": "Tax Planning and Return Filing",
          "follow_up_questions": ["What specific outcomes are you hoping to achieve?"]
        }
      },
      "created_at": "2025-08-27T14:00:00.000Z",
      "updated_at": "2025-08-27T14:00:15.000Z"
    }
  ],
  "total_returned": 1,
  "offset": 0,
  "limit": 10
}
```

**Workflow Fields:**
- `extracted_fields` (nullable): Lead capture data extracted during conversational workflow. Each field contains `value`, `confidence`, `extraction_method`, and `extracted_at`. Only present when a workflow was active during the conversation.
- `result_data` (nullable): Workflow completion data including lead scoring (`lead_score`, `lead_quality`, `priority_level`), lead summary with contact info and follow-up questions. Only present when the workflow completed and was evaluated.

### Get User Sessions
```http
GET /users/{user_email}/sessions?active_only=true
```

**Query Parameters:**
- `active_only` (optional): Return only active sessions (default: true)

**Response:**
```json
{
  "user_email": "user@example.com",
  "sessions": [
    {
      "id": "session-uuid-789",
      "session_token": "session_abc123",
      "persona_id": "persona-uuid-456",
      "created_at": "2025-08-27T14:00:00.000Z",
      "last_accessed": "2025-08-27T14:30:00.000Z",
      "expires_at": "2025-09-03T14:00:00.000Z",
      "is_active": true,
      "is_expired": false,
      "is_valid": true,
      "metadata": {}
    }
  ],
  "total_sessions": 1,
  "active_sessions": 1
}
```

### Get User's Personas
```http
GET /users/{user_email}/personas
```

**Description:** Get all personas that a user has had conversations with.

**Response:**
```json
{
  "user_email": "user@example.com",
  "personas": [
    {
      "id": "persona-uuid-456",
      "name": "John Doe",
      "role": "Software Engineer",
      "company": "Tech Corp",
      "description": "Senior developer with AI expertise",
      "created_at": "2025-08-27T12:00:00.000Z",
      "conversation_count": 5
    }
  ],
  "total_personas": 1
}
```

### Get User Statistics
```http
GET /users/{user_email}/stats
```

**Description:** Get comprehensive user activity statistics.

**Response:**
```json
{
  "user_email": "user@example.com",
  "stats": {
    "total_conversations": 25,
    "active_sessions": 2,
    "recent_conversations_7_days": 8,
    "unique_personas_interacted": 4,
    "last_activity": "2025-08-27T14:30:00.000Z"
  }
}
```

### Deactivate User Session
```http
DELETE /users/{user_email}/sessions/{session_id}
```

**Description:** Deactivate a specific user session.

**Response:**
```json
{
  "message": "Session deactivated successfully",
  "session_id": "session_abc123",
  "user_email": "user@example.com"
}
```

## 📈 System Health

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy"
}
```

### API Root
```http
GET /api
```

**Response:**
```json
{
  "message": "Digital Persona System API",
  "version": "1.0.0",
  "docs": "/docs"
}
```

## 🔧 Error Responses

### Standard Error Format
```json
{
  "detail": "Error message here",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common HTTP Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

## 📝 Usage Examples

### Complete Streaming Chat Implementation

**Python Client:**
```python
import requests
import json
import sseclient

def stream_chat(persona_id, message, api_base_url):
    url = f"{api_base_url}/personas/{persona_id}/stream-chat"
    
    payload = {
        "message": message,
        "use_memory": True
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
    }
    
    response = requests.post(url, json=payload, headers=headers, stream=True)
    client = sseclient.SSEClient(response)
    
    full_response = ""
    for event in client.events():
        data = json.loads(event.data)
        
        if data.get('type') == 'content':
            chunk = data.get('chunk', '')
            full_response += chunk
            print(chunk, end='', flush=True)
        elif data.get('type') == 'complete':
            break
        elif data.get('type') == 'error':
            print(f"Error: {data.get('error')}")
            break
    
    return full_response

# Usage
response = stream_chat("uuid-here", "How do you approach system design?", "http://localhost:8000/api/v1")
```

**JavaScript/React Client:**
```javascript
const streamChat = async (personaId, message) => {
  const response = await fetch(`/api/v1/personas/${personaId}/stream-chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: message,
      use_memory: true
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let fullResponse = '';

  while (true) {
    const { done, value } = await reader.read();
    
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          
          if (data.type === 'content') {
            fullResponse += data.chunk;
            // Update UI with chunk
            updateChatUI(data.chunk);
          } else if (data.type === 'complete') {
            console.log('Stream complete');
            return fullResponse;
          }
        } catch (e) {
          // Skip invalid JSON
        }
      }
    }
  }
  
  return fullResponse;
};
```

## 🚀 Getting Started

1. **Start Streaming Chat:**
```bash
curl -X POST http://localhost:8000/api/v1/personas/{uuid}/stream-chat \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"message": "Hello! Tell me about yourself.", "use_memory": true}'
```

## 📚 Additional Resources

- **Interactive API Docs**: http://localhost:8000/docs
- **LlamaIndex Streaming**: https://docs.llamaindex.ai/en/stable/module_guides/deploying/query_engine/streaming/
- **Server-Sent Events**: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events

---
*Last Updated: December 2024*