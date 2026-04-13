"""
Shared SQLAlchemy Base for all database models.

This module provides the single declarative_base() that is used by:
- App models (Persona, ContentChunk, etc.)
- Shared models (VoiceProcessingJob)
- Worker models

This ensures Alembic can track all models in one metadata object.
"""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
