"""convert_persona_prompts_id_to_uuid

Revision ID: d4cd672073f2
Revises: 849e72c9fbc3
Create Date: 2025-10-11 07:57:39.896334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4cd672073f2'
down_revision: Union[str, Sequence[str], None] = '849e72c9fbc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable uuid-ossp extension for uuid_generate_v4()
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ===== persona_prompts table =====
    # Drop PK and id column, add new UUID id column
    op.drop_constraint('persona_prompts_pkey', 'persona_prompts', type_='primary')
    op.drop_column('persona_prompts', 'id')
    op.add_column('persona_prompts',
        sa.Column('id', postgresql.UUID(as_uuid=True),
                  nullable=False,
                  server_default=sa.text('uuid_generate_v4()'))
    )
    op.create_primary_key('persona_prompts_pkey', 'persona_prompts', ['id'])

    # ===== persona_prompts_history table =====
    # Drop PK and id column, add new UUID id column
    op.drop_constraint('persona_prompts_history_pkey', 'persona_prompts_history', type_='primary')
    op.drop_column('persona_prompts_history', 'id')
    op.add_column('persona_prompts_history',
        sa.Column('id', postgresql.UUID(as_uuid=True),
                  nullable=False,
                  server_default=sa.text('uuid_generate_v4()'))
    )
    op.create_primary_key('persona_prompts_history_pkey', 'persona_prompts_history', ['id'])

    # Convert original_id from integer to UUID
    op.drop_column('persona_prompts_history', 'original_id')
    op.add_column('persona_prompts_history',
        sa.Column('original_id', postgresql.UUID(as_uuid=True), nullable=True)
    )

    # ===== prompt_templates table =====
    # Drop unique constraint that includes the id column
    op.drop_constraint('uq_prompt_template_unique_active', 'prompt_templates', type_='unique')
    # Drop PK and id column, add new UUID id column
    op.drop_constraint('prompt_templates_pkey', 'prompt_templates', type_='primary')
    op.drop_column('prompt_templates', 'id')
    op.add_column('prompt_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True),
                  nullable=False,
                  server_default=sa.text('uuid_generate_v4()'))
    )
    op.create_primary_key('prompt_templates_pkey', 'prompt_templates', ['id'])
    # Re-create unique constraint
    op.create_unique_constraint('uq_prompt_template_unique_active', 'prompt_templates',
        ['type', 'expertise', 'persona_username', 'platform', 'is_active'])


def downgrade() -> None:
    """Downgrade schema."""
    # ===== prompt_templates table =====
    op.drop_constraint('uq_prompt_template_unique_active', 'prompt_templates', type_='unique')
    op.drop_constraint('prompt_templates_pkey', 'prompt_templates', type_='primary')
    op.drop_column('prompt_templates', 'id')
    # Recreate sequence
    op.execute('CREATE SEQUENCE IF NOT EXISTS prompt_templates_id_seq')
    op.add_column('prompt_templates',
        sa.Column('id', sa.INTEGER(),
                  nullable=False,
                  server_default=sa.text("nextval('prompt_templates_id_seq'::regclass)"))
    )
    op.create_primary_key('prompt_templates_pkey', 'prompt_templates', ['id'])
    op.create_unique_constraint('uq_prompt_template_unique_active', 'prompt_templates',
        ['type', 'expertise', 'persona_username', 'platform', 'is_active'])

    # ===== persona_prompts_history table =====
    op.drop_column('persona_prompts_history', 'original_id')
    op.add_column('persona_prompts_history',
        sa.Column('original_id', sa.INTEGER(), nullable=True)
    )
    op.drop_constraint('persona_prompts_history_pkey', 'persona_prompts_history', type_='primary')
    op.drop_column('persona_prompts_history', 'id')
    # Recreate sequence
    op.execute('CREATE SEQUENCE IF NOT EXISTS persona_prompts_history_id_seq')
    op.add_column('persona_prompts_history',
        sa.Column('id', sa.INTEGER(),
                  nullable=False,
                  server_default=sa.text("nextval('persona_prompts_history_id_seq'::regclass)"))
    )
    op.create_primary_key('persona_prompts_history_pkey', 'persona_prompts_history', ['id'])

    # ===== persona_prompts table =====
    op.drop_constraint('persona_prompts_pkey', 'persona_prompts', type_='primary')
    op.drop_column('persona_prompts', 'id')
    # Recreate sequence
    op.execute('CREATE SEQUENCE IF NOT EXISTS persona_prompts_id_seq')
    op.add_column('persona_prompts',
        sa.Column('id', sa.INTEGER(),
                  nullable=False,
                  server_default=sa.text("nextval('persona_prompts_id_seq'::regclass)"))
    )
    op.create_primary_key('persona_prompts_pkey', 'persona_prompts', ['id'])
