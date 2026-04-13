# Suggested Questions Feature - Complete Guide

## Overview

AI-powered persona-specific suggested questions feature that generates contextually relevant starter questions for the chat UI to improve user engagement and onboarding experience.

---

## Architecture

### High-Level Flow

```
Persona Creation
    ↓
PersonaPrompt Created (with all configuration fields)
    ↓
Generate Suggested Questions (POST /personas/{id}/suggested-questions)
    ↓
LLM analyzes all prompt fields → generates 5 questions
    ↓
Store in personas.suggested_questions (JSONB)
    ↓
Frontend fetches persona (GET /expert/{username}/public)
    ↓
Display questions as clickable buttons in chat UI
```

### Data Flow

```
Input: PersonaPrompt fields (8 fields)
    - introduction
    - area_of_expertise
    - chat_objective
    - objective_response
    - thinking_style
    - target_audience
    - response_structure
    - role & company

Processing: OpenAI LLM
    - Temperature mapped from creativity setting
    - Contextual prompt with all persona data
    - JSON output parsing

Output: Suggested Questions
    - 1-10 questions (default: 5)
    - Stored in personas.suggested_questions (JSONB)
    - Cached for fast retrieval

Retrieval: Public Persona Endpoint
    - Single API call includes questions
    - No extra request needed
```

---

## Database Schema

### Migration

**File**: `alembic/versions/2dd8da251a96_add_suggested_questions_to_personas.py`

```sql
-- Add JSONB column
ALTER TABLE personas
ADD COLUMN suggested_questions JSONB;

-- Add GIN index for fast queries
CREATE INDEX idx_personas_suggested_questions
ON personas USING gin(suggested_questions);

-- Add column comment
COMMENT ON COLUMN personas.suggested_questions IS
'Persona-specific suggested starter questions for chat UI.
Format: {"questions": ["Q1?", "Q2?"], "generated_at": "ISO timestamp"}';
```

### Data Structure

```json
{
  "questions": [
    "How did you get started in machine learning?",
    "What's the most common mistake beginners make in ML?",
    "Can you explain neural networks in simple terms?",
    "What's your favorite ML project you've worked on?",
    "How do you approach debugging ML models?"
  ],
  "generated_at": "2025-10-31T17:30:00.000Z",
  "response_settings": {
    "response_length": "explanatory",
    "creativity": "adaptive"
  }
}
```

### Storage Decision

**Chose `personas` table (NOT `persona_prompts`)**

**Reasoning**:

| Aspect | personas ✅ | persona_prompts ❌ |
|--------|------------|-------------------|
| **Purpose** | User-facing UX content | Internal LLM configuration |
| **Frontend Access** | Single API call | Requires extra call |
| **Data Stability** | Stable across prompt versions | Changes with prompt updates |
| **Conceptual Fit** | Like `voice_id` (UX concern) | Mixed with LLM config |
| **Performance** | Fast (same table) | Slower (extra query/join) |

