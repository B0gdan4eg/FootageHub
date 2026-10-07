"""
Internal API for inter-service communication.

Web-api calls these endpoints to perform downloads via media-bot,
since the browser automation (nodriver, playwright) runs only here.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from media_bot.services import BotServices
from shared.internal_auth import require_internal_auth

router = APIRouter(prefix="/internal", dependencies=[Depends(require_internal_auth)])


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
        platform_map = {
            "ENVATO": "envato",
            "FREEPIK": "freepik",
            "MOTION_ARRAY": "motion",
        }
        platform = platform_map.get(provider)
        if not platform:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

        link_processor = BotServices.link_processor
        if not link_processor:
            raise HTTPException(status_code=503, detail="Download service is not ready")

        result = await link_processor.submit(req.url, platform=platform)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download error: {e}")

    if not result:
        raise HTTPException(status_code=500, detail="Download failed — no URL returned")

    return {"download_url": result}
