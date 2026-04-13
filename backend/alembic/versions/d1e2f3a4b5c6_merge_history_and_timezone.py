"""merge history and timezone branches

Revision ID: d1e2f3a4b5c6
Revises: f784955dd88d, 52fd2e9ac67c
Create Date: 2025-10-05 00:00:00.000000

This is a no-op merge migration that unifies two divergent heads:
- f784955dd88d: create_persona_prompts_history_table_
- 52fd2e9ac67c: convert_datetime_columns_to_timezone_aware

Both previously branched from 6565293fb0c0. This merge restores a single head.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = ("f784955dd88d", "52fd2e9ac67c")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op merge
    pass


def downgrade() -> None:
    # No-op merge
    pass

