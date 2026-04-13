"""convert_datetime_columns_to_timezone_aware

Revision ID: 52fd2e9ac67c
Revises: 6565293fb0c0
Create Date: 2025-10-03 20:46:37.217557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52fd2e9ac67c'
down_revision: Union[str, Sequence[str], None] = '6565293fb0c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert all TIMESTAMP WITHOUT TIME ZONE columns to TIMESTAMP WITH TIME ZONE and fix nullable constraints."""

    # user_sessions table
    op.alter_column('user_sessions', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('user_sessions', 'last_accessed',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('user_sessions', 'expires_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('user_sessions', 'is_active',
                    existing_type=sa.Boolean(),
                    existing_nullable=True,
                    nullable=False)

    # personas table
    op.alter_column('personas', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('personas', 'updated_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)

    # content_chunks table
    op.alter_column('content_chunks', 'posted_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)
    op.alter_column('content_chunks', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)

    # patterns table
    op.alter_column('patterns', 'confidence',
                    existing_type=sa.Float(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('patterns', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('patterns', 'updated_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)

    # conversations table
    op.alter_column('conversations', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('conversations', 'updated_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)

    # external_data_sources table
    op.alter_column('external_data_sources', 'processed',
                    existing_type=sa.Boolean(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('external_data_sources', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('external_data_sources', 'processed_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)

    # persona_prompts table
    op.alter_column('persona_prompts', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)
    op.alter_column('persona_prompts', 'updated_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True,
                    nullable=False)

    # prompt_templates table
    op.alter_column('prompt_templates', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)
    op.alter_column('prompt_templates', 'updated_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)

    # waitlist table
    op.alter_column('waitlist', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)

    # api_keys table
    op.alter_column('api_keys', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)
    op.alter_column('api_keys', 'expires_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)
    op.alter_column('api_keys', 'last_used_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)

    # worker_processes table
    op.alter_column('worker_processes', 'started_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)
    op.alter_column('worker_processes', 'last_health_check',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)
    op.alter_column('worker_processes', 'last_activity',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)

    # active_rooms table
    op.alter_column('active_rooms', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)
    op.alter_column('active_rooms', 'last_activity',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_nullable=True)


def downgrade() -> None:
    """Revert all TIMESTAMP WITH TIME ZONE columns back to TIMESTAMP WITHOUT TIME ZONE and revert nullable constraints."""

    # active_rooms table
    op.alter_column('active_rooms', 'last_activity',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)
    op.alter_column('active_rooms', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    # worker_processes table
    op.alter_column('worker_processes', 'last_activity',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)
    op.alter_column('worker_processes', 'last_health_check',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)
    op.alter_column('worker_processes', 'started_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    # api_keys table
    op.alter_column('api_keys', 'last_used_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)
    op.alter_column('api_keys', 'expires_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)
    op.alter_column('api_keys', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    # waitlist table
    op.alter_column('waitlist', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    # prompt_templates table
    op.alter_column('prompt_templates', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)
    op.alter_column('prompt_templates', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    # persona_prompts table
    op.alter_column('persona_prompts', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('persona_prompts', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)

    # external_data_sources table
    op.alter_column('external_data_sources', 'processed_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)
    op.alter_column('external_data_sources', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('external_data_sources', 'processed',
                    existing_type=sa.Boolean(),
                    existing_nullable=False,
                    nullable=True)

    # conversations table
    op.alter_column('conversations', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('conversations', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)

    # patterns table
    op.alter_column('patterns', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('patterns', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('patterns', 'confidence',
                    existing_type=sa.Float(),
                    existing_nullable=False,
                    nullable=True)

    # content_chunks table
    op.alter_column('content_chunks', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('content_chunks', 'posted_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    # personas table
    op.alter_column('personas', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('personas', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)

    # user_sessions table
    op.alter_column('user_sessions', 'is_active',
                    existing_type=sa.Boolean(),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('user_sessions', 'expires_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('user_sessions', 'last_accessed',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
    op.alter_column('user_sessions', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    nullable=True)
