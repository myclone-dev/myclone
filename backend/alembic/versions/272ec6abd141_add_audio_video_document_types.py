"""add_audio_video_document_types

Revision ID: 272ec6abd141
Revises: b7c8d9e0f1g2
Create Date: 2025-10-28 19:05:06.780543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '272ec6abd141'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1g2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support audio and video document types."""
    # Drop the old constraint
    op.drop_constraint('ck_documents_valid_type', 'documents', type_='check')

    # Add the new constraint with audio and video types
    op.create_check_constraint(
        'ck_documents_valid_type',
        'documents',
        "document_type IN ('pdf', 'xlsx', 'pptx', 'docx', 'csv', 'txt', 'md', 'mp3', 'mp4', 'webm', 'wav', 'avi', 'm4a', 'mov', 'mkv')"
    )

    # Add duration_seconds column with default value 0
    op.add_column(
        'documents',
        sa.Column('duration_seconds', sa.Integer(), nullable=True)
    )



def downgrade() -> None:
    """Downgrade schema to remove audio and video document types."""
    # Drop duration_seconds column
    op.drop_column('documents', 'duration_seconds')

    # Drop the new constraint
    op.drop_constraint('ck_documents_valid_type', 'documents', type_='check')

    # Restore the old constraint (original types only)
    op.create_check_constraint(
        'ck_documents_valid_type',
        'documents',
        "document_type IN ('pdf', 'xlsx', 'pptx', 'docx', 'csv', 'txt', 'md')"
    )