**Conclusion**: Suggested questions are **UX/UI content** (part of persona's public interface), not LLM prompt configuration.

---

## Implementation

### 1. Data Models

**ORM Model** (`shared/database/models/database.py`):

```python
class Persona(Base):
    __tablename__ = "personas"

    # ... existing fields ...
    suggested_questions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment='Persona-specific suggested starter questions for chat UI'
    )
```

**Pydantic Model** (`shared/database/models/persona.py`):

```python
class PersonaBase(BaseModel):
    # ... existing fields ...
    suggested_questions: Optional[List[str]] = Field(
        None,
        description="Suggested starter questions for chat UI"
    )
```

### 2. LLM Generation Function

**Location**: `app/api/prompt_routes.py`

```python
async def generate_suggested_questions_with_llm(
    persona_prompt: PersonaPrompt,
    persona: Persona,
    role: Optional[str],
    company: Optional[str],
    num_questions: int = 5
) -> List[str]:
    """
    Generate suggested questions using OpenAI based on ALL persona_prompt fields.

    Input Fields Used:
    - introduction: Persona background
    - area_of_expertise: Domain focus
    - chat_objective: Conversation goal
    - objective_response: Engagement strategy
    - thinking_style: Communication style
    - target_audience: Who they talk to
    - response_structure: Response preferences (maps to temperature)
    - role & company: Current position

    Returns:
    - List of 1-10 contextually relevant questions
    """
```

**Key Features**:
- ✅ Uses all 8 PersonaPrompt fields
- ✅ Temperature mapping from creativity setting (strict=0.3, adaptive=0.7, creative=0.9)
- ✅ Fallback questions if LLM fails
- ✅ JSON parsing with markdown removal
- ✅ Error handling with detailed logging

**LLM Prompt Structure**:

```
## Persona Profile
- Name, Role, Company
- Introduction (background)
- Area of Expertise
- Chat Objective
- Target Audience
- Communication Style
- Objective Response Strategy
- Response Preferences (length, creativity)

## Task
Generate N questions that:
1. Align with area of expertise
2. Support chat objective
3. Follow engagement strategy
4. Match target audience level
5. Vary in depth (beginner to advanced)
6. Are inviting and conversational

## Guidelines
- Concise (10-15 words)
- Clickable/actionable
- No yes/no questions
- Start meaningful conversations

## Output Format
JSON array: ["Question 1?", "Question 2?", ...]
```

### 3. API Endpoints

#### **Generation Endpoint**

```python
@router.post("/personas/{persona_id}/suggested-questions")
async def generate_suggested_questions_endpoint(
    persona_id: str,
    num_questions: int = Query(default=5, ge=1, le=10),
    force_regenerate: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
```

**URL**: `POST /api/v1/prompt/personas/{persona_id}/suggested-questions`

**Query Parameters**:
- `num_questions` (int, 1-10, default: 5) - Number of questions to generate
- `force_regenerate` (bool, default: false) - Force regeneration even if cached

**Request Example**:
```bash
POST /api/v1/prompt/personas/123e4567-e89b-12d3-a456-426614174000/suggested-questions?num_questions=5&force_regenerate=false
```

**Response**:
```json
{
  "status": "success",
  "persona_id": "123e4567-e89b-12d3-a456-426614174000",
  "suggested_questions": [
    "How did you get started in machine learning?",
    "What's the most common mistake beginners make in ML?",
    "Can you explain neural networks in simple terms?",
    "What's your favorite ML project you've worked on?",
    "How do you approach debugging ML models?"
  ],
  "generated_at": "2025-10-31T17:30:00.000Z",
  "response_settings": {
    "response_length": "explanatory",
    "creativity": "adaptive"
  },
  "from_cache": false,
  "message": "Generated 5 suggested questions"
}
```

**Caching Strategy**:
```
1. Check personas.suggested_questions cache
2. If cached and not force_regenerate → return cached (~50ms)
3. Else → generate via LLM (~1-2s)
4. Store in personas.suggested_questions
5. Return generated questions
```

#### **Public Persona Endpoint** (Updated)

**URL**: `GET /expert/{username}/public`

**Changes**:
```python
# Parse suggested_questions from JSONB
suggested_questions = None
if persona.suggested_questions and isinstance(persona.suggested_questions, dict):
    suggested_questions = persona.suggested_questions.get("questions", [])

return PublicExpertProfileResponse(
    # ... existing fields ...
    suggested_questions=suggested_questions,  # NEW
)
```

**Response** (updated):
```json
{
  "id": "uuid",
  "persona_name": "default",
  "name": "John Doe",
  "role": "ML Engineer",
  "company": "Tech Corp",
  "description": "Experienced ML engineer...",
  "suggested_questions": [  // NEW FIELD
    "How did you get started in machine learning?",
    "What's your approach to problem-solving in ML?"
  ],
  "created_at": "2025-10-31T12:00:00.000Z",
  "updated_at": "2025-10-31T12:00:00.000Z",
  "username": "johndoe",
  "fullname": "John Doe",
  "avatar": "https://..."
}
```

---

## Frontend Integration

### Step 1: Store Persona Configuration (During Creation/Onboarding)

**Use existing endpoint**: `PATCH /api/v1/prompt/update-prompt-parameter`

This endpoint updates a single field at a time and automatically handles versioning.

```typescript
// Helper function to update a single persona prompt field
const updatePromptField = async (
  personaId: string,
  field: string,
  value: any
) => {
  const response = await fetch('/api/v1/prompt/update-prompt-parameter', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      persona_id: personaId,
      field: field,
      value: value
    })
  });

  if (!response.ok) {
    throw new Error(`Failed to update ${field}`);
  }

  return response.json();
};

// Update all persona prompt fields during onboarding
const updatePersonaPromptFields = async (personaId: string, formData: any) => {
  try {
    // Update all fields in sequence
    await updatePromptField(personaId, 'introduction', formData.introduction);
    await updatePromptField(personaId, 'area_of_expertise', formData.areaOfExpertise);
    await updatePromptField(personaId, 'chat_objective', formData.chatObjective);
    await updatePromptField(personaId, 'objective_response', formData.objectiveResponse);
    await updatePromptField(personaId, 'thinking_style', formData.thinkingStyle);
    await updatePromptField(personaId, 'target_audience', formData.targetAudience);

    // Update response_structure as JSON string
    await updatePromptField(
      personaId,
      'response_structure',
      JSON.stringify({
        response_length: formData.responseLength, // "intelligent" | "concise" | "explanatory" | "custom"
        creativity: formData.creativity             // "strict" | "adaptive" | "creative"
      })
    );

    console.log('✅ All persona prompt fields updated successfully');
  } catch (error) {
    console.error('❌ Failed to update persona prompt fields:', error);
    throw error;
  }
};

// Example usage in onboarding flow
const handleOnboardingSubmit = async (formData: any) => {
  // 1. Create persona (if needed)
  const personaId = formData.personaId; // or create new persona

  // 2. Update persona prompt fields
  await updatePersonaPromptFields(personaId, {
    introduction: "ML engineer with 5 years experience...",
    areaOfExpertise: "Machine Learning, Deep Learning, NLP",
    chatObjective: "Help users understand ML concepts and solve problems",
    objectiveResponse: "Ask clarifying questions, provide step-by-step explanations with examples",
    thinkingStyle: "Analytical, example-driven, breaks down complex concepts",
    targetAudience: "ML beginners to intermediate practitioners",
    responseLength: "explanatory",
    creativity: "adaptive"
  });

  // 3. Generate suggested questions (next step)
};
```

**API Details**:

**Endpoint**: `PATCH /api/v1/prompt/update-prompt-parameter`

**Request**:
```json
{
  "persona_id": "uuid",
  "field": "chat_objective",
  "value": "Help users understand ML concepts"
}
```

**Response**:
```json
{
  "status": "success",
  "action": "field_updated",
  "persona_id": "uuid",
  "field": "chat_objective",
  "value": "Help users understand ML concepts",
  "archived_version": 2,
  "message": "Field 'chat_objective' updated successfully (version archived)"
}
```

**Supported Fields**:
- `introduction` (required)
- `thinking_style`
- `area_of_expertise`
- `chat_objective`
- `objective_response`
- `example_responses`
- `target_audience`
- `response_structure` (JSON string)
- `conversation_flow`

**Benefits**:
- ✅ Automatic versioning (old values archived)
- ✅ Individual field updates
- ✅ No need for full object replacement
- ✅ Existing endpoint (no new code needed)
```

### Step 2: Generate Suggested Questions (Once)

```typescript
// Generate questions (usually after persona creation or onboarding)
const generateQuestions = async (personaId: string) => {
  const response = await fetch(
    `/api/v1/prompt/personas/${personaId}/suggested-questions?num_questions=5`,
    { method: 'POST' }
  );

  const data = await response.json();
  console.log('Generated questions:', data.suggested_questions);
  console.log('From cache:', data.from_cache);
};
```

### Step 3: Fetch and Display (Every Chat Page Load)

```typescript
// Single API call gets everything including suggested questions
const ChatInterface = ({ username }: { username: string }) => {
  const [persona, setPersona] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPersona = async () => {
      try {
        const response = await fetch(`/expert/${username}/public`);
        const data = await response.json();
        setPersona(data);
      } catch (error) {
        console.error('Failed to fetch persona:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPersona();
  }, [username]);

  if (loading) return <div>Loading...</div>;

  return (
    <div className="chat-interface">
      {/* Header */}
      <div className="chat-header">
        <img src={persona.avatar} alt={persona.name} />
        <h1>{persona.name}</h1>
        <p>{persona.role} at {persona.company}</p>
      </div>

      {/* Suggested Questions */}
      {persona.suggested_questions && persona.suggested_questions.length > 0 && (
        <div className="suggested-questions">
          <h3>Suggested Questions</h3>
          <div className="questions-grid">
            {persona.suggested_questions.map((question: string, idx: number) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(question)}
                className="question-pill"
              >
                {question}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat Messages */}
      <div className="messages">
        {/* ... */}
      </div>

      {/* Input */}
      <input
        type="text"
        placeholder="Ask a question..."
        onKeyPress={(e) => {
          if (e.key === 'Enter') {
            handleSendMessage(e.currentTarget.value);
          }
        }}
      />
    </div>
  );
};
```

### Optional: Force Regenerate

```typescript
// Regenerate questions (e.g., after prompt update)
const regenerateQuestions = async (personaId: string) => {
  const response = await fetch(
    `/api/v1/prompt/personas/${personaId}/suggested-questions?force_regenerate=true`,
    { method: 'POST' }
  );

  const data = await response.json();
  console.log('Regenerated questions:', data.suggested_questions);
};
```

---

## Testing

### 1. Run Migration

```bash
# Using Poetry
poetry run alembic upgrade head

# Using Docker
docker-compose exec backend alembic upgrade head

# Check migration applied
poetry run alembic current
```

### 2. Create Persona and Update Prompt Fields

```bash
# Step 1: Create persona
curl -X POST "http://localhost:8001/api/v1/personas" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "description": "ML Engineer"
  }'

# Response: { "id": "{persona_id}", ... }

# Step 2: Update persona prompt fields using update-prompt-parameter endpoint

# Update introduction
curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "{persona_id}",
    "field": "introduction",
    "value": "ML engineer with 5 years experience"
  }'

# Update area_of_expertise
curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "{persona_id}",
    "field": "area_of_expertise",
    "value": "Machine Learning, Deep Learning"
  }'

# Update chat_objective
curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "{persona_id}",
    "field": "chat_objective",
    "value": "Help users learn ML concepts"
  }'

