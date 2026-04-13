"""Add is_active, response_structure, conversation_flow to persona_prompts

Revision ID: a1b2c3d4e5f6
Revises: 9abc123def45
Create Date: 2025-09-26 01:05:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9abc123def45'
branch_labels = None
depends_on = None

def upgrade():
    # Add new columns to persona_prompts
    op.add_column('persona_prompts', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('persona_prompts', sa.Column('response_structure', sa.Text(), nullable=True))
    op.add_column('persona_prompts', sa.Column('conversation_flow', sa.Text(), nullable=True))

    # Optional: remove the server_default for is_active after setting existing rows
    op.alter_column('persona_prompts', 'is_active', server_default=None)


def downgrade():
    # Drop the added columns (reverse order is safe)
    op.drop_column('persona_prompts', 'conversation_flow')
    op.drop_column('persona_prompts', 'response_structure')
    op.drop_column('persona_prompts', 'is_active')

