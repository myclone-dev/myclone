# Persona Prompt Management Documentation

## Overview

The Persona Prompt Management system provides comprehensive versioning and CRUD operations for managing persona prompts with full audit trails. The system maintains historical versions of all changes while providing flexible access to current and past prompt configurations.

## Features

- **Full Version History**: Every change creates a versioned snapshot in the history table
- **Soft Deletion**: Prompts are marked inactive rather than deleted, preserving data integrity
- **Version Comparison**: Compare any two versions to see differences
- **Timeline View**: Combined view of current and historical versions
- **Restoration**: Restore any previous version as the current active version
- **Non-Versioned Updates**: Special operations that don't create version history
- **Comprehensive Audit Trail**: Track all operations with timestamps and operation types

## Data Model

### PersonaPrompt (Main Table)
- `persona_id` (str): Unique identifier for the persona
- `introduction` (str): Introduction text for the persona
- `thinking_style` (str): Description of thinking approach
- `area_of_expertise` (str): Domain expertise area
- `chat_objective` (str): Primary chat objectives
- `objective_response` (str): Expected response patterns
- `example_responses` (str): Sample responses
- `target_audience` (str): Intended audience
- `prompt_template` (str): Template structure
- `example_prompt` (str): Generated prompt content
- `is_dynamic` (bool): Dynamic behavior flag
- `is_active` (bool): Active status flag
- `response_structure` (str): Response formatting rules
- `conversation_flow` (str): Conversation management rules
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last modification timestamp

### PersonaPromptHistory (History Table)
- `id` (int): Unique history entry ID
- `original_id` (int): Reference to original record ID
- `persona_id` (str): Persona ID reference
- `version` (int): Version number (auto-incremented)
- `operation` (str): Operation type (CREATE, UPDATE, DELETE, RESTORE)
- `changed_at` (datetime): Timestamp of the change
- All persona prompt fields as snapshot

## API Endpoints

### Legacy Prompt Generation Endpoints

#### POST `/api/v1/prompt/create-prompt-for-persona`
Creates a new prompt for a persona using OpenAI LLM with versioning integration.

**Request Body:**
```json
{
  "username": "string",
  "template": "basic",
  "expertise": "general",
  "platform": "openai"
}
```

**Logic:**
1. Check for active prompt - if exists, return it
2. Check for inactive prompt - if exists, reactivate and update
3. If no prompt exists, create new one

**Response:**
```json
{
  "status": "success",
  "action": "created|existing|reactivated",
  "persona_id": "string",
  "prompt": "string",
  "message": "string"
}
```

#### PUT `/api/v1/prompt/update-prompt-for-persona`
Updates an existing prompt using OpenAI LLM with automatic versioning.

**Request Body:** Same as create endpoint

**Response:**
```json
{
  "status": "success",
  "action": "updated",
  "persona_id": "string",
  "prompt": "string",
  "archived_version": 2,
  "message": "string"
}
```

#### DELETE `/api/v1/prompt/delete-prompt-for-persona?username={username}`
Soft deletes a prompt by setting `is_active = false` and archiving to history.

**Response:**
```json
{
  "status": "success",
  "action": "inactivated",
  "persona_id": "string",
  "archived_version": 3,
  "operation": "DELETE",
  "message": "string"
}
```

#### PATCH `/api/v1/prompt/update-prompt-parameter`
Updates a single field with automatic versioning.

**Request Body:**
```json
{
  "username": "string",
  "field": "introduction|thinking_style|area_of_expertise|...",
  "value": "string"
}
```

**Response:**
```json
{
  "status": "success",
  "action": "field_updated",
  "persona_id": "string",
  "field": "string",
  "value": "string",
  "archived_version": 4,
  "message": "string"
}
```

### Versioned CRUD Endpoints

#### POST `/api/v1/prompt/persona-prompts`
Creates a new persona prompt (Version 1) with versioning support.

**Request Body:**
```json
{
  "persona_id": "string",
  "introduction": "string",
  "thinking_style": "string",
  "area_of_expertise": "string",
  "chat_objective": "string",
  "objective_response": "string",
  "example_responses": "string",
  "target_audience": "string",
  "prompt_template": "string",
  "example_prompt": "string",
  "is_dynamic": false,
  "response_structure": "string",
  "conversation_flow": "string"
}
```

#### PUT `/api/v1/prompt/persona-prompts/{persona_id}`
Updates a persona prompt with automatic versioning.

**Request Body:** Same fields as POST (all optional except changes)

#### GET `/api/v1/prompt/persona-prompts/{persona_id}`
Retrieves the current active version of a persona prompt.

#### GET `/api/v1/prompt/persona-prompts-all?include_inactive=false`
Lists all persona prompts (current versions only by default).

### History and Versioning Endpoints

#### GET `/api/v1/prompt/persona-prompts/{persona_id}/history?limit=10`
Gets all historical versions (excluding current version).

**Response:**
```json
[
  {
    "id": 1,
    "original_id": 123,
    "persona_id": "string",
    "version": 2,
    "operation": "UPDATE",
    "changed_at": "2025-10-04T10:30:00Z",
    "introduction": "string",
    // ... all other fields
  }
]
```

