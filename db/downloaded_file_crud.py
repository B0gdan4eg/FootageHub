from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Download, Media, ServiceType


async def get_media_by_url(session, url: str):
    result = await session.execute(select(Media).where(Media.url == url))
    return result.scalars().first()


async def create_media(session, url: str, file_type: str):
    # Проверяем, есть ли уже запись с таким url
    result = await session.execute(select(Media).where(Media.url == url))
    media = result.scalar_one_or_none()

    if media:
        # Если нашли — возвращаем её
        return media

    # Если не нашли — создаём новую запись
    media = Media(url=url, file_type=file_type)
    session.add(media)
    await session.commit()
    await session.refresh(media)
    return media


async def create_download(session, user_id: int, media_id: int, service_type: ServiceType = None):
    download = Download(user_id=user_id, media_id=media_id, service_type=service_type)
    session.add(download)
    await session.commit()
    await session.refresh(download)
    return download


async def count_downloads_by_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(Download.id)).where(Download.user_id == user_id)
    )
    count = result.scalar_one()
    return count


async def count_total_downloads(session: AsyncSession):
    result = await session.execute(select(func.count()).select_from(Download))
    return result.scalar()
