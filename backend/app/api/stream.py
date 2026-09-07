from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.ai.detector import (
    generate_frames,
    get_camera,
    get_restricted_zones
)


router = APIRouter(
    prefix="/api",
    tags=["Stream"]
)


@router.get("/cameras/{camera_id}/stream")
def camera_stream(camera_id: int):

    camera = get_camera(camera_id)

    if camera is None:
        raise HTTPException(
            status_code=404,
            detail=f"Camera {camera_id} not found"
        )

    zones = get_restricted_zones(camera_id)

    if not zones:
        raise HTTPException(
            status_code=400,
            detail=f"No RESTRICTED zone found for camera {camera_id}"
        )

    return StreamingResponse(
        generate_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )