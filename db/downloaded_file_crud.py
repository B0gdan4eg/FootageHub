from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Media, Download

async def get_media_by_url(session, url: str):
    result = await session.execute(select(Media).where(Media.url == url))
    return result.scalars().first()

async def create_media(session, url: str, file_path: str, file_type: str):
    media = Media(url=url, file_path=file_path, file_type=file_type)
    session.add(media)
    await session.commit()
    await session.refresh(media)
    return media

async def create_download(session, user_id: int, media_id: int):
    download = Download(user_id=user_id, media_id=media_id)
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