# Update objective_response
curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "{persona_id}",
    "field": "objective_response",
    "value": "Ask clarifying questions, provide examples"
  }'

# Update thinking_style
curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "{persona_id}",
    "field": "thinking_style",
    "value": "Analytical and clear"
  }'

# Update target_audience
curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "{persona_id}",
    "field": "target_audience",
    "value": "ML beginners"
  }'

# Update response_structure (as JSON string)
curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "{persona_id}",
    "field": "response_structure",
    "value": "{\"response_length\": \"explanatory\", \"creativity\": \"adaptive\"}"
  }'
```

### 3. Generate Suggested Questions

```bash
curl -X POST "http://localhost:8000/api/v1/prompt/personas/{persona_id}/suggested-questions?num_questions=5"
```

**Expected Response**:
```json
{
  "status": "success",
  "suggested_questions": [
    "How did you get started in machine learning?",
    "What's the most common ML mistake you see?",
    "Can you explain neural networks in simple terms?",
    "What's your favorite ML project?",
    "How do you approach debugging ML models?"
  ],
  "from_cache": false
}
```

### 4. Verify in Database

```sql
SELECT
  id,
  name,
  suggested_questions
FROM personas
WHERE id = '{persona_id}';
```

**Expected**:
```
suggested_questions: {"questions": ["..."], "generated_at": "...", "response_settings": {...}}
```

### 5. Test Public Endpoint

```bash
curl "http://localhost:8000/expert/{username}/public"
```

**Expected**: Response includes `suggested_questions` field.

### 6. Test Caching

```bash
# First call (generates)
time curl -X POST ".../suggested-questions"
# Should take ~1-2 seconds

