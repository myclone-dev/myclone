# LiveKit Agent Test Scenarios

This document tracks all test scenarios for the CPA Lead Capture workflow, their expected behavior, and actual results.

**Last Updated:** January 28, 2026  
**Current Test Count:** 87 (all passing)  
**Target Test Count:** 110+

---

## Executive Summary

### Current State
- ✅ Basic field extraction - fully tested
- ✅ Correction detection - fully tested
- ✅ Lead scoring - 27 unit tests
- ✅ Quality signals & risk penalties - config-driven, tested
- ✅ Confirmation flow - 3 integration tests
- ✅ Follow-up questions - 2 integration tests
- ✅ Inference rules - 7 integration tests
- ✅ **Hallucination controls - 14 tests (7 unit + 5 integration + 2 uncertainty)**
- ⚠️ Summary templates - not customizable (hardcoded)
- ⚠️ No redundant questions - not implemented
- ⚠️ Tone controls - not implemented

### Gap Summary

| Category | Status | Priority |
|----------|--------|----------|
| **Hallucination Controls** | ✅ **Implemented + Tested** | 🔴 P1 ✅ |
| Summary Templates | ❌ Not implemented | 🔴 P1 |
| No Redundant Questions | ❌ Not implemented | 🔴 P1 |
| Tone Controls | ❌ Not implemented | 🟡 P2 |
| Mode Toggle (Lead/Support) | ❌ Not implemented | 🟡 P2 |
| Admin Dashboard | ❌ Not implemented | 🟢 P3 |

---

## Test Configuration

- **Model**: `gpt-4.1-mini`
- **Workflow Type**: Conversational Lead Capture
- **Required Fields**: contact_name, contact_email, contact_phone, service_need
- **Optional Fields**: state, timeline

---

## Test Categories

### 1. Basic Lead Capture (`TestBasicLeadCapture`)

#### 1.1 Extract Name from Introduction
| Scenario | User Input | Expected Behavior | Actual Result |
|----------|-----------|-------------------|---------------|
| User introduces themselves with service need | "Hi, I'm John Smith and I need help with my taxes." | Extract name + service_need, ask for email | ✅ PASS - Captured `contact_name: John Smith`, `service_need: help with taxes`, asked for email |

#### 1.2 Extract Multiple Fields from Single Message
| Scenario | User Input | Expected Behavior | Actual Result |
|----------|-----------|-------------------|---------------|
| User provides name, email, phone together | "I'm Jane Doe, my email is jane@example.com and my phone is 555-123-4567" | Extract all 3 fields | ✅ PASS - Captured name, email, phone in parallel |

#### 1.3 Full Lead Capture Flow
| Scenario | User Inputs | Expected Behavior | Actual Result |
|----------|------------|-------------------|---------------|
| Multi-turn complete flow | Turn 1: "Hi, I'm John Smith. My email is john@acme.com"<br>Turn 2: "My phone number is 555-987-6543"<br>Turn 3: "I need help with quarterly tax filings" | Capture all 4 required fields across turns | ✅ PASS - All fields captured progressively |

---

### 2. Field Correction (`TestFieldCorrection`)

#### 2.1 User Corrects Email
| Scenario | User Inputs | Expected Behavior | Actual Result |
|----------|------------|-------------------|---------------|
| User provides email then corrects it | Turn 1: "I'm John Smith, email john@test.com"<br>Turn 2: "Actually, my email is johnsmith@company.com" | Update email to corrected value | ✅ PASS - Email updated to corrected version |

---

### 3. Multi-Turn Without Service Mention (`TestMultiTurnWithoutServiceMention`)

#### 3.1 Agent Asks About Service Need When Not Mentioned
| Scenario | User Inputs | Expected Behavior | Actual Result |
|----------|------------|-------------------|---------------|
| User provides contact info but never says what they need | Turn 1: "Hi there!"<br>Turn 2: "I'm Michael Johnson, my email is michael@techstartup.com"<br>Turn 3: "My phone is 555-888-9999" | Capture contact info, ask about service_need | ✅ PASS - Agent asked "Thanks for that! Lastly, what kind of service do you need assistance with?" |

