from fastapi import APIRouter

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("/")
def get_cameras():
    return {"message": "Camera API working"}