"""
Prompt-related schemas for Langfuse prompt management
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LangfusePromptConfig(BaseModel):
    """Configuration for prompt behavior"""

    temperature: float = Field(0.7, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: int = Field(2000, ge=1, le=8000, description="Maximum tokens in response")
    top_p: float = Field(1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="Presence penalty")
    model: str = Field("gpt-4o", description="LLM model to use")

    class Config:
        json_schema_extra = {
            "example": {
                "temperature": 0.7,
                "max_tokens": 2000,
                "top_p": 0.95,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "model": "gpt-4o",
            }
        }


class LangfusePromptCreate(BaseModel):
    """Request model for creating a prompt in Langfuse"""

    name: str = Field(..., description="Unique name for the prompt (e.g., 'persona-chat-v1')")
    prompt: str = Field(..., description="The prompt template text with {{variables}}")
    config: Optional[LangfusePromptConfig] = Field(None, description="Optional LLM configuration")
    labels: Optional[List[str]] = Field(
        default_factory=list, description="Labels for categorization"
    )
    tags: Optional[List[str]] = Field(default_factory=list, description="Additional metadata tags")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "persona-expert-chat-v1",
                "prompt": "You are {{persona_name}}, {{role}} at {{company}}...",
                "config": {"temperature": 0.7, "max_tokens": 2000, "model": "gpt-4o"},
                "labels": ["persona", "chat"],
                "tags": ["version:1"],
            }
        }


class LangfusePromptUpdate(BaseModel):
    """Request model for updating a prompt (creates new version)"""

    prompt: Optional[str] = Field(None, description="Updated prompt template")
    config: Optional[LangfusePromptConfig] = Field(None, description="Updated LLM configuration")
    labels: Optional[List[str]] = Field(None, description="Updated labels")
    tags: Optional[List[str]] = Field(None, description="Updated tags")


class LangfusePromptResponse(BaseModel):
    """Response model for prompt operations"""

    status: str
    name: str
    version: int
    prompt: str
    config: Dict[str, Any]
    labels: List[str]
    tags: List[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message: str


class CompilePromptRequest(BaseModel):
    """Request model for compiling a prompt with persona data"""

    user_id: UUID = Field(..., description="User's UUID")
    persona_id: UUID = Field(..., description="Persona's UUID")
    prompt_name: str = Field(..., description="Langfuse prompt template name")
    version: Optional[int] = Field(None, description="Specific version (null = latest)")
    user_query: str = Field(..., description="User's question to compile into prompt")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "persona_id": "987fcdeb-51a2-43f8-9876-543210fedcba",
                "prompt_name": "persona-expert-chat-v1",
                "version": None,
                "user_query": "What's your approach to machine learning?",
            }
        }


class CompilePromptResponse(BaseModel):
    """Response model for compiled prompt"""

    status: str
    prompt_name: str
    version: int
    compiled_prompt: str
    config: Dict[str, Any]
    variables_used: Dict[str, Any]
    message: str
