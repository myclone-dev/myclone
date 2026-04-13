"""
Lead Scoring Service - LLM-based lead evaluation with consistent JSON schema

This is the SINGLE SOURCE OF TRUTH for lead scoring and summary generation.
Replaces the old rule-based scoring + separate enrichment approach.

WHY LLM-ONLY:
- Rule-based scoring is brittle ("Immediate" vs "immediately" vs "ASAP")
- LLM understands intent and nuance in free-form text
- Single source of truth - no conflicting scores
- Structured JSON output for easy frontend rendering

WORKFLOW-AWARE:
- Accepts scoring_rules from workflow template
- LLM evaluates against SPECIFIC quality signals and risk penalties
- Generates follow-up questions based on workflow config

CONSISTENT OUTPUT:
- Uses Pydantic models to guarantee schema consistency
- Frontend always receives the same JSON structure
- Validation ensures all required fields are present

FLOW:
1. Workflow completes → extracted_fields saved
2. Background task fires → LLM evaluates lead
3. Returns structured JSON: score, summary, signals, follow-up questions
4. result_data updated with complete evaluation

USAGE:
    service = LeadScoringService()
    result = await service.evaluate_lead(
        extracted_fields={"contact_name": {"value": "John"}, ...},
        workflow_context={
            "template_name": "CPA Lead Capture",
            "scoring_rules": {...},
            "output_config": {...}
        }
    )
    # result is a validated LeadEvaluationResult
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Consistent Schema
# =============================================================================


class LeadContact(BaseModel):
    """Contact information extracted from lead."""

    name: str = Field(..., description="Full name of the lead")
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")


class SignalMatched(BaseModel):
    """A quality signal that was matched for this lead."""

    signal_id: str = Field(..., description="ID of the signal from scoring_rules")
    points: int = Field(..., description="Points awarded for this signal")
    reason: str = Field(..., description="Why this signal was matched")


class PenaltyApplied(BaseModel):
    """A risk penalty that was applied to this lead."""

    penalty_id: str = Field(..., description="ID of the penalty from scoring_rules")
    points: int = Field(..., description="Points deducted for this penalty")
    reason: str = Field(..., description="Why this penalty was applied")


class LeadScoring(BaseModel):
    """Detailed scoring breakdown."""

    score: int = Field(..., ge=0, le=100, description="Lead score 0-100")
    priority: Literal["high", "medium", "low"] = Field(..., description="Priority level")
    signals_matched: List[SignalMatched] = Field(
        default_factory=list, description="Quality signals that matched"
    )
    penalties_applied: List[PenaltyApplied] = Field(
        default_factory=list, description="Risk penalties that were applied"
    )
    reasoning: str = Field(..., description="Brief explanation of the score")


class LeadSummary(BaseModel):
    """Structured lead summary for frontend rendering."""

    contact: LeadContact = Field(..., description="Contact information")
    service_need: str = Field(..., description="What service the lead needs")
    additional_info: Dict[str, str] = Field(
        default_factory=dict, description="Additional captured fields (state, timeline, etc.)"
    )
    follow_up_questions: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions for the expert",
        max_length=5,
    )


class LeadEvaluationResult(BaseModel):
    """
    Complete lead evaluation result with consistent schema.

    This is what gets stored in result_data and sent to the frontend.
    """

    # Core assessment
    lead_score: int = Field(..., ge=0, le=100, description="Overall lead score 0-100")
    priority_level: Literal["high", "medium", "low"] = Field(
        ..., description="Recommended follow-up priority"
    )
    lead_quality: Literal["hot", "warm", "cold"] = Field(
        ..., description="Overall lead quality assessment"
    )
    urgency_level: Literal["high", "medium", "low"] = Field(
        ..., description="How urgent is the lead's need"
    )

    # Structured data for frontend
    lead_summary: LeadSummary = Field(..., description="Structured lead summary")
    scoring: LeadScoring = Field(..., description="Detailed scoring breakdown")

    # Metadata
    confidence: float = Field(default=0.8, ge=0, le=1, description="Confidence in this evaluation")
    evaluated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="When evaluation was performed",
    )

    @field_validator("lead_score", "scoring", mode="before")
    @classmethod
    def sync_score(cls, v, info):
        """Ensure lead_score and scoring.score are consistent."""
        return v


# =============================================================================
# Lead Scoring Service
# =============================================================================


class LeadScoringService:
    """
    LLM-based lead evaluation service.

    Generates lead score, summary, and follow-up questions using a single
    LLM call with structured output validation.
    """

    SYSTEM_PROMPT = """You are an expert lead qualification assistant. Your job is to analyze captured lead information and provide a complete evaluation.

