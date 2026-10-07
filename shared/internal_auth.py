"""Authenticate private download requests even inside the Docker network."""
import hmac
import os

from fastapi import HTTPException, Request


def internal_headers():
    secret = os.getenv("INTERNAL_API_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("Internal API secret is not configured")
    return {"Authorization": "Bearer " + secret}


async def require_internal_auth(request: Request):
    secret = os.getenv("INTERNAL_API_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Internal authentication unavailable")
    supplied = request.headers.get("authorization", "")
    if (
        len(supplied) > 256
        or not supplied.isascii()
        or not hmac.compare_digest(supplied, "Bearer " + secret)
    ):
        raise HTTPException(status_code=403, detail="Invalid internal authorization")