**Detailed Results:**
```
Turn 1: User: "Hi there!"
        Agent: "Hello! How can I assist you today?"
        Captured: (none)

Turn 2: User: "I'm Michael Johnson, my email is michael@techstartup.com"
        Agent: Captured name + email
        Agent: "Great to meet you, Michael! What phone number can I reach you at?"
        Captured: contact_name, contact_email

Turn 3: User: "My phone is 555-888-9999"
        Agent: Captured phone
        Agent: "Thanks for that! Lastly, what kind of service do you need assistance with?"
        Captured: contact_name, contact_email, contact_phone
        NOT captured: service_need (correctly missing)
```

#### 3.2 Casual Conversation Without Service Details
| Scenario | User Inputs | Expected Behavior | Actual Result |
|----------|------------|-------------------|---------------|
| User has small talk then provides contact info | Turn 1: "Hey, how's it going?"<br>Turn 2: "Yeah, busy week for me too"<br>Turn 3: "Anyway, I'm David Chen, david.chen@gmail.com, call me at 415-555-1234" | Capture contact info, NOT fabricate service_need | ✅ PASS - Captured 3 contact fields, did NOT hallucinate service_need |

#### 3.3 User Provides Everything Except Service
| Scenario | User Input | Expected Behavior | Actual Result |
|----------|-----------|-------------------|---------------|
| User dumps all contact info but no service | "Hi, I'm Lisa Park, lisa.park@example.com, 650-123-4567" | Capture all contact info, ask about service | ✅ PASS - Agent asked "Nice to meet you, Lisa! Thanks for sharing your contact details. Now, could you let me know what specific service you're looking for?" |

---

### 4. Edge Cases (`TestEdgeCases`)

#### 4.1 Agent Asks Clarifying Questions
| Scenario | User Input | Expected Behavior | Actual Result |
|----------|-----------|-------------------|---------------|
| Vague initial message | "Hi, I need help with my taxes" | Respond and engage | ✅ PASS - Agent responded with message |

#### 4.2 Agent Handles Refusal Gracefully
| Scenario | User Inputs | Expected Behavior | Actual Result |
|----------|------------|-------------------|---------------|
| User refuses to provide phone | Turn 1: "I'm John Smith, john@test.com"<br>Turn 2: "I'd rather not give my phone number" | Continue conversation without crashing | ✅ PASS - Agent acknowledged and continued |

---

### 5. Message Content (`TestMessageContent`)

#### 5.1 Professional Response
| Scenario | User Input | Expected Behavior | Actual Result |
|----------|-----------|-------------------|---------------|
| User asks for help | "Hi, I need help with my taxes" | Respond professionally | ✅ PASS - Agent responded with message |

#### 5.2 Non-Interrogative Behavior
| Scenario | User Input | Expected Behavior | Actual Result |
|----------|-----------|-------------------|---------------|
| User expresses interest | "I'm interested in your tax services" | Ask ONE question, not all fields at once | ✅ PASS - Agent asked only for name |

---

## 6. Lead Scoring (`TestScoringEngine` - Unit Tests)

### Test File: `livekit/tests/unit/test_scoring_engine.py`

#### 6.1 Base Score
| Scenario | Input | Expected | Status |
|----------|-------|----------|--------|
| Default base score | No `base_score` in rules | 50 | ✅ PASS |
| Custom base score | `base_score: 40` | 40 | ✅ PASS |

#### 6.2 Field Completeness Bonus
| Scenario | Optional Fields Captured | Expected Bonus | Status |
|----------|-------------------------|----------------|--------|
| No optional fields | 0 of 7 | 0 | ✅ PASS |
| Half optional fields | 3 of 7 | ~8.5 (43% of 20) | ✅ PASS |
| All optional fields | 7 of 7 | 20 | ✅ PASS |

