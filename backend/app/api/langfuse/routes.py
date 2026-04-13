"""
Langfuse Prompt Management API

This module provides a clean, organized API for Langfuse prompt management
and evaluation, following best practices for modularity and maintainability.
"""

from fastapi import APIRouter

from app.api.langfuse.endpoints import (
    datasets_router,
    evaluation_router,
    llm_judge_router,
    prompt_crud_router,
)

# Main router (no tags to avoid duplicate categorization)
router = APIRouter(prefix="/api/v1/langfuse/prompts")

# Include all sub-routers (tags will be inherited from individual routers)
router.include_router(prompt_crud_router)
router.include_router(evaluation_router, prefix="/eval")
router.include_router(llm_judge_router, prefix="/eval")
router.include_router(datasets_router, prefix="/dataset")

__all__ = ["router"]