#### GET `/api/v1/prompt/persona-prompts/{persona_id}/timeline`
Gets complete timeline including current and historical versions.

#### GET `/api/v1/prompt/persona-prompts/{persona_id}/history/{version}`
Gets a specific historical version.

#### GET `/api/v1/prompt/persona-prompts/{persona_id}/compare?from_version=1&to_version=3`
Compares two versions and returns differences. Use `0` for current version.

**Response:**
```json
{
  "persona_id": "string",
  "version_1": 1,
  "version_2": 3,
  "differences": {
    "introduction": {
      "version_1": "old text",
      "version_3": "new text"
    }
  },
  "identical": false
}
```

#### POST `/api/v1/prompt/persona-prompts/{persona_id}/restore/{version}`
Restores a previous version as current. Archives current version first.

#### GET `/api/v1/prompt/persona-prompts/{persona_id}/versions`
Gets version metadata (numbers, operations, timestamps) without full content.

#### GET `/api/v1/prompt/persona-prompts/{persona_id}/history/count`
Gets count of historical versions.

### Special Operations

#### POST `/api/v1/prompt/change-is-dynamic`
Toggles the `is_dynamic` flag **without creating version history**.

**Request Body:**
```json
{
  "username": "string",
  "is_dynamic": true
}
```

**Note:** Also accepts `is_dyname` as an alias for backward compatibility.

**Response:**
```json
{
  "status": "success",
  "action": "is_dynamic_changed",
  "persona_id": "string",
  "is_dynamic": true
}
```

## Version Management

### Automatic Versioning
All update and delete operations automatically:
1. Archive the current state to `PersonaPromptHistory`
2. Increment the version number
3. Record the operation type and timestamp
4. Apply the changes to the main record

### Operation Types
- `CREATE`: Initial creation (no history entry)
- `UPDATE`: Standard field updates
- `DELETE`: Soft deletion (sets `is_active = false`)
- `RESTORE`: Restoration from previous version

### Version Numbers
- Version numbers are auto-incremented per persona
- Current version number = highest history version + 1
- Initial creation starts at version 1 (no history entry)

### Soft Deletion
- Records are never hard deleted
- `is_active = false` marks inactive records
- Inactive records can be reactivated
- Full audit trail preserved

## Usage Examples

### Creating a New Persona Prompt
```bash
curl -X POST "/api/v1/prompt/persona-prompts" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "expert_advisor",
    "introduction": "I am an expert financial advisor...",
    "thinking_style": "Analytical and methodical",
    "area_of_expertise": "Financial planning",
    "is_dynamic": false
  }'
```

### Updating with Version History
```bash
curl -X PUT "/api/v1/prompt/persona-prompts/expert_advisor" \
  -H "Content-Type: application/json" \
  -d '{
    "introduction": "Updated introduction text",
    "thinking_style": "More collaborative approach"
  }'
```

### Comparing Versions
```bash
curl "/api/v1/prompt/persona-prompts/expert_advisor/compare?from_version=1&to_version=0"
```

### Restoring Previous Version
```bash
curl -X POST "/api/v1/prompt/persona-prompts/expert_advisor/restore/2"
```

### Non-Versioned Update
```bash
curl -X POST "/api/v1/prompt/change-is-dynamic" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "expert_advisor",
    "is_dynamic": true
  }'
```

## Integration Notes

### Database Schema
- Main table: `persona_prompts`
- History table: `persona_prompt_history`
- Unique constraint on `persona_username` in main table
- Foreign key relationship maintained through username

### Service Layer
The `PersonaPromptHistoryService` handles all versioning operations:
- `update_persona_prompt_with_versioning()`
- `delete_persona_prompt_with_versioning()`
- `restore_version()`
- `compare_versions()`
- `get_complete_timeline()`

### Error Handling
- 404: Persona not found
- 400: Invalid request data
- 409: Constraint violations
- 500: Server errors with rollback

### Performance Considerations
- Use metadata endpoints for version lists
- Limit history queries when appropriate
- Consider archival strategies for old versions
- Index on `persona_username` and `version` fields

## Migration Notes

### Backward Compatibility
- Legacy endpoints continue to work
- New versioning features added alongside existing functionality
- `is_dyname` alias maintained for compatibility

### Data Migration
- Existing records become version 1
- No history entries for pre-existing data
- All future changes tracked with versioning

## Best Practices

1. **Use versioned endpoints** for new development
2. **Implement proper error handling** for all API calls
3. **Consider version limits** for long-running personas
4. **Use comparison endpoints** before major updates
5. **Leverage soft deletion** instead of hard deletes
6. **Monitor history table growth** for maintenance
7. **Use non-versioned updates sparingly** and only for truly non-content changes

## Troubleshooting

### Common Issues
- **Version conflicts**: Use latest version info before updates
- **Permission errors**: Ensure proper database access
- **Large history**: Implement archival or cleanup policies
- **Performance**: Use metadata endpoints for UI displays

### Debugging
- Check operation logs in history table
- Verify version sequences are consistent
- Monitor database constraint violations
- Review error logs for versioning failures