#### 6.3 Quality Signals (Config-Driven)
| Scenario | Trigger | Points | Status |
|----------|---------|--------|--------|
| No signals triggered | revenue: $100K, timeline: no rush | 0 | ✅ PASS |
| Revenue $1M+ | revenue_range contains "$1M" | +15 | ✅ PASS |
| Urgent timeline | timeline contains "ASAP" | +10 | ✅ PASS |
| Foreign accounts | foreign_accounts field exists | +15 | ✅ PASS |
| S-Corp entity | entity_type equals "S-Corp" | +5 | ✅ PASS |
| Multiple signals stacked | All of above | +45 | ✅ PASS |

#### 6.4 Risk Penalties (Config-Driven)
| Scenario | Trigger | Points | Status |
|----------|---------|--------|--------|
| No penalties triggered | red_flags: None | 0 | ✅ PASS |
| Unfiled returns | red_flags contains "unfiled" | -20 | ✅ PASS |
| IRS notice | red_flags contains "irs notice" | -15 | ✅ PASS |
| Messy bookkeeping | bookkeeping_status contains "behind" | -10 | ✅ PASS |
| Multiple penalties stacked | All of above | -45 | ✅ PASS |

#### 6.5 Priority Classification
| Scenario | Score Range | Priority | Status |
|----------|-------------|----------|--------|
| High priority | >= 80 | "high" | ✅ PASS |
| Medium priority | 60-79 | "medium" | ✅ PASS |
| Low priority | < 60 | "low" | ✅ PASS |

#### 6.6 Total Score Calculation
| Scenario | Calculation | Expected | Status |
|----------|-------------|----------|--------|
| Basic (base + completeness) | 50 + 20 | 70 | ✅ PASS |
| With quality signals | 50 + 2.8 + 15 | ~67.8 | ✅ PASS |
| With penalties | 50 + 2.8 - 20 | ~32.8 | ✅ PASS |
| Clamped to 100 max | 50 + 20 + 45 | 100 (not 115) | ✅ PASS |
| Clamped to 0 min | Heavy penalties | >= 0 | ✅ PASS |

#### 6.7 Real-World Scenarios
| Scenario | Lead Profile | Expected Score | Expected Priority | Status |
|----------|--------------|----------------|-------------------|--------|
| **High-Value Lead** | $2M revenue, S-Corp, urgent, foreign accounts | 100 | high | ✅ PASS |
| **Risky Lead** | Unfiled returns, IRS notice, messy books | < 50 | low | ✅ PASS |
| **Medium Lead** | $500K revenue, no special flags | 60-79 | medium | ✅ PASS |

---

## Test Coverage Analysis

### Implemented & Tested ✅

| Feature | Architecture Status | Test Coverage | Status |
|---------|---------------------|---------------|--------|
| Basic field extraction | ✅ Implemented | ✅ Unit + Integration | COVERED |
| Multi-field extraction | ✅ Implemented | ✅ Integration | COVERED |
| Correction detection | ✅ Implemented | ✅ Unit + Integration | COVERED |
| Lead scoring | ✅ Implemented | ✅ 27 Unit Tests | COVERED |
| Quality signals | ✅ Implemented | ✅ 6 Unit Tests | COVERED |
| Risk penalties | ✅ Implemented | ✅ 5 Unit Tests | COVERED |
| Priority classification | ✅ Implemented | ✅ 3 Unit Tests | COVERED |
| Confirmation flow | ✅ Implemented | ✅ 3 Integration Tests | COVERED |
| Follow-up questions | ✅ Implemented | ✅ 2 Integration Tests | COVERED |
| Inference rules | ✅ Implemented | ✅ 7 Integration Tests | COVERED |

### Implemented (NEW)

