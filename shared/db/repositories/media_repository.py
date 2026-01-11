"""
Repository for Media model operations.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Media
from shared.db.repositories.base import BaseRepository


class MediaRepository(BaseRepository[Media]):
    """Repository for managing media files."""

    def __init__(self, session: AsyncSession):
        """Initialize media repository."""
        super().__init__(Media, session)

    async def get_by_url(self, url: str) -> Optional[Media]:
        """
        Get media record by URL.

        Args:
            url: Media URL

        Returns:
            Media record or None if not found
        """
        result = await self.session.execute(select(Media).where(Media.url == url))
        return result.scalars().first()

    async def get_or_create(self, url: str, file_type: str) -> Media:
        """
        Get existing media record or create new one.

        Args:
            url: Media URL
            file_type: File type

        Returns:
            Media record
        """
        # Check if record with this URL already exists
        media = await self.get_by_url(url)

        if media:
            return media

        # If not found, create new record
        return await self.create(url=url, file_type=file_type)
