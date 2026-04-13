# Workflow Templates & LiveKit Integration - Architecture Proposal

**Status:** ✅ Phase 1 Completed (Template System Backend)
**Date:** 2026-01-25 (Updated: 2026-01-26)
**Purpose:** Understand requirements and design architecture before implementation

**Implementation Status:**
- ✅ Phase 1: Template System (Backend) - **COMPLETED**
  - Database schema with `minimum_plan_tier_id` FK to `tier_plans(id)`
  - Template repository with tier-based access control
  - CPA Lead Capture template seeded
  - Legacy tier exclusion implemented
- 🚧 Phase 2: Template API - **IN PROGRESS**
- ⏳ Phase 3: LiveKit Integration - **NOT STARTED**
- ⏳ Phase 4: Frontend Dashboard - **NOT STARTED**

---

## 🔑 Key Understanding

**IMPORTANT**: This is NOT a system for multiple pre-built templates. Instead:

- **ONE base template**: "CPA Lead Capture" with generic fields
- **Heavy customization expected**: Each CPA firm enables the template and customizes it for their specific needs
- **Example use cases**:
  - AMI CPA enables → customizes for individual tax, FBAR focus
  - Lion Star Tax enables same template → customizes for business tax, entity formation
- **Result**: Same template → multiple different customized workflows per firm

---

## 🎯 Business Requirements

### 1. Workflow Template System
- **ONE Base Template**: "CPA Lead Capture" - generic conversational workflow for CPA firms
- **Customization Expected**: Each CPA firm (AMI CPA, Lion Star Tax, etc.) enables the template and customizes it for their specific needs
  - Example: AMI CPA customizes for individual tax, FBAR focus
  - Example: Lion Star Tax customizes for business tax, entity formation focus
- **Enterprise Feature**: Template available only for enterprise-tier users
- **Persona Enablement**: Users enable template for their personas, then customize fields/scoring

### 2. LiveKit Voice Integration
- Users can complete conversational workflows via voice (LiveKit)
- Real-time field extraction from spoken conversation
- Voice-based clarifying questions
- Progress tracking during voice interaction

---

## 🏗️ Current Architecture Analysis

### Database Schema (Current State)

```
persona_workflows table:
├── id (UUID)
├── persona_id (FK → personas)
├── workflow_type ('simple', 'scored', 'conversational')
├── title
├── description
├── opening_message
├── workflow_objective
├── workflow_config (JSONB) - field definitions, extraction strategy
├── result_config (JSONB) - for 'scored' workflows
├── output_template (JSONB) ← Added in migration, not in ORM model yet
│   └── Structure: {scoring_rules, sections, follow_up_rules}
├── is_active (boolean)
├── version (int)
├── published_at
├── trigger_config (JSONB)
├── extra_metadata (JSONB)
├── created_at
└── updated_at

workflow_sessions table:
├── id (UUID)
├── workflow_id (FK → persona_workflows)
├── persona_id (FK → personas)
├── conversation_id (FK → conversations, nullable)
├── user_id (FK → users, nullable)
├── status ('in_progress', 'completed', 'abandoned')
├── current_step_id
├── progress_percentage (0-100)
├── collected_data (JSONB) - for simple/scored workflows
├── extracted_fields (JSONB) ← Added in migration, not in ORM model yet
│   └── Structure: {field_id: {value, confidence, extraction_method}}
├── result_data (JSONB)
├── session_metadata (JSONB)
├── started_at
├── completed_at
└── updated_at
```

**Key Observation**: Currently, workflows are **persona-owned** (one workflow per persona). No template system exists.

---

## 🔧 Architecture Option 1: Template Library with Copy-on-Enable

### Proposed Tables

