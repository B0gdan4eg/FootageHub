from datetime import datetime, timedelta, timezone

import jwt
import pytest

from web_api.auth.jwt_handler import create_access_token, decode_token
from web_api.config import config


def claims():
    now = datetime.now(timezone.utc)
    return {"sub": "123", "iat": now, "exp": now + timedelta(minutes=5)}


def test_current_tokens_and_existing_hs256_tokens_remain_compatible(monkeypatch):
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "private-test-key-" * 4)
    assert decode_token(create_access_token(123)) == 123
    assert decode_token(jwt.encode(claims(), config.JWT_SECRET_KEY, algorithm="HS256")) == 123


@pytest.mark.parametrize(
    "attack", ["wrong-signature", "none", "other-algorithm", "expired", "missing-exp"]
)
def test_invalid_or_incomplete_tokens_are_rejected(monkeypatch, attack):
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "private-test-key-" * 4)
    payload = claims()
    secret = config.JWT_SECRET_KEY
    algorithm = "HS256"
    if attack == "wrong-signature":
        secret = "other-private-test-key-" * 4
    elif attack == "none":
        secret, algorithm = None, "none"
    elif attack == "other-algorithm":
        algorithm = "HS384"
    elif attack == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    elif attack == "missing-exp":
        del payload["exp"]
    with pytest.raises(ValueError):
        decode_token(jwt.encode(payload, secret, algorithm=algorithm))
