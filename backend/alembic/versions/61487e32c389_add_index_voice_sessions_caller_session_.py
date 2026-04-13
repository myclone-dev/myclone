"""add_index_voice_sessions_caller_session_token

Revision ID: 61487e32c389
Revises: 73b9a885ca04
Create Date: 2026-02-04 11:19:53.032446

Adds an index on voice_sessions.caller_session_token to optimize the
conversation detail API lookup for voice recordings.

Without this index, the query at conversation_routes.py would cause
full table scans as the voice_sessions table grows:
    WHERE caller_session_token = conversation.session_id

This column links voice sessions to conversations and is queried on
every conversation detail request for voice conversations.

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "61487e32c389"
down_revision: Union[str, Sequence[str], None] = "73b9a885ca04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add index on voice_sessions.caller_session_token for conversation lookups."""
    op.create_index(
        "ix_voice_sessions_caller_session_token",
        "voice_sessions",
        ["caller_session_token"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the caller_session_token index."""
    op.drop_index(
        "ix_voice_sessions_caller_session_token",
        table_name="voice_sessions",
    )
