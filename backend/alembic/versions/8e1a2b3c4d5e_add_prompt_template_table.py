"""
Add prompt_templates table

Revision ID: 8e1a2b3c4d5e
Revises: 301ca550b0cc
Create Date: 2025-09-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import datetime

# revision identifiers, used by Alembic.
revision = '8e1a2b3c4d5e'
down_revision = '301ca550b0cc'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('example', sa.Text(), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('expertise', sa.Text(), nullable=True),
        sa.Column('persona_username', sa.String(length=100), nullable=True),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    )

def downgrade():
    op.drop_table('prompt_templates')

