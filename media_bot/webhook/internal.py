"""
Internal API for inter-service communication.

Web-api calls these endpoints to perform downloads via media-bot,
since the browser automation (nodriver, playwright) runs only here.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/internal")


class DownloadRequest(BaseModel):
    url: str
    provider: str


@router.post("/download")
async def internal_download(req: DownloadRequest):
    """
    Download a file using the appropriate downloader.
    Called by web-api to delegate browser-based downloads.
    """
    provider = req.provider.upper()

    try:
        if provider == "ENVATO":
            from media_bot.utils.envato_utils.envato_playwright import (
                get_envato_direct_download_url,
            )

            result = await get_envato_direct_download_url(req.url)

        elif provider == "FREEPIK":
            from media_bot.utils.freepik_utils.freepik import get_freepik_direct_download_url

            result = await get_freepik_direct_download_url(req.url)

        elif provider == "MOTION_ARRAY":
            from media_bot.utils.motion_utils.motion import get_motion_direct_download_url

            result = await get_motion_direct_download_url(req.url)

        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download error: {e}")

    if not result:
        raise HTTPException(status_code=500, detail="Download failed — no URL returned")

    return {"download_url": result}