```sql
-- NEW TABLE: Workflow Templates (Master Library)
CREATE TABLE workflow_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Template identification
    template_key VARCHAR(100) UNIQUE NOT NULL,  -- e.g., 'cpa_lead_capture'
                                                 -- Stable identifier for code references, migrations
    template_name VARCHAR(200) NOT NULL,        -- e.g., 'CPA Lead Capture'
    template_category VARCHAR(50) NOT NULL,     -- e.g., 'cpa', 'tax', 'insurance'

    -- Access control (FK to tier_plans table)
    minimum_plan_tier_id INTEGER NOT NULL DEFAULT 0 REFERENCES tier_plans(id) ON DELETE RESTRICT,
    -- Tier hierarchy: 0=free, 1=pro, 2=business, 3=enterprise (highest)
    -- Legacy tiers (4+) are excluded from template access

    -- Template configuration (same structure as persona_workflows)
    workflow_type VARCHAR(20) NOT NULL,         -- 'conversational' (for now)
    workflow_config JSONB NOT NULL,             -- Base field definitions, extraction strategy
    output_template JSONB NOT NULL,             -- Base scoring rules, follow-up questions, sections

    -- Metadata (OPTIONAL - nullable)
    description TEXT,                           -- Template description for UI
    preview_image_url TEXT,                     -- Screenshot/preview for template gallery (optional)
    tags TEXT[],                                -- ['cpa', 'tax', 'lead-capture'] for search/filtering

    -- Versioning
    version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE INDEX idx_workflow_templates_key ON workflow_templates(template_key);
CREATE INDEX idx_workflow_templates_category ON workflow_templates(template_category);
CREATE INDEX idx_workflow_templates_active ON workflow_templates(is_active);
CREATE INDEX idx_workflow_templates_tier_id ON workflow_templates(minimum_plan_tier_id);
CREATE INDEX idx_workflow_templates_config ON workflow_templates USING GIN (workflow_config);


-- UPDATE TABLE: persona_workflows (add template tracking)
ALTER TABLE persona_workflows ADD COLUMN template_id UUID REFERENCES workflow_templates(id) ON DELETE SET NULL;
ALTER TABLE persona_workflows ADD COLUMN is_template_customized BOOLEAN DEFAULT false;

CREATE INDEX idx_persona_workflows_template ON persona_workflows(template_id);
```

### How It Works

**1. Template Creation (Admin/System)**
- Admin seeds ONE template: `cpa_lead_capture`
- Template contains GENERIC base config for CPA lead capture
- Marked as `minimum_plan_tier_id = 3` (enterprise - highest tier)

**2. Template Discovery (Enterprise User)**
- User browses template library
- API filters templates based on user's plan tier
- User sees: "CPA Lead Capture" template

**3. Template Enablement - Example: AMI CPA**
```
AMI CPA clicks "Enable CPA Lead Capture Template for Persona X"
  ↓
Backend creates entry in persona_workflows:
  - template_id = cpa_lead_capture_id
  - persona_id = X
  - workflow_config = COPY from template (base config)
  - output_template = COPY from template (base scoring)
  - is_template_customized = false (initially)
  ↓
AMI CPA can now use this workflow
```

**4. Template Customization - AMI CPA (Individual Tax Focus)**
```
AMI CPA customizes workflow for their firm:
  ↓
Adds fields:
  - filing_type (individual/joint)
  - foreign_accounts (FBAR requirement)
  - life_events (marriage, divorce, etc.)
  ↓
Updates scoring:
  - foreign_accounts present: +15 points
  - foreign income: +10 points
  ↓
Backend updates persona_workflows:
  - workflow_config = MODIFIED (AMI CPA's custom config)
  - is_template_customized = true
  ↓
AMI CPA's workflow now tailored for individual tax clients
```

**5. Same Template, Different Customization - Lion Star Tax (Business Focus)**
```
Lion Star Tax ALSO enables "CPA Lead Capture" template
  ↓
Backend creates SEPARATE persona_workflows entry:
  - template_id = cpa_lead_capture_id (SAME template!)
  - persona_id = Y (Lion Star Tax's persona)
  - workflow_config = COPY from template (base config)
  - is_template_customized = false
  ↓
Lion Star Tax customizes differently:
  ↓
Adds fields:
  - business_name
  - entity_type (LLC, S-Corp, C-Corp)
  - revenue_range
  - employee_count
  ↓
Updates scoring:
  - revenue $1M+: +15 points
  - multi-state operations: +10 points
  ↓
Backend updates their persona_workflows:
  - workflow_config = MODIFIED (LST's custom config)
  - is_template_customized = true
  ↓
Lion Star Tax's workflow now tailored for business clients
```

**Result**: ONE template → TWO completely different customized workflows

**6. Template Updates (Future)**
```
Admin updates base "CPA Lead Capture" template (v2)
  ↓
System notifies ALL users: "CPA Lead Capture template updated"
  ↓
If is_template_customized = false:
  - Auto-update workflow_config from template
If is_template_customized = true:
  - Show diff, let user decide to merge or keep custom
  ↓
AMI CPA and LST can each choose to adopt template changes or keep their customizations
```

### Pros & Cons

✅ **Pros:**
- Clean separation: templates are master, workflows are instances
- Easy to add new templates without touching persona_workflows
- Users can customize after enabling (copy-on-write)
- Template updates can propagate to instances
- Clear audit trail (which workflows came from which template)

❌ **Cons:**
- Duplication of config in database (template + all instances)
- Need to handle template update propagation logic
- More complex queries (need to check both template_id and is_customized)