# Second call (cached)
time curl -X POST ".../suggested-questions"
# Should take ~50ms

# Force regenerate
curl -X POST ".../suggested-questions?force_regenerate=true"
# Should take ~1-2 seconds
```

### 7. Test Fallback

```bash
# Temporarily break OpenAI API key in .env
OPENAI_API_KEY=invalid

# Generate questions
curl -X POST ".../suggested-questions"

# Should return fallback questions:
# ["How did you get started in {expertise}?", ...]
```

---

## Performance

| Operation | Response Time | Notes |
|-----------|---------------|-------|
| **First generation** (LLM) | ~1-2 seconds | OpenAI API call |
| **Cached retrieval** | ~50ms | From database |
| **Public endpoint** (with questions) | ~100ms | Single query |
| **Force regenerate** | ~1-2 seconds | Regenerates + updates cache |

---

## Error Handling

### Fallback Questions

If OpenAI LLM fails, fallback to generic questions:

```python
expertise = persona_prompt.area_of_expertise or "your field"
fallback = [
    f"How did you get started in {expertise}?",
    f"What's the most important thing to know about {expertise}?",
    f"What's a common misconception about {expertise}?",
    "What's the most interesting project you've worked on?",
    "What advice would you give someone starting out?"
]
```

### Error Logging

```python
logger.error(f"Failed to generate suggested questions: {e}")
# Returns fallback questions instead of failing
```

### Graceful Degradation

- Frontend checks `if (persona.suggested_questions)` before rendering
- If missing, chat UI still works (just no suggested questions)
- No breaking changes to existing functionality

---

## Files Changed

### Created

1. **`alembic/versions/2dd8da251a96_add_suggested_questions_to_personas.py`**
   - Database migration
   - Adds `suggested_questions` JSONB column
   - Adds GIN index

2. **`docs/SUGGESTED_QUESTIONS_FEATURE.md`**
   - This documentation file

### Modified

1. **`shared/database/models/database.py`** (+3 lines)
   - Added `suggested_questions` field to Persona ORM model

2. **`shared/database/models/persona.py`** (+3 lines)
   - Added `suggested_questions` field to PersonaBase Pydantic model

3. **`app/api/prompt_routes.py`** (+298 lines)
   - Added `generate_suggested_questions_with_llm()` function
   - Added `SuggestedQuestionsResponse` model
   - Added `POST /personas/{persona_id}/suggested-questions` endpoint

4. **`app/api/routes.py`** (+7 lines)
   - Updated `PublicExpertProfileResponse` with `suggested_questions` field
   - Updated `GET /expert/{username}/public` to parse and return questions

**Total**: +311 lines of code (excluding docs)

---

## Configuration

### Environment Variables

Uses existing OpenAI configuration:

```bash
OPENAI_API_KEY=sk-...  # Required for LLM generation
```

### Settings

All settings managed through existing `shared/config.py`:

```python
settings.openai_api_key  # Used by OpenAIModelService
```

---

## API Reference Summary

### 1. Update Persona Prompt Fields (EXISTING ENDPOINT)

```
PATCH /api/v1/prompt/update-prompt-parameter
```

**Use this endpoint to store persona prompt data from frontend.**

**Request Body**:
```json
{
  "persona_id": "uuid",
  "field": "chat_objective",
  "value": "Help users understand ML concepts"
}
```

**Supported Fields**:
- `introduction` (string, required)
- `thinking_style` (string)
- `area_of_expertise` (string)
- `chat_objective` (string)
- `objective_response` (string)
- `example_responses` (string)
- `target_audience` (string)
- `response_structure` (string - JSON format)
- `conversation_flow` (string)

**Response**:
```json
{
  "status": "success",
  "action": "field_updated",
  "persona_id": "uuid",
  "field": "chat_objective",
  "value": "Help users understand ML concepts",
  "archived_version": 2,
  "message": "Field 'chat_objective' updated successfully (version archived)"
}
```

**Features**:
- ✅ Updates single field at a time
- ✅ Automatic versioning (archives old value)
- ✅ Returns updated value
- ✅ Version history tracking

**Example - Update Response Structure**:
```bash
curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "uuid",
    "field": "response_structure",
    "value": "{\"response_length\": \"explanatory\", \"creativity\": \"adaptive\"}"
  }'