You must evaluate:
1. LEAD SCORE (0-100): Based on quality signals matched and penalties applied
2. PRIORITY LEVEL: high (score >= 80), medium (score 60-79), low (score < 60)
3. LEAD QUALITY: hot (urgent + complete info + signals), warm (good but not urgent), cold (incomplete/vague)
4. URGENCY: high (deadline pressure, emergency), medium (soon), low (exploring)

SCORING GUIDELINES:
- Start with a base score of 50
- Add points for quality signals matched
- Subtract points for risk penalties
- Add up to 20 points for field completeness (all optional fields captured)
- Final score should be 0-100

FOLLOW-UP QUESTIONS:
Generate 2-4 relevant follow-up questions the expert should ask to better qualify or serve this lead.

RESPONSE FORMAT:
You must respond with a valid JSON object matching the exact schema provided."""

    WORKFLOW_CONTEXT_PROMPT = """
WORKFLOW: {template_name}

QUALITY SIGNALS TO LOOK FOR (add points if matched):
{quality_signals}

RISK PENALTIES TO CHECK (subtract points if matched):
{risk_penalties}

Use the signal_id and penalty_id in your signals_matched and penalties_applied arrays."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the scoring service."""
        self.api_key = api_key or settings.openai_api_key
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.logger = logging.getLogger(__name__)
        self.model = "gpt-4o-mini"

    async def evaluate_lead(
        self,
        extracted_fields: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> LeadEvaluationResult:
        """
        Evaluate a lead using LLM with structured output.

        Args:
            extracted_fields: Captured lead data (field_id -> {value, confidence, ...})
            workflow_context: Workflow configuration including:
                - template_name: Name of the workflow
                - scoring_rules: Quality signals and risk penalties
                - output_config: Summary format preferences

        Returns:
            LeadEvaluationResult with consistent schema
        """
        try:
            # Build the prompts
            system_prompt = self._build_system_prompt(workflow_context)
            user_prompt = self._build_user_prompt(extracted_fields, workflow_context)

            workflow_name = (
                workflow_context.get("template_name", "unknown") if workflow_context else "generic"
            )
            self.logger.info(f"🧠 [SCORING] Evaluating lead for workflow: {workflow_name}")

            # Call LLM with JSON schema enforcement
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            # Parse and validate response
            result_text = response.choices[0].message.content
            result_data = json.loads(result_text)

            # Validate with Pydantic
            evaluation = self._parse_llm_response(result_data, extracted_fields)

            self.logger.info(
                f"✅ [SCORING] Lead evaluated: score={evaluation.lead_score}, "
                f"quality={evaluation.lead_quality}, priority={evaluation.priority_level}"
            )

            return evaluation

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            capture_exception_with_context(
                e,
                extra={"response_text": result_text if "result_text" in locals() else None},
                tags={
                    "component": "lead_scoring",
                    "operation": "parse_response",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            return self._default_evaluation(extracted_fields, "Failed to parse LLM response")

        except Exception as e:
            self.logger.error(f"Lead scoring failed: {e}")
            capture_exception_with_context(
                e,
                extra={"extracted_fields_count": len(extracted_fields)},
                tags={
                    "component": "lead_scoring",
                    "operation": "evaluate_lead",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            return self._default_evaluation(extracted_fields, f"Evaluation failed: {str(e)}")

    def _build_system_prompt(self, workflow_context: Optional[Dict[str, Any]]) -> str:
        """Build system prompt with workflow-specific scoring rules."""
        base_prompt = self.SYSTEM_PROMPT

        if workflow_context and workflow_context.get("scoring_rules"):
            scoring_rules = workflow_context["scoring_rules"]
            quality_signals = self._format_signals(scoring_rules.get("quality_signals", []))
            risk_penalties = self._format_penalties(scoring_rules.get("risk_penalties", []))

            workflow_prompt = self.WORKFLOW_CONTEXT_PROMPT.format(
                template_name=workflow_context.get("template_name", "Lead Capture"),
                quality_signals=quality_signals or "None defined",
                risk_penalties=risk_penalties or "None defined",
            )
            return base_prompt + "\n" + workflow_prompt

        return base_prompt

    def _build_user_prompt(
        self,
        extracted_fields: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]],
    ) -> str:
        """Build user prompt with lead data and expected output format."""
        # Format extracted fields
        lead_data = self._format_extracted_fields(extracted_fields)

        # Get max follow-up questions from config
        max_questions = 4
        if workflow_context and workflow_context.get("output_config"):
            max_questions = workflow_context["output_config"].get("max_follow_up_questions", 4)

        return f"""Evaluate this lead and provide a complete assessment.

CAPTURED LEAD DATA:
{lead_data}

Respond with a JSON object in this exact format:
{{
  "lead_score": <number 0-100>,
  "priority_level": "high" | "medium" | "low",
  "lead_quality": "hot" | "warm" | "cold",
  "urgency_level": "high" | "medium" | "low",
  "lead_summary": {{
    "contact": {{
      "name": "<full name>",
      "email": "<email or null>",
      "phone": "<phone or null>"
    }},
    "service_need": "<what they need>",
    "additional_info": {{
      "<field_name>": "<value>",
      ...
    }},
    "follow_up_questions": [
      "<question 1>",
      "<question 2>",
      ... (max {max_questions})
    ]
  }},
  "scoring": {{
    "score": <same as lead_score>,
    "priority": "<same as priority_level>",
    "signals_matched": [
      {{"signal_id": "<id>", "points": <number>, "reason": "<why matched>"}}
    ],
    "penalties_applied": [
      {{"penalty_id": "<id>", "points": <negative number>, "reason": "<why applied>"}}
    ],
    "reasoning": "<1-2 sentence explanation>"
  }},
  "confidence": <0.0-1.0>
}}"""

    def _format_signals(self, signals: List[Dict]) -> str:
        """Format quality signals for the prompt."""
        if not signals:
            return ""
        lines = []
        for s in signals:
            condition = self._describe_condition(s.get("condition", {}))
            lines.append(f"  • {s.get('signal_id')}: +{s.get('points')} points if {condition}")
        return "\n".join(lines)

    def _format_penalties(self, penalties: List[Dict]) -> str:
        """Format risk penalties for the prompt."""
        if not penalties:
            return ""
        lines = []
        for p in penalties:
            condition = self._describe_condition(p.get("condition", {}))
            lines.append(f"  • {p.get('penalty_id')}: {p.get('points')} points if {condition}")
        return "\n".join(lines)

    def _describe_condition(self, condition: Dict[str, Any]) -> str:
        """Convert a condition dict into human-readable description."""
        if "any_of" in condition:
            sub_conditions = [self._describe_condition(c) for c in condition["any_of"]]
            return "ANY of: " + ", ".join(sub_conditions)

        if "all_of" in condition:
            sub_conditions = [self._describe_condition(c) for c in condition["all_of"]]
            return "ALL of: " + ", ".join(sub_conditions)

        field = condition.get("field", "?")
        operator = condition.get("operator", "?")
        value = condition.get("value") or condition.get("values")

        if operator == "exists":
            return f"{field} is provided"
        elif operator == "not_exists":
            return f"{field} is missing"
        elif operator == "equals":
            return f"{field} = '{value}'"
        elif operator in ("in", "in_list"):
            if isinstance(value, list):
                return f"{field} is one of: {', '.join(str(v) for v in value)}"
            return f"{field} in {value}"
        elif operator == "contains":
            return f"{field} contains '{value}'"
        else:
            return f"{field} {operator} {value}"

    def _format_extracted_fields(self, extracted_fields: Dict[str, Any]) -> str:
        """Format extracted fields for the prompt."""
        lines = []
        for field_id, field_data in extracted_fields.items():
            if isinstance(field_data, dict):
                value = field_data.get("value", str(field_data))
            else:
                value = str(field_data)
            label = field_id.replace("_", " ").title()
            lines.append(f"- {label}: {value}")
        return "\n".join(lines) if lines else "No fields captured"

    def _parse_llm_response(
        self,
        result_data: Dict[str, Any],
        extracted_fields: Dict[str, Any],
    ) -> LeadEvaluationResult:
        """Parse and validate LLM response, filling in missing fields."""
        # Extract contact info from extracted_fields if not in result
        lead_summary = result_data.get("lead_summary", {})
        contact = lead_summary.get("contact", {})

        if not contact.get("name"):
            contact["name"] = self._get_field_value(extracted_fields, "contact_name", "Unknown")
        if not contact.get("email"):
            contact["email"] = self._get_field_value(extracted_fields, "contact_email")
        if not contact.get("phone"):
            contact["phone"] = self._get_field_value(extracted_fields, "contact_phone")

        lead_summary["contact"] = contact

        if not lead_summary.get("service_need"):
            lead_summary["service_need"] = self._get_field_value(
                extracted_fields, "service_need", "Not specified"
            )

        result_data["lead_summary"] = lead_summary

        # Ensure scoring has required fields
        scoring = result_data.get("scoring", {})
        if "score" not in scoring:
            scoring["score"] = result_data.get("lead_score", 50)
        if "priority" not in scoring:
            scoring["priority"] = result_data.get("priority_level", "medium")
        if "reasoning" not in scoring:
            scoring["reasoning"] = "Evaluation completed"
        if "signals_matched" not in scoring:
            scoring["signals_matched"] = []
        if "penalties_applied" not in scoring:
            scoring["penalties_applied"] = []
        result_data["scoring"] = scoring

        # Validate with Pydantic
        return LeadEvaluationResult.model_validate(result_data)

    def _get_field_value(
        self,
        extracted_fields: Dict[str, Any],
        field_id: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Extract field value from extracted_fields dict."""
        field_data = extracted_fields.get(field_id)
        if field_data is None:
            return default
        if isinstance(field_data, dict):
            return field_data.get("value", default)
        return str(field_data)

    def _default_evaluation(
        self,
        extracted_fields: Dict[str, Any],
        reason: str,
    ) -> LeadEvaluationResult:
        """Return default evaluation when LLM call fails."""
        return LeadEvaluationResult(
            lead_score=50,
            priority_level="medium",
            lead_quality="warm",
            urgency_level="medium",
            lead_summary=LeadSummary(
                contact=LeadContact(
                    name=self._get_field_value(extracted_fields, "contact_name", "Unknown"),
                    email=self._get_field_value(extracted_fields, "contact_email"),
                    phone=self._get_field_value(extracted_fields, "contact_phone"),
                ),
                service_need=self._get_field_value(
                    extracted_fields, "service_need", "Not specified"
                ),
                additional_info={},
                follow_up_questions=[],
            ),
            scoring=LeadScoring(
                score=50,
                priority="medium",
                signals_matched=[],
                penalties_applied=[],
                reasoning=reason,
            ),
            confidence=0.0,
        )


# =============================================================================
# Background Task
# =============================================================================


async def score_lead_background(
    session_id: UUID,
    extracted_fields: Dict[str, Any],
    workflow_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Background task to score a lead and update the database.

    This is fire-and-forget - errors are logged but don't affect the user.

    Args:
        session_id: Workflow session ID to update
        extracted_fields: Captured lead data
        workflow_context: Workflow configuration (template_name, scoring_rules, output_config)
    """
    try:
        logger.info(f"🔄 [BACKGROUND] Starting lead scoring for session {session_id}")

        # Run LLM scoring
        service = LeadScoringService()
        evaluation = await service.evaluate_lead(extracted_fields, workflow_context)

        # Update database with complete evaluation
        from shared.database.models.database import async_session_maker
        from shared.database.repositories.workflow_repository import WorkflowRepository

        async with async_session_maker() as session:
            repo = WorkflowRepository(session)
            await repo.update_session_lead_evaluation(
                session_id=session_id,
                evaluation_data=evaluation.model_dump(),
            )

        logger.info(
            f"✅ [BACKGROUND] Lead scoring complete for session {session_id}: "
            f"score={evaluation.lead_score}, priority={evaluation.priority_level}"
        )

    except Exception as e:
        logger.error(f"❌ [BACKGROUND] Lead scoring failed for session {session_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"session_id": str(session_id)},
            tags={
                "component": "lead_scoring",
                "operation": "background_task",
                "severity": "low",
                "user_facing": "false",
            },
        )
