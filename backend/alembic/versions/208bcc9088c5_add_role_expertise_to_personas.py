"""add_role_expertise_to_personas

Revision ID: 208bcc9088c5
Revises: 6a1d662be909
Create Date: 2025-11-10 21:11:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "208bcc9088c5"
down_revision: Union[str, Sequence[str], None] = "6a1d662be909"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add role and expertise columns to personas table.

    - role: Professional role/title (String, nullable)
    - expertise: Areas of expertise (Text, nullable)

    These fields allow users to manually specify persona role and expertise,
    separate from LinkedIn experience data.
    """
    # Add role column
    op.add_column("personas", sa.Column("role", sa.String(length=255), nullable=True))

    # Add expertise column
    op.add_column("personas", sa.Column("expertise", sa.Text(), nullable=True))


def downgrade() -> None:
    """
    Remove role and expertise columns from personas table.

    Note: Data will be lost on downgrade.
    """
    # Drop expertise column
    op.drop_column("personas", "expertise")

    # Drop role column
    op.drop_column("personas", "role")