---

## 🔧 Architecture Option 2: Template References (No Duplication)

### Proposed Tables

```sql
-- Same workflow_templates table as Option 1

-- UPDATE: persona_workflows (reference-based)
ALTER TABLE persona_workflows ADD COLUMN template_id UUID REFERENCES workflow_templates(id) ON DELETE RESTRICT;
ALTER TABLE persona_workflows ADD COLUMN custom_workflow_config JSONB;  -- Overrides for template config
ALTER TABLE persona_workflows ADD COLUMN custom_output_template JSONB; -- Overrides for template output

-- If template_id is set:
--   - Use template's workflow_config + merge custom_workflow_config
--   - Use template's output_template + merge custom_output_template
-- If template_id is NULL:
--   - Use workflow_config directly (custom workflow, not from template)
```

### How It Works

**1. Template Enablement - AMI CPA Example**
```
AMI CPA enables "CPA Lead Capture" template
  ↓
Backend creates persona_workflows entry:
  - template_id = cpa_lead_capture_id
  - workflow_config = NULL (use template's)
  - output_template = NULL (use template's)
  - custom_workflow_config = NULL
  - custom_output_template = NULL
  ↓
At runtime, system reads base config from template
```

**2. Template Customization - AMI CPA Adds FBAR Fields**
```
AMI CPA adds foreign_accounts field and updates scoring
  ↓
Backend updates persona_workflows:
  - custom_workflow_config = {
      "optional_fields": [
        {"field_id": "foreign_accounts", "field_type": "text", ...}
      ]
    }
  - custom_output_template = {
      "scoring_rules": {
        "quality_signals": [
          {"signal_id": "foreign_accounts_fbar", "points": 15, "condition": {...}}
        ]
      }
    }
  ↓
At runtime, system merges template config + AMI CPA's custom overrides
```

**3. Same Template, Different Customization - Lion Star Tax**
```
Lion Star Tax also enables "CPA Lead Capture" template
  ↓
Creates SEPARATE persona_workflows entry with same template_id
  ↓
Lion Star Tax adds business-specific fields and scoring
  ↓
Their custom_workflow_config adds: business_name, entity_type, revenue_range
Their custom_output_template adds: revenue-based scoring
  ↓
Result: Same template, completely different customizations
```

**4. Template Updates**
```
Admin updates template
  ↓
All instances automatically use new template (if no custom overrides)
  ↓
Users with custom overrides keep their customizations
```

### Pros & Cons

✅ **Pros:**
- Zero duplication - config lives only in template
- Template updates instantly apply to all instances
- Smaller database footprint
- Clear distinction: base template vs overrides

❌ **Cons:**
- More complex runtime logic (merge template + overrides)
- Cannot delete template if personas reference it (ON DELETE RESTRICT)
- Harder to audit "what config was used on date X" (template may have changed)
- Merge conflicts if user customized field that template also changed

---

## 🔧 Architecture Option 3: Hybrid (Snapshot + Reference)

### Proposed Tables

```sql
-- Same workflow_templates table as Option 1

-- UPDATE: persona_workflows
ALTER TABLE persona_workflows ADD COLUMN template_id UUID REFERENCES workflow_templates(id) ON DELETE SET NULL;
ALTER TABLE persona_workflows ADD COLUMN template_version INT;  -- Snapshot version
ALTER TABLE persona_workflows ADD COLUMN is_template_customized BOOLEAN DEFAULT false;

-- How it works:
-- 1. When enabling template: COPY config from template (snapshot)
-- 2. Store template_id + template_version for reference
-- 3. If user customizes: is_template_customized = true
-- 4. If template updates: compare template_version, offer to re-sync
```

### Pros & Cons

✅ **Pros:**
- Best of both worlds: snapshot for stability + reference for updates
- Clear audit trail (workflow has exact config at creation time)
- Can delete old template versions without breaking workflows
- User can choose to sync with new template version or stay on old

❌ **Cons:**
- Still has duplication (same as Option 1)
- Need to build UI for "template update available" notifications

---

## 🎙️ LiveKit Integration Architecture

### Current LiveKit Setup

```
LiveKit Voice Agent (livekit/livekit_agent_retrieval.py)
  ├── Deepgram (STT - Speech to Text)
  ├── ElevenLabs (TTS - Text to Speech)
  └── PersonaRetrievalAgent (custom)
      └── Generates responses using persona system prompts + RAG
```

### Proposed: Conversational Workflow + LiveKit Integration

**Option A: Workflow-Aware LiveKit Agent**