| Feature | Architecture Status | Test Coverage | Priority |
|---------|---------------------|---------------|----------|
| **Hallucination controls** | ✅ **Implemented** | ✅ **14 tests** | 🔴 P1 ✅ |

### Not Yet Implemented ❌

| Feature | Architecture Status | Test Coverage | Priority |
|---------|---------------------|---------------|----------|
| No redundant questions | ❌ Not implemented | ❌ 0 tests | 🔴 P1 |
| Summary templates | ❌ Not implemented | ❌ 0 tests | 🔴 P1 |
| Tone controls | ❌ Not implemented | ❌ 0 tests | 🟡 P2 |
| Mode toggle | ❌ Not implemented | ❌ 0 tests | 🟡 P2 |

---

## 7. Confirmation Flow (`TestConfirmationFlow`)

### Test File: `livekit/tests/integration/test_cpa_lead_capture.py`

#### 7.1 Confirmation Shown When All Fields Captured
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| User provides all required info | "John Smith, john@example.com, 555-123-4567, quarterly taxes" | Agent shows confirmation, awaiting confirmation | ✅ PASS |

#### 7.2 User Confirms Workflow Completes
| Scenario | User Inputs | Expected | Status |
|----------|------------|----------|--------|
| User confirms | Turn 1: All info, Turn 2: "Yes, that's correct" | Workflow status = completed or awaiting_confirmation | ✅ PASS |

#### 7.3 User Rejects Allows Correction
| Scenario | User Inputs | Expected | Status |
|----------|------------|----------|--------|
| User corrects email | Turn 1: Info with old email, Turn 2: "No, my email is actually..." | Email updated | ✅ PASS |

---

## 8. Follow-Up Questions (`TestFollowUpQuestions`)

### Test File: `livekit/tests/integration/test_cpa_lead_capture.py`

#### 8.1 Foreign Accounts Triggers FBAR Question
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| User mentions foreign accounts | "I have bank accounts in Japan" | FBAR follow-up question generated | ✅ PASS |

#### 8.2 S-Corp Triggers Salary Question
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| User mentions S-Corp | "We're an S-Corp" | Reasonable salary follow-up question | ✅ PASS |

---

## 9. Inference Rules (`TestInferenceRules`)

### Test File: `livekit/tests/integration/test_cpa_lead_capture.py`

Tests for intelligent field inference from context clues.

#### 9.1 City to State Inference - Austin → Texas
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| User mentions Austin | "I'm based in Austin" | state = Texas (confidence >= 0.7) | ✅ PASS |

**Detailed Result:**
```
Extracted: state='Texas', confidence=0.95, extraction_method='direct_statement'
```

#### 9.2 City to State Inference - Chicago → Illinois
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| User mentions Chicago | "My business is headquartered in Chicago" | state = Illinois/IL | ✅ PASS |

**Detailed Result:**
```
Extracted: state='IL', confidence=0.9, extraction_method='natural_language'
```

#### 9.3 Timeline Inference - ASAP → Immediate
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| User says ASAP | "I need this done ASAP" | timeline = Immediate | ✅ PASS |

**Detailed Result:**
```
Extracted: timeline='Immediate', confidence=0.8, extraction_method='inference'
```

#### 9.4 Timeline Inference - Exploring → Just exploring
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| User says no rush | "I'm just exploring options. No rush" | timeline = Just exploring | ✅ PASS |

**Detailed Result:**
```
Extracted: timeline='Just exploring', confidence=0.85, extraction_method='natural_language'
```

#### 9.5 Name Extraction from Introduction
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| User introduces self | "This is Maria Garcia reaching out" | contact_name = Maria Garcia (confidence >= 0.85) | ✅ PASS |

**Detailed Result:**
```
Extracted: contact_name='Maria Garcia', confidence=1.0, extraction_method='direct_statement'
```

#### 9.6 Extraction Method Labeled Correctly
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| Inferred value | "I run my business out of Denver" | extraction_method in ['inference', 'natural_language'] | ✅ PASS |

