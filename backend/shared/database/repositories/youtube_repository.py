"""
YouTube Repository - Database operations for YouTube data
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import async_session_maker
from shared.database.models.youtube import YouTubeVideo

logger = logging.getLogger(__name__)


class YouTubeRepository:
    """Repository for YouTube database operations"""

    async def save_youtube_video(self, user_id: UUID, video_data: Dict) -> UUID:
        """
        Save YouTube video data for a user

        Args:
            user_id: User UUID
            video_data: Video data from scraping provider

        Returns:
            UUID of the saved video
        """
        async with async_session_maker() as session:
            try:
                video_id = await self._upsert_video(session, user_id, video_data)
                await session.commit()

                logger.info(f"Saved YouTube video for user {user_id}: video_id={video_id}")
                return video_id

            except Exception as e:
                await session.rollback()
                logger.error(f"Error saving YouTube video for user {user_id}: {e}")
                raise

    async def save_youtube_videos_batch(self, user_id: UUID, videos_data: List[Dict]) -> Dict:
        """
        Save multiple YouTube videos for a user

        Args:
            user_id: User UUID
            videos_data: List of video data from scraping provider

        Returns:
            dict with videos_count
        """
        async with async_session_maker() as session:
            try:
                videos_count = 0
                for video_data in videos_data:
                    await self._upsert_video(session, user_id, video_data)
                    videos_count += 1

                await session.commit()

                logger.info(f"Saved {videos_count} YouTube videos for user {user_id}")
                return {"videos_count": videos_count}

            except Exception as e:
                await session.rollback()
                logger.error(f"Error saving YouTube videos batch for user {user_id}: {e}")
                raise

    async def _upsert_video(self, session: AsyncSession, user_id: UUID, video_data: Dict) -> UUID:
        """Upsert YouTube video"""
        # Parse published_at if it's a string
        published_at = None
        if video_data.get("published_at"):
            if isinstance(video_data["published_at"], str):
                try:
                    published_at = datetime.fromisoformat(
                        video_data["published_at"].replace("Z", "+00:00")
                    )
                except ValueError:
                    published_at = None
            else:
                published_at = video_data["published_at"]

        stmt = (
            insert(YouTubeVideo)
            .values(
                user_id=user_id,
                video_id=video_data["video_id"],
                title=video_data.get("title"),
                description=video_data.get("description"),
                video_url=video_data["video_url"],
                thumbnail_url=video_data.get("thumbnail_url"),
                duration_seconds=video_data.get("duration_seconds"),
                view_count=video_data.get("view_count", 0),
                channel_name=video_data.get("channel_name"),
                channel_url=video_data.get("channel_url"),
                published_at=published_at,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_youtube_videos_user_video_id",
                set_={
                    "title": video_data.get("title"),
                    "description": video_data.get("description"),
                    "video_url": video_data["video_url"],
                    "thumbnail_url": video_data.get("thumbnail_url"),
                    "duration_seconds": video_data.get("duration_seconds"),
                    "view_count": video_data.get("view_count", 0),
                    "channel_name": video_data.get("channel_name"),
                    "channel_url": video_data.get("channel_url"),
                    "published_at": published_at,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            .returning(YouTubeVideo.id)
        )

        result = await session.execute(stmt)
        return result.scalar_one()

    async def get_user_videos(
        self, user_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[YouTubeVideo]:
        """Get YouTube videos for a user"""
        async with async_session_maker() as session:
            stmt = (
                select(YouTubeVideo)
                .where(YouTubeVideo.user_id == user_id)
                .order_by(YouTubeVideo.published_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_video_by_id(self, video_id: str) -> Optional[YouTubeVideo]:
        """Get a specific YouTube video by video_id"""
        async with async_session_maker() as session:
            stmt = select(YouTubeVideo).where(YouTubeVideo.video_id == video_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def delete_user_videos(self, user_id: UUID) -> int:
        """Delete all YouTube videos for a user"""
        async with async_session_maker() as session:
            try:
                stmt = select(YouTubeVideo).where(YouTubeVideo.user_id == user_id)
                result = await session.execute(stmt)
                videos = result.scalars().all()
                count = len(videos)

                for video in videos:
                    await session.delete(video)

                await session.commit()
                logger.info(f"Deleted {count} YouTube videos for user {user_id}")
                return count

            except Exception as e:
                await session.rollback()
                logger.error(f"Error deleting YouTube videos for user {user_id}: {e}")
                raise