```python
class ConversationalWorkflowVoiceAgent(VoiceAgent):
    """
    LiveKit agent that runs conversational workflows via voice.
    """

    def __init__(self, persona_id, workflow_id):
        self.persona_id = persona_id
        self.workflow_id = workflow_id
        self.session_id = None  # Created when workflow starts
        self.executor = ConversationalWorkflowExecutor()

    async def on_user_speech(self, transcript: str):
        """Called when user speaks (Deepgram STT)"""

        # Process message through conversational workflow
        result = await self.executor.process_user_message(
            user_message=transcript,
            session_id=self.session_id,
            workflow_config=self.workflow_config,
            output_template=self.output_template,
            workflow_repo=self.workflow_repo,
            chat_history=self.chat_history
        )

        if result['status'] == 'in_progress':
            # Ask next clarifying question via TTS
            await self.speak(result['next_question'])

        elif result['status'] == 'awaiting_confirmation':
            # Read confirmation summary via TTS
            await self.speak(result['confirmation_summary'])

        elif result['status'] == 'completed':
            # Workflow done - read summary via TTS
            await self.speak(f"Great! Here's your summary: {result['final_summary']}")
```

**Flow:**
1. User starts voice call with persona
2. System detects workflow trigger (e.g., "I want to get qualified for CPA services")
3. Backend creates `WorkflowSession` and switches LiveKit agent to workflow mode
4. User speaks → Deepgram STT → Conversational workflow processes
5. System responds with clarifying questions → ElevenLabs TTS → User hears
6. Repeat until workflow complete
7. System generates final summary and reads it to user

**Option B: Dual-Mode LiveKit Agent**

```python
class PersonaVoiceAgent:
    """
    LiveKit agent with two modes: chat mode and workflow mode.
    """

    mode: Literal['chat', 'workflow'] = 'chat'

    async def on_user_speech(self, transcript: str):
        if self.mode == 'chat':
            # Normal chat - use RAG + LLM
            response = await self.generate_chat_response(transcript)

            # Check if user triggered workflow
            if self.detect_workflow_trigger(transcript):
                await self.start_workflow()

        elif self.mode == 'workflow':
            # Workflow mode - process through executor
            result = await self.process_workflow_message(transcript)

            if result['status'] == 'completed':
                self.mode = 'chat'  # Return to chat mode
```

---

## 📊 Comparison Matrix

| Aspect | Option 1: Copy-on-Enable | Option 2: Reference | Option 3: Hybrid |
|--------|-------------------------|---------------------|------------------|
| **Config Duplication** | Yes | No | Yes |
| **Template Updates** | Manual sync | Automatic | Manual sync |
| **Audit Trail** | Excellent | Poor | Excellent |
| **Customization** | Easy | Complex (overrides) | Easy |
| **Database Size** | Larger | Smaller | Larger |
| **Implementation Complexity** | Medium | High | Medium |
| **Recommended?** | ✅ **Yes** | ⚠️ Maybe | ✅ **Yes** |

---

## 💡 Recommendation

### For Workflow Templates: **Option 1 (Copy-on-Enable)** or **Option 3 (Hybrid)**

**Why?**
- Templates are relatively small (JSONB config, ~5-20KB each)
- Stability is more important than saving space (users need consistent workflows)
- Clear audit trail (know exactly what config was used)
- Simple to implement and reason about

**Implementation Priority:**
1. Create `workflow_templates` table
2. Add `template_id` column to `persona_workflows`
3. Build template repository (CRUD operations)
4. Create ONE base "CPA Lead Capture" template (generic config)
5. Build template library API (list, enable, customize)
6. Add tier-based access control (check `minimum_plan_tier_id` FK to tier_plans)

### For LiveKit Integration: **Option B (Dual-Mode Agent)**

**Why?**
- More flexible - user can chat OR do workflow
- Seamless transition between modes
- Reuses existing LiveKit infrastructure
- Can detect workflow triggers naturally in conversation

**Implementation Priority:**
1. Add workflow mode to existing PersonaVoiceAgent
2. Implement workflow trigger detection
3. Connect ConversationalWorkflowExecutor to LiveKit agent
4. Add voice-specific response formatting
5. Test voice-based field extraction accuracy

---

## 🚀 Implementation Phases

### Phase 1: Template System (Backend)
- [x] Create `workflow_templates` migration
- [x] Add `template_id` and `is_template_customized` to `persona_workflows` ORM model
- [x] Build template repository (CRUD operations)
- [x] Create ONE base "CPA Lead Capture" template seed/migration
  - Generic fields: contact_name, email, phone, state, service_need, timeline
  - Base scoring: 50 + field completeness
  - No firm-specific fields (those are added by customization)