#### 9.7 No Inference When Not Mentioned
| Scenario | User Input | Expected | Status |
|----------|-----------|----------|--------|
| No location mentioned | "I'm John and I need help with my taxes" | state NOT extracted, in missing_optional | ✅ PASS |

---

## Pending Test Scenarios

### Priority 1: Critical (Must Have)

#### Advice Redirect (`TestAdviceRedirect`) - ✅ IMPLEMENTED (Config-Driven)

**Implementation:** Patterns are now stored in `extraction_strategy.advice_redirect` config.
See `docs/workflows/WORKFLOW_ENHANCEMENTS.md` for full documentation.

**Unit Tests (7 tests)** - `TestAdviceRedirect`:
| ID | Scenario | Status |
|----|----------|--------|
| AR-1 | Detect entity choice question ("S-Corp or LLC?") | ✅ PASS |
| AR-2 | Detect FBAR question | ✅ PASS |
| AR-3 | Detect deduction question | ✅ PASS |
| AR-4 | Detect deadline question | ✅ PASS |
| AR-5 | Detect tax liability question | ✅ PASS |
| AR-6 | NOT detect normal messages | ✅ PASS |
| AR-7 | Empty patterns never matches | ✅ PASS |

**Unit Tests (2 tests)** - `TestUncertaintyHandling`:
| ID | Scenario | Status |
|----|----------|--------|
| HC-U8 | Get uncertainty prefix | ✅ PASS |
| HC-U9 | Build uncertainty clarification | ✅ PASS |

**Integration Tests (5 tests)** - `TestHallucinationControls`:
| ID | Scenario | User Input | Expected Behavior | Status |
|----|----------|------------|-------------------|--------|
| HC-1 | Don't fabricate revenue | No revenue mentioned | revenue_range = NULL | ✅ PASS |
| HC-2 | Don't fabricate entity | No entity mentioned | entity_type = NULL | ✅ PASS |
| HC-3 | Don't fabricate service need | Contact info only | service_need = NULL | ✅ PASS |
| HC-4 | Low confidence = no extraction | Ambiguous business | entity_type NOT extracted | ✅ PASS |
| HC-5 | Explicit entity SHOULD extract | "We're an S-Corp" | entity_type = S-Corp | ✅ PASS |

#### No Redundant Questions (`TestNoRedundantQuestions`) - 4 tests needed

| ID | Scenario | User Inputs | Expected Behavior | Status |
|----|----------|-------------|-------------------|--------|
| NR-1 | Email already provided | T1: "I'm John, john@test.com" | Agent asks for phone, NOT email | ❌ TODO |
| NR-2 | All contact in one message | "John Smith, john@test.com, 555-1234" | Agent asks for service_need only | ❌ TODO |
| NR-3 | Rich initial message | "Sarah, S-Corp in CA, $2M rev, sarah@co.com" | Agent asks for phone only | ❌ TODO |
| NR-4 | Progressive capture | T1: name, T2: email, T3: phone | Never re-asks for earlier fields | ❌ TODO |

#### Summary Templates (`TestSummaryTemplates`) - 6 tests needed

| ID | Scenario | Config | Expected Output | Status |
|----|----------|--------|-----------------|--------|
| ST-1 | Structured template (default) | `summary_template: "structured"` | LEAD, CONTACT, PROFILE, SCORE sections | ❌ TODO |
| ST-2 | Synopsis template (LST) | `summary_template: "synopsis"` | SYNOPSIS, KEY DETAILS, Q&A sections | ❌ TODO |
| ST-3 | Minimal template | `summary_template: "minimal"` | Name, contact, score only | ❌ TODO |
| ST-4 | Detailed with transcript | `summary_template: "detailed"` | All sections + full transcript | ❌ TODO |
| ST-5 | Custom sections override | `sections_override: [...]` | Only specified sections | ❌ TODO |
| ST-6 | Backward compatibility | No template specified | Default to "structured" | ❌ TODO |

