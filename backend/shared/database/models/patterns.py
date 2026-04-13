from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PatternType(str, Enum):
    COMMUNICATION_STYLE = "communication_style"
    THINKING_PATTERN = "thinking_pattern"
    RESPONSE_STRUCTURE = "response_structure"
    VOCABULARY = "vocabulary"
    EMOTIONAL_TONE = "emotional_tone"
    EXPERTISE_DOMAIN = "expertise_domain"


class CommunicationStyle(BaseModel):
    avg_sentence_length: float = Field(..., description="Average sentence length in words")
    vocabulary_complexity: float = Field(..., description="Vocabulary complexity score")
    unique_words_ratio: float = Field(..., description="Ratio of unique words to total")
    formality_score: float = Field(..., description="Formality level (0-1)")
    common_phrases: List[str] = Field(default_factory=list, description="Frequently used phrases")
    transition_words: List[str] = Field(default_factory=list, description="Common transition words")
    filler_words: List[str] = Field(default_factory=list, description="Common filler words")


class ThinkingPattern(BaseModel):
    approach: str = Field(..., description="Problem-solving approach (top-down/bottom-up/lateral)")
    evidence_usage: str = Field(
        ..., description="How evidence is used (data-driven/narrative/mixed)"
    )
    abstraction_level: str = Field(
        ..., description="Abstraction preference (concrete/conceptual/balanced)"
    )
    framework_usage: List[str] = Field(
        default_factory=list, description="Mental models and frameworks used"
    )
    reasoning_style: str = Field(..., description="Reasoning style (deductive/inductive/abductive)")


class ResponseStructure(BaseModel):
    typical_opening: List[str] = Field(default_factory=list, description="Common opening patterns")
    explanation_style: str = Field(..., description="How explanations are structured")
    example_usage_frequency: float = Field(..., description="Frequency of using examples")
    conclusion_style: str = Field(..., description="How conclusions are formed")
    question_handling: str = Field(..., description="How questions are typically answered")


class EmotionalTone(BaseModel):
    sentiment_average: float = Field(..., description="Average sentiment score (-1 to 1)")
    emotional_range: float = Field(..., description="Emotional variability")
    empathy_markers: List[str] = Field(default_factory=list, description="Empathy expressions")
    humor_frequency: float = Field(..., description="Frequency of humor usage")
    tone_consistency: float = Field(..., description="Consistency of emotional tone")


class PatternData(BaseModel):
    pattern_type: PatternType
    data: Dict[str, Any]
    confidence: float = Field(ge=0, le=1, description="Confidence score for this pattern")
    sample_count: int = Field(..., description="Number of samples used to derive pattern")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PatternCreate(BaseModel):
    persona_id: UUID
    pattern_type: PatternType
    pattern_data: Dict[str, Any]
    confidence: float = Field(default=0.0, ge=0, le=1)


class PatternResponse(BaseModel):
    id: UUID
    persona_id: UUID
    pattern_type: str
    pattern_data: Dict[str, Any]
    confidence: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatternAnalysis(BaseModel):
    persona_id: UUID
    communication_style: Optional[CommunicationStyle] = None
    thinking_patterns: Optional[ThinkingPattern] = None
    response_structure: Optional[ResponseStructure] = None
    emotional_tone: Optional[EmotionalTone] = None
    expertise_domains: List[str] = Field(default_factory=list)
    overall_confidence: float = Field(..., description="Overall pattern confidence")