- [x] Add tier-based access control middleware (check `minimum_plan_tier_id` FK to tier_plans)

### Phase 2: Template API
- [x] GET /api/templates (list available templates with tier filtering & legacy tier exclusion)
- [x] GET /api/templates/{template_id} (get single template with tier validation)
- [x] POST /api/templates/{template_id}/enable (enable template for persona)
- [x] PUT /api/templates/{template_id}/customize (customize template-based workflow)
- [x] GET /api/templates/{template_id}/sync-status (check for template updates)
- [x] POST /api/templates/{template_id}/sync (sync workflow with latest template version)

### Phase 3: LiveKit Integration
- [ ] Extend PersonaVoiceAgent with workflow mode
- [ ] Add workflow trigger detection
- [ ] Connect ConversationalWorkflowExecutor to voice agent
- [ ] Add TTS formatting for conversational workflow responses
- [ ] Test voice-based field extraction with real audio

### Phase 4: Frontend (Dashboard)
- [ ] Template library UI
- [ ] Template preview modal
- [ ] Enable/disable template for persona
- [ ] Template customization editor
- [ ] Template update notifications

---

## ❓ Open Questions for Discussion

1. **Base Template Scope**: What should the base "CPA Lead Capture" template contain?
   - Minimum fields: contact_name, email, phone, state?
   - Should it include ANY optional fields, or start completely minimal?
   - Should base scoring be just 50 + field completeness, or include generic signals?

2. **Template Versioning**: Should we support multiple versions of same template (e.g., CPA Lead Capture v1, v2, v3)?

3. **Template Sharing**: Should users be able to create their own templates and share with other users?
   - For now: Admin-managed only
   - Future: User-created templates?

4. **Template Pricing**: Is `minimum_plan_tier_id=3` (enterprise) sufficient, or do we need per-template pricing?

5. **LiveKit Workflow Triggers**: How should we detect when user wants to start a workflow vs normal chat?
   - Explicit phrase: "I want to get qualified"
   - Implicit: User asks about services → Agent offers workflow
   - Manual: User clicks button in UI to start workflow call

6. **Voice Confirmation Flow**: How to handle Phase 3 confirmation flow in voice?
   - Read entire summary, then ask "Is this correct?"
   - Read field-by-field with pauses for confirmation?
   - Hybrid: Summary + highlight critical fields?

7. **Template Updates**: When admin updates template, what happens to in-progress sessions using old version?
   - Complete with old version
   - Migrate to new version mid-session
   - Invalidate and restart

---

## 📝 Summary of Schema Design Decisions

Based on discussion, here are the finalized schema decisions:

### ✅ Kept Fields
1. **`template_key`** (VARCHAR): Stable identifier for code/migrations
   - Example: `'cpa_lead_capture'`
   - Easier to reference than UUID in code and logs

2. **`minimum_plan_tier_id`** (INTEGER, FK): Tier-based access control via foreign key
   - Foreign key to `tier_plans(id)` table
   - Values: 0=free, 1=pro, 2=business, 3=enterprise (highest tier)
   - **Important**: Enterprise (tier_id=3) is the highest tier despite legacy tiers (4+) having higher IDs
   - **Legacy tier exclusion**: Users with tier_id >= 4 are excluded from template access entirely
   - More maintainable than string values (single source of truth)

3. **`tags`** (TEXT[]): Search/filtering in template library UI
   - Example: `['cpa', 'tax', 'lead-capture']`
   - Optional, can be empty array

4. **`preview_image_url`** (TEXT): Screenshot for template gallery
   - Optional, nullable
   - Can be added later when building frontend

### ❌ Removed Fields
1. **`is_enterprise_only`** (BOOLEAN): Redundant with tier-based access control
   - Using `minimum_plan_tier_id` FK provides more granular control
   - Removing reduces confusion and maintains normalization

### 🔄 Migration from Original Design
**Original**: `minimum_plan_tier VARCHAR(50)` with string values ('free', 'professional', 'enterprise')
**Updated**: `minimum_plan_tier_id INTEGER` with FK to `tier_plans(id)` table
- Ensures referential integrity
- Prevents invalid tier values
- Single source of truth for tier hierarchy
- Supports tier hierarchy logic (enterprise is top tier, legacy tiers excluded)

---

**Next Steps:** Please review this proposal and let me know:
1. Which template architecture option you prefer (1, 2, or 3)?
2. Which LiveKit integration approach (A or B)?
3. What should the base "CPA Lead Capture" template contain? (See Open Question #1)
4. Any adjustments to the implementation phases?
5. Answers to the other open questions above

Then we can start implementing! 🚀