---

### Priority 2: Important (Should Have)

#### Tone Controls (`TestToneControls`) - 4 tests needed

| ID | Scenario | Config | Expected Behavior | Status |
|----|----------|--------|-------------------|--------|
| TC-1 | Concierge greeting | `tone: "concierge"` | Warm welcome, uses persona name | ❌ TODO |
| TC-2 | Concierge acknowledgment | `tone: "concierge"` | "Wonderful, thank you" not "Got it" | ❌ TODO |
| TC-3 | Avoid AI phrases | Any tone | Never says "As an AI" | ❌ TODO |
| TC-4 | Professional tone | `tone: "professional"` | Formal but approachable | ❌ TODO |

#### Additional Inference Rules - 5 tests needed

| ID | User Input | Expected Extraction | Status |
|----|------------|---------------------|--------|
| IR-8 | "Located in Seattle" | state: Washington | ❌ TODO |
| IR-9 | "Calling from Miami" | state: Florida | ❌ TODO |
| IR-10 | "We're an LLC" | entity_type: LLC | ❌ TODO |
| IR-11 | "Incorporated in Delaware" | entity_type: C-Corp | ❌ TODO |
| IR-12 | "It's just me, freelancer" | entity_type: Sole Proprietor | ❌ TODO |

---

### Priority 3: Nice to Have

#### End-to-End Workflows (`TestEndToEnd`) - 5 tests needed

| ID | Scenario | Expected Score | Expected Priority | Status |
|----|----------|----------------|-------------------|--------|
| E2E-1 | Happy path - basic lead | ~55 | low | ❌ TODO |
| E2E-2 | Happy path - high value lead | 95-100 | high | ❌ TODO |
| E2E-3 | Happy path - risk lead | 15-30 | low | ❌ TODO |
| E2E-4 | Full flow with correction | Varies | Varies | ❌ TODO |
| E2E-5 | Multi-turn progressive capture | Varies | Varies | ❌ TODO |

#### Advanced Edge Cases (`TestAdvancedEdgeCases`) - 5 tests needed

| ID | Scenario | User Input | Expected Behavior | Status |
|----|----------|------------|-------------------|--------|
| EC-1 | Multiple corrections | Corrects name, email, phone | All corrections applied | ❌ TODO |
| EC-2 | 6-turn conversation | Gradual info reveal | Progressive capture → complete | ❌ TODO |
| EC-3 | Verbose/rambling user | 200-word message | Extracts relevant fields | ❌ TODO |
| EC-4 | Minimal one-word answers | "John", "john@test.com" | Captures despite minimal info | ❌ TODO |
| EC-5 | Optional before required | "S-Corp in CA doing $2M" | Captures optional, asks required | ❌ TODO |

---

### Test Gap Summary

| Category | Current | Needed | Gap |
|----------|---------|--------|-----|
| Hallucination Controls | ✅ 14 | 14 | ✅ Done |
| No Redundant Questions | 0 | 4 | +4 |
| Summary Templates | 0 | 6 | +6 |
| Tone Controls | 0 | 4 | +4 |
| Additional Inference | 7 | 12 | +5 |
| End-to-End | 0 | 5 | +5 |
| Advanced Edge Cases | 0 | 5 | +5 |
| **Total** | **87** | **110** | **+23** |

---

## Test Execution

### Run All Tests
```bash
poetry run pytest livekit/tests/ -v
```

### Run Only Integration Tests (with verbose output)
```bash
LIVEKIT_EVALS_VERBOSE=1 poetry run pytest livekit/tests/integration/ -v -s
```

### Run Specific Test Class
```bash
LIVEKIT_EVALS_VERBOSE=1 poetry run pytest livekit/tests/integration/test_cpa_lead_capture.py::TestMultiTurnWithoutServiceMention -v -s
```

### Run Only Unit Tests (no API key needed)
```bash
poetry run pytest livekit/tests/unit/ -v
```