```

---

### 2. Generate Suggested Questions (NEW ENDPOINT)

```
POST /api/v1/prompt/personas/{persona_id}/suggested-questions
```

**Query Parameters**:
- `num_questions` (int, 1-10, default: 5)
- `force_regenerate` (bool, default: false)

**Response**: `SuggestedQuestionsResponse`
```json
{
  "status": "success",
  "persona_id": "uuid",
  "suggested_questions": [
    "How did you get started in machine learning?",
    "What's your approach to debugging ML models?"
  ],
  "generated_at": "2025-10-31T17:30:00.000Z",
  "response_settings": {
    "response_length": "explanatory",
    "creativity": "adaptive"
  },
  "from_cache": false,
  "message": "Generated 5 suggested questions"
}
```

**Features**:
- ✅ Generates questions using OpenAI LLM
- ✅ Uses all persona_prompt fields
- ✅ Caches in `personas.suggested_questions`
- ✅ Returns cached version if available
- ✅ Force regeneration support

---

### 3. Public Persona Profile (UPDATED ENDPOINT)

```
GET /expert/{username}/public
```

**Query Parameters**:
- `persona_name` (str, default: "default")

**Response**: `PublicExpertProfileResponse` (updated)
```json
{
  "id": "uuid",
  "name": "John Doe",
  "role": "ML Engineer",
  "company": "Tech Corp",
  "suggested_questions": [  // NEW FIELD
    "How did you get started in ML?",
    "What's your approach to problem-solving?"
  ],
  "username": "johndoe",
  "avatar": "https://..."
}
```

**Features**:
- ✅ Single API call gets all chat UI data
- ✅ Includes suggested_questions if generated
- ✅ No extra request needed

---

## Future Enhancements

### Phase 2: Auto-Regeneration
- Regenerate when `persona_prompts` updated
- Add database trigger or webhook
- Update cache automatically

### Phase 3: Analytics
- Track which questions clicked most
- Measure conversion rates
- A/B test different question sets
- User feedback on relevance

### Phase 4: Manual Curation
- Admin UI to edit/approve questions
- Dedicated `persona_suggested_questions` table
- Versioning and approval workflow
- Multi-language support

### Phase 5: Personalization
- User-specific questions based on history
- Dynamic questions based on conversation context
- ML-powered question ranking

---

## Troubleshooting

### Questions Not Appearing

1. **Check database**:
   ```sql
   SELECT suggested_questions FROM personas WHERE id = '{persona_id}';
   ```

2. **Generate manually**:
   ```bash
   curl -X POST ".../suggested-questions?force_regenerate=true"
   ```

3. **Check persona_prompt exists**:
   ```sql
   SELECT * FROM persona_prompts WHERE persona_id = '{persona_id}' AND is_active = true;
   ```

### Slow Generation

- First generation takes 1-2 seconds (normal, LLM call)
- Use caching (subsequent calls ~50ms)
- Consider background job for generation

### LLM Errors

- Check `OPENAI_API_KEY` is valid
- Check OpenAI API status
- Fallback questions will be returned automatically

### JSON Parsing Errors

- Handled gracefully with fallback
- Markdown code blocks automatically removed
- Logs detailed errors for debugging

---

## Summary

✅ **Feature Complete**
- Database schema with JSONB column
- LLM-based generation using all persona_prompt fields
- Caching for performance
- Public API integration
- Frontend-ready

✅ **Production Ready**
- Error handling with fallbacks
- Caching strategy
- Performance optimized
- Backward compatible
- No breaking changes

✅ **Well Documented**
- Complete API reference
- Frontend integration guide
- Testing procedures
- Troubleshooting guide

---

## Quick Start

```bash
# 1. Run migration
docker compose exec api bash -c "cd /app && /home/appuser/.local/bin/alembic upgrade heads"

