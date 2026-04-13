"""Create persona_prompts table

Revision ID: 0e763f7538c0
Revises: b2c3d4e5f6a7
Create Date: 2025-09-22 19:35:28.575279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e763f7538c0'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE persona_prompts (
        id SERIAL PRIMARY KEY,
        persona_username VARCHAR(100) UNIQUE NOT NULL,
        introduction TEXT NOT NULL,
        thinking_style TEXT,
        area_of_expertise TEXT,
        chat_objective TEXT,
        objective_response TEXT,
        example_responses TEXT,
        target_audience TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE persona_prompts;")