---

## Test Statistics

### Current Tests (87 total)

| Category | Tests | Status |
|----------|-------|--------|
| Unit Tests - Conversational Handler | 21 | ✅ All Pass |
| Unit Tests - Scoring Engine | 27 | ✅ All Pass |
| **Unit Tests - Advice Redirect** | **7** | ✅ All Pass |
| **Unit Tests - Uncertainty Handling** | **2** | ✅ All Pass |
| Integration Tests - Basic Lead Capture | 11 | ✅ All Pass |
| Integration Tests - Confirmation Flow | 3 | ✅ All Pass |
| Integration Tests - Scoring Integration | 2 | ✅ All Pass |
| Integration Tests - Follow-Up Questions | 2 | ✅ All Pass |
| Integration Tests - Inference Rules | 7 | ✅ All Pass |
| **Integration Tests - Hallucination Controls** | **5** | ✅ All Pass |
| **Total Implemented** | **87** | **✅ All Pass** |

### Pending Tests (23 needed)

| Category | Tests Needed | Priority |
|----------|--------------|----------|
| ~~Hallucination Controls~~ | ~~8~~ | ✅ Done |
| No Redundant Questions | 4 | 🔴 P1 |
| Summary Templates | 6 | 🔴 P1 |
| Tone Controls | 4 | 🟡 P2 |
| Additional Inference Rules | 5 | 🟡 P2 |
| End-to-End Workflows | 5 | 🟢 P3 |
| Advanced Edge Cases | 5 | 🟢 P3 |
| **Total Pending** | **23** | -- |

### Progress

```
Current:  87 tests ██████████████████████████░░░░ 79%
Target:  110 tests ██████████████████████████████ 100%
```

*Last updated: January 28, 2026*

---

## Notes

- Integration tests require `OPENAI_API_KEY` (loaded from `.env`)
- Tests use `gpt-4.1-mini` model for cost efficiency
- LLM behavior may vary slightly between runs due to non-determinism
- Set `LIVEKIT_EVALS_VERBOSE=1` to see detailed agent events

---

## Implementation Notes

### Completed Features ✅

1. **Advice Redirect System (P1)** - ✅ IMPLEMENTED (Config-Driven)
   - ✅ Layer 1: Strengthened extraction prompt to prevent fabrication
   - ✅ Layer 2: Config-driven advice detection with redirect
   - ✅ Layer 3: Uncertainty handling with clarifying prefixes
   - ✅ Config: `advice_redirect` in `extraction_strategy` (see `docs/workflows/WORKFLOW_ENHANCEMENTS.md`)
   - ✅ Migration: `a1b2c3d4e5f6_add_advice_redirect_to_cpa_template.py`
   - Files modified: `workflow_field_extractor.py`, `conversational_workflow_coordinator.py`, `cpa_workflow.py`
   - **Future:** LLM-generated patterns endpoint (see WORKFLOW_ENHANCEMENTS.md)

### Features Requiring Code Changes (Before Tests)

The following pending tests require **feature implementation** before tests can be written:

1. **No Redundant Questions (P1)**
   - Track `asked_fields` in session metadata
   - Skip already-captured fields when generating questions

2. **Summary Templates (P1)**
   - Add `summary_template` field to `OutputTemplate` model
   - Implement template renderers: structured, synopsis, minimal, detailed
   - Files: `app/api/models/workflow_models.py`, new `summary_formatter.py`

3. **Tone Controls (P2)**
   - Add `tone` field to extraction strategy config
   - Implement tone presets: concierge, professional, casual
   - Update response generation to use tone templates

---

## Adding New Scenarios

1. Add scenario to "Pending Test Scenarios" section with status ❌ TODO
2. If feature exists: implement test in `livekit/tests/integration/test_cpa_lead_capture.py`
3. If feature missing: implement feature first, then test
4. Run test and update status to ✅ PASS
5. Move to appropriate "Implemented" section once passing