# 2. Create persona
curl -X POST "http://localhost:8001/api/v1/personas" \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "description": "ML Engineer"}'
# Response: { "id": "{persona_id}", ... }

# 3. Update persona prompt fields using update-prompt-parameter
PERSONA_ID="<persona_id_from_step_2>"

# Update key fields
curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d "{\"persona_id\": \"$PERSONA_ID\", \"field\": \"introduction\", \"value\": \"ML engineer with 5 years experience\"}"

curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d "{\"persona_id\": \"$PERSONA_ID\", \"field\": \"area_of_expertise\", \"value\": \"Machine Learning, Deep Learning\"}"

curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d "{\"persona_id\": \"$PERSONA_ID\", \"field\": \"chat_objective\", \"value\": \"Help users learn ML concepts\"}"

curl -X PATCH "http://localhost:8001/api/v1/prompt/update-prompt-parameter" \
  -H "Content-Type: application/json" \
  -d "{\"persona_id\": \"$PERSONA_ID\", \"field\": \"response_structure\", \"value\": \"{\\\"response_length\\\": \\\"explanatory\\\", \\\"creativity\\\": \\\"adaptive\\\"}\"}"

# 4. Generate suggested questions
curl -X POST "http://localhost:8001/api/v1/prompt/personas/$PERSONA_ID/suggested-questions?num_questions=5"

# 5. Fetch persona with questions in frontend
const persona = await fetch('/expert/{username}/public').then(r => r.json());
console.log(persona.suggested_questions);
// Output: ["How did you get started in ML?", "What's your approach to...", ...]
```

**That's it!** 🚀

### Frontend Integration Summary

```typescript
// 1. Update persona prompt fields (during onboarding)
await updatePromptField(personaId, 'introduction', formData.introduction);
await updatePromptField(personaId, 'area_of_expertise', formData.expertise);
await updatePromptField(personaId, 'chat_objective', formData.objective);
await updatePromptField(personaId, 'response_structure', JSON.stringify({
  response_length: formData.responseLength,
  creativity: formData.creativity
}));

// 2. Generate questions (once)
const { suggested_questions } = await fetch(
  `/api/v1/prompt/personas/${personaId}/suggested-questions?num_questions=5`,
  { method: 'POST' }
).then(r => r.json());

// 3. Display in chat UI (every page load)
const persona = await fetch(`/expert/${username}/public`).then(r => r.json());
// persona.suggested_questions is already available!
```
