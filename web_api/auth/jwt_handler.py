"""JWT token creation and validation."""

from datetime import datetime, timedelta

import jwt
from jwt import InvalidTokenError

from web_api.config import config


def create_access_token(user_id: int) -> str:
    """Create JWT access token for user."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> int:
    """Decode JWT and return user_id (DB primary key)."""
    try:
        payload = jwt.decode(
            token,
            config.JWT_SECRET_KEY,
            algorithms=[config.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("Missing sub claim")
        return int(user_id)
    except InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}") from e
