"""update_youtube_video_unique_constraint_per_user

Revision ID: 174efc03f2f3
Revises: 6e9865052876
Create Date: 2025-11-03 14:54:49.753267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '174efc03f2f3'
down_revision: Union[str, Sequence[str], None] = '6e9865052876'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Update unique constraint to allow per-user duplicate video_ids."""
    # Drop old unique constraint on video_id
    op.drop_constraint('uq_youtube_videos_video_id', 'youtube_videos', type_='unique')

    # Create new unique constraint on (user_id, video_id) combination
    op.create_unique_constraint('uq_youtube_videos_user_video_id', 'youtube_videos', ['user_id', 'video_id'])


def downgrade() -> None:
    """Downgrade schema: Revert to original unique constraint."""
    # Drop new unique constraint
    op.drop_constraint('uq_youtube_videos_user_video_id', 'youtube_videos', type_='unique')

    # Recreate old unique constraint on video_id only
    # WARNING: This will fail if multiple users have ingested the same video_id
    op.create_unique_constraint('uq_youtube_videos_video_id', 'youtube_videos', ['video_id'])
