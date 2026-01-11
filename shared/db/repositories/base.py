"""
Base repository with common CRUD operations.
"""

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Base repository implementing common CRUD operations.

    This follows the Repository pattern to abstract database operations.
    """

    def __init__(self, model: Type[T], session: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Database session
        """
        self.model = model
        self.session = session

    async def get_by_id(self, id: int) -> Optional[T]:
        """
        Get entity by ID.

        Args:
            id: Entity ID

        Returns:
            Entity or None if not found
        """
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """
        Get all entities with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of entities
        """
        result = await self.session.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, **kwargs) -> T:
        """
        Create new entity.

        Args:
            **kwargs: Entity attributes

        Returns:
            Created entity
        """
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, id: int, **kwargs) -> Optional[T]:
        """
        Update entity by ID.

        Args:
            id: Entity ID
            **kwargs: Attributes to update

        Returns:
            Updated entity or None if not found
        """
        await self.session.execute(update(self.model).where(self.model.id == id).values(**kwargs))
        await self.session.commit()
        return await self.get_by_id(id)

    async def delete(self, id: int) -> bool:
        """
        Delete entity by ID.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False if not found
        """
        result = await self.session.execute(delete(self.model).where(self.model.id == id))
        await self.session.commit()
        return result.rowcount > 0

    async def count(self) -> int:
        """
        Count total entities.

        Returns:
            Number of entities
        """
        result = await self.session.execute(select(func.count()).select_from(self.model))
        return result.scalar()
