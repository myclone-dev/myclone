"""backfill_llm_expertise_for_existing_users

Revision ID: b2c3d4e5f6g8
Revises: a1b2c3d4e5f7
Create Date: 2025-12-09 13:00:00.000000

This migration backfills llm_generated_expertise for existing users who have
LinkedIn data but no expertise generated yet.

Note: This is a data migration that makes LLM API calls, so it may take some time
to run depending on the number of users.
"""

import logging
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    """No-op: LinkedIn expertise backfill removed (scraping infrastructure removed)."""
    pass


def downgrade() -> None:
    """
    Clear llm_generated_expertise for all users.

    Note: This removes all generated expertise. They can be regenerated
    by re-running the upgrade or by re-importing LinkedIn data.
    """
    op.execute(
        "UPDATE users SET llm_generated_expertise = NULL WHERE llm_generated_expertise IS NOT NULL"
    )
