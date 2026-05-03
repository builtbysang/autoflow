from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from flowboard.services.vision import VisionError, describe_media, describe_url

router = APIRouter(prefix="/api/vision", tags=["vision"])


class DescribeRequest(BaseModel):
    media_id: Optional[str] = None
    url: Optional[str] = None


@router.post("/describe")
async def describe(body: DescribeRequest):
    try:
        if body.media_id:
            text = await describe_media(body.media_id)
        elif body.url:
            text = await describe_url(body.url)
        else:
            raise HTTPException(400, "provide media_id or url")
        return {"description": text}
    except VisionError as exc:
        raise HTTPException(422, str(exc))
