"""
Repository for Download model operations.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Download, ServiceType
from shared.db.repositories.base import BaseRepository


class DownloadRepository(BaseRepository[Download]):
    """Repository for managing downloads."""

    def __init__(self, session: AsyncSession):
        """Initialize download repository."""
        super().__init__(Download, session)

    async def create_download(
        self,
        user_id: int,
        media_id: int,
        service_type: Optional[ServiceType] = None,
    ) -> Download:
        """
        Create a new download record.

        Args:
            user_id: User ID
            media_id: Media ID
            service_type: Service type (ENVATO, FREEPIK, MOTION_ARRAY)

        Returns:
            Created download record
        """
        return await self.create(user_id=user_id, media_id=media_id, service_type=service_type)

    async def count_by_user(self, user_id: int) -> int:
        """
        Count downloads for a specific user.

        Args:
            user_id: User ID

        Returns:
            Number of downloads
        """
        result = await self.session.execute(
            select(func.count(Download.id)).where(Download.user_id == user_id)
        )
        return result.scalar_one()

    async def count_total(self) -> int:
        """
        Count total downloads across all users.

        Returns:
            Total number of downloads
        """
        result = await self.session.execute(select(func.count()).select_from(Download))
        return result.scalar()

    async def count_today(self, today_start: datetime) -> int:
        """
        Count downloads since start of today.

        Args:
            today_start: Start of today (datetime)

        Returns:
            Number of downloads today
        """
        result = await self.session.execute(
            select(func.count(Download.id)).where(Download.downloaded_at >= today_start)
        )
        return result.scalar()

    async def count_by_service_today(self, service_type: ServiceType, today_start: datetime) -> int:
        """
        Count downloads for a specific service since start of today.

        Args:
            service_type: Service type
            today_start: Start of today (datetime)

        Returns:
            Number of downloads for this service today
        """
        result = await self.session.execute(
            select(func.count(Download.id)).where(
                Download.downloaded_at >= today_start,
                Download.service_type == service_type,
            )
        )
        return result.scalar()

    async def has_user_downloaded(self, user_id: int, url: str) -> bool:
        """
        Check if user has downloaded file by URL in last 24 hours.

        Args:
            user_id: User ID
            url: Media URL

        Returns:
            True if user downloaded this file in last 24 hours
        """
        from shared.db.models import Media

        try:
            # Time limit (last 24 hours only)
            time_limit = datetime.utcnow() - timedelta(hours=24)

            # Check if there's a download record for this user and URL
            result = await self.session.execute(
                select(Download)
                .join(Media, Download.media_id == Media.id)
                .where(
                    Download.user_id == user_id,
                    Media.url == url,
                    Download.downloaded_at >= time_limit,  # Last 24 hours
                )
            )
            download = result.scalars().first()

            return download is not None

        except Exception as e:
            print(f"Error checking has_user_downloaded: {e}")
            return False
