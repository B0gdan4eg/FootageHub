"""FastAPI dependency injection."""

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shared.db.models import User, UserRole
from shared.db.repositories.user_repository import UserRepository
from web_api.auth.jwt_handler import decode_token
from web_api.config import config

# Создаём engine и session factory отдельно от ботов
_engine = create_async_engine(config.DATABASE_URL, echo=False, pool_pre_ping=True)
_AsyncSessionLocal = sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: async database session."""
    async with _AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> User:
    """Dependency: authenticated user from JWT."""
    cookie_token = request.cookies.get("fh_session") if request else None
    if not credentials and cookie_token and request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") not in config.CORS_ORIGINS:
            raise HTTPException(status_code=403, detail="Invalid request origin")
    token = credentials.credentials if credentials else cookie_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
        )
    try:
        user_id = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )
    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency: admin/manager user."""
    if current_user.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав",
        )
    return current_user
