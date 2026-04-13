"""replace_persona_unique_constraint_with_partial_index

Revision ID: 1b036e1c1421
Revises: c10a70dabba7
Create Date: 2026-02-20 22:39:24.692990

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b036e1c1421'
down_revision: Union[str, Sequence[str], None] = 'c10a70dabba7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace full unique constraint with partial unique index.

    The old constraint prevented creating a persona with the same name
    as a soft-deleted one. The new partial index only enforces uniqueness
    among non-deleted personas (WHERE deleted_at IS NULL).
    """
    op.drop_constraint('uq_personas_user_persona_name', 'personas', type_='unique')
    op.create_index(
        'uq_personas_user_persona_name_active',
        'personas',
        ['user_id', 'persona_name'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    """Restore the full unique constraint."""
    op.drop_index(
        'uq_personas_user_persona_name_active',
        table_name='personas',
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.create_unique_constraint(
        'uq_personas_user_persona_name',
        'personas',
        ['user_id', 'persona_name'],
    )
