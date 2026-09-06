from fastapi import APIRouter

router = APIRouter(prefix="/cameras", tags=["Cameras"])

cameras = []


@router.get("/")
def get_cameras():
    return cameras


@router.post("/")
def add_camera(camera: dict):
    cameras.append(camera)
    return {
        "message": "Camera added successfully",
        "camera": camera
    }