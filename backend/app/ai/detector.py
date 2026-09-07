import os
from datetime import datetime

import cv2
import numpy as np
from ultralytics import YOLO
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.Model.models import Camera, Zone
from app.services.event_service import create_intrusion_event
from app.ai.vehicle import is_vehicle, get_vehicle_name


# ============================================================
# CONFIG
# ============================================================

MODEL_PATH = "yolo11n.pt"

CONFIDENCE = 0.30
IMAGE_SIZE = 640

REQUIRED_INSIDE_FRAMES = 5

SNAPSHOT_DIR = "snapshots"

# Person + car + motorcycle + bus + truck
DETECTION_CLASSES = [0, 2, 3, 5, 7]


# ============================================================
# GET CAMERA
# ============================================================

def get_camera(camera_id: int):
    """
    Get camera from PostgreSQL using camera ID.
    """

    db: Session = SessionLocal()

    try:
        camera = (
            db.query(Camera)
            .filter(Camera.id == camera_id)
            .first()
        )

        return camera

    finally:
        db.close()


# ============================================================
# GET RESTRICTED ZONES
# ============================================================

def get_restricted_zones(camera_id: int):

    db: Session = SessionLocal()

    try:
        zones = (
            db.query(Zone)
            .filter(
                Zone.camera_id == camera_id,
                Zone.zone_type == "PROTECTED"
            )
            .all()
        )

        return zones

    finally:
        db.close()

# ============================================================
# PREPARE ZONE POLYGONS
# ============================================================

def prepare_zone_polygons(zones):

    zone_polygons = []

    for zone in zones:

        coordinates = zone.coordinates

        if not coordinates or "points" not in coordinates:
            continue

        points = coordinates["points"]

        if len(points) < 3:
            continue

        polygon = [
            (int(point[0]), int(point[1]))
            for point in points
        ]

        zone_polygons.append(
            {
                "id": zone.id,
                "name": zone.name,
                "polygon": polygon,
            }
        )

    return zone_polygons


# ============================================================
# GENERATE PROCESSED VIDEO FRAMES
# ============================================================

def generate_frames(camera_id: int):
    """
    Capture CCTV video, run AI processing, draw detections
    and virtual fences, then yield JPEG frames for FastAPI.
    """

    # ========================================================
    # LOAD CAMERA
    # ========================================================

    camera = get_camera(camera_id)

    if not camera:
        print(f"[STREAM] Camera {camera_id} not found.")
        return

    print()
    print("==============================================")
    print(" SECURESTACK IBVAP - BORDER SURVEILLANCE")
    print("==============================================")
    print(f"Camera      : {camera.name}")
    print(f"Camera ID   : {camera.id}")
    print(f"RTSP URL    : {camera.rtsp_url}")
    print(f"Confidence  : {CONFIDENCE}")
    print(f"Image Size  : {IMAGE_SIZE}")
    print("==============================================")
    print()

    # ========================================================
    # LOAD RESTRICTED ZONES
    # ========================================================

    zones = get_restricted_zones(camera_id)

    if not zones:
        print(
            f"[STREAM] No RESTRICTED zone found "
            f"for camera {camera_id}."
        )
        return

    zone_polygons = prepare_zone_polygons(zones)

    if not zone_polygons:
        print(
            f"[STREAM] No valid RESTRICTED zone polygons "
            f"found for camera {camera_id}."
        )
        return

    print(f"[STREAM] Restricted fences: {len(zone_polygons)}")

    # ========================================================
    # LOAD YOLO
    # ========================================================

    model = YOLO(MODEL_PATH)

    # ========================================================
    # OPEN VIDEO / CAMERA
    # ========================================================

    video_source = camera.rtsp_url

    cap = cv2.VideoCapture(video_source)

    if not cap.isOpened():

        print()
        print(
            f"[STREAM] ERROR: Could not open "
            f"camera/video: {video_source}"
        )
        print()

        return

    # ========================================================
    # STATE
    # ========================================================

    # Each API request gets its own state.
    # This prevents tracking state from being shared
    # between different camera streams.

    inside_counter = {}

    confirmed_tracks = set()

    frame_number = 0

    total_events = 0

    # ========================================================
    # SNAPSHOT DIRECTORY
    # ========================================================

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    # ========================================================
    # MAIN LOOP
    # ========================================================

    while True:

        ret, frame = cap.read()

        if not ret:

            print(
                f"[STREAM] Video ended / camera "
                f"{camera_id} disconnected."
            )

            break

        frame_number += 1

        # ====================================================
        # YOLO + BYTE TRACK
        # ====================================================

        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=DETECTION_CLASSES,
            conf=CONFIDENCE,
            imgsz=IMAGE_SIZE,
            verbose=False
        )

        # ====================================================
        # DRAW RESTRICTED ZONES
        # ====================================================

        for zone in zone_polygons:

            polygon = np.array(
                zone["polygon"],
                dtype=np.int32
            )

            cv2.polylines(
                frame,
                [polygon],
                isClosed=True,
                color=(0, 0, 255),
                thickness=2
            )

            x, y = zone["polygon"][0]

            cv2.putText(
                frame,
                f"ZONE {zone['id']}: {zone['name']}",
                (x, max(25, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2
            )

        # ====================================================
        # PROCESS DETECTIONS
        # ====================================================

        if (
            results
            and results[0].boxes is not None
            and results[0].boxes.id is not None
        ):

            boxes = results[0].boxes

            track_ids = boxes.id.int().cpu().tolist()

            xyxy = boxes.xyxy.cpu().numpy()

            confidences = boxes.conf.cpu().numpy()

            class_ids = boxes.cls.int().cpu().tolist()

            # =================================================
            # PROCESS EACH OBJECT
            # =================================================

            for box, track_id, confidence, class_id in zip(
                xyxy,
                track_ids,
                confidences,
                class_ids
            ):

                x1, y1, x2, y2 = map(
                    int,
                    box
                )

                # =============================================
                # VEHICLE
                # =============================================

                if is_vehicle(class_id):

                    vehicle_name = get_vehicle_name(class_id)

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (255, 180, 0),
                        2
                    )

                    label = (
                        f"{vehicle_name} "
                        f"ID:{track_id} "
                        f"{confidence:.2f}"
                    )

                    cv2.putText(
                        frame,
                        label,
                        (x1, max(25, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (255, 180, 0),
                        2
                    )

                    continue

                # =============================================
                # ONLY PROCESS PERSON FOR INTRUSION
                # =============================================

                if class_id != 0:
                    continue

                # =============================================
                # FOOT POINT
                # =============================================

                foot_x = int((x1 + x2) / 2)
                foot_y = int(y2)

                foot_point = (
                    foot_x,
                    foot_y
                )

                # =============================================
                # CHECK VIRTUAL FENCES
                # =============================================

                inside_zone = None

                for zone in zone_polygons:

                    polygon_np = np.array(
                        zone["polygon"],
                        dtype=np.int32
                    )

                    result = cv2.pointPolygonTest(
                        polygon_np,
                        foot_point,
                        False
                    )

                    if result >= 0:

                        inside_zone = zone

                        break

                # =============================================
                # PERSON INSIDE ZONE
                # =============================================

                if inside_zone:

                    zone_id = inside_zone["id"]

                    key = (
                        track_id,
                        zone_id
                    )

                    inside_counter[key] = (
                        inside_counter.get(key, 0) + 1
                    )

                    current_frames = inside_counter[key]

                    # -----------------------------------------
                    # RED PERSON BOX
                    # -----------------------------------------

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 0, 255),
                        2
                    )

                    cv2.putText(
                        frame,
                        f"PERSON {track_id} - INTRUSION",
                        (x1, max(25, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2
                    )

                    cv2.circle(
                        frame,
                        foot_point,
                        5,
                        (0, 0, 255),
                        -1
                    )

                    # -----------------------------------------
                    # CONFIRM INTRUSION
                    # -----------------------------------------

                    if (
                        current_frames >= REQUIRED_INSIDE_FRAMES
                        and key not in confirmed_tracks
                    ):

                        print()
                        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        print("🚨 INTRUSION CONFIRMED")
                        print(f"Camera   : {camera_id}")
                        print(f"Track ID : {track_id}")
                        print(f"Zone     : {zone_id}")
                        print(f"Frames   : {current_frames}")
                        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        print()

                        # =====================================
                        # SNAPSHOT
                        # =====================================

                        filename = (
                            f"intrusion_"
                            f"{camera_id}_"
                            f"{track_id}_"
                            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            f".jpg"
                        )

                        snapshot_path = os.path.join(
                            SNAPSHOT_DIR,
                            filename
                        )

                        cv2.imwrite(
                            snapshot_path,
                            frame
                        )

                        # =====================================
                        # DATABASE EVENT
                        # =====================================

                        event = create_intrusion_event(
                            camera_id=camera_id,
                            track_id=track_id,
                            confidence=float(confidence),
                            snapshot_path=snapshot_path,
                            zone_id=zone_id
                        )

                        confirmed_tracks.add(key)

                        total_events += 1

                        print("✅ Event saved:")
                        print(event)
                        print()

                # =============================================
                # PERSON OUTSIDE ZONE
                # =============================================

                else:

                    # Reset inside counters for this track

                    for key in list(
                        inside_counter.keys()
                    ):

                        if key[0] == track_id:

                            inside_counter[key] = 0

                    # -----------------------------------------
                    # GREEN PERSON BOX
                    # -----------------------------------------

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        f"PERSON {track_id}",
                        (x1, max(25, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )

                    cv2.circle(
                        frame,
                        foot_point,
                        5,
                        (0, 255, 0),
                        -1
                    )

        # ====================================================
        # ENCODE PROCESSED FRAME
        # ====================================================

        success, buffer = cv2.imencode(
            ".jpg",
            frame,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                80
            ]
        )

        if not success:
            continue

        # ====================================================
        # SEND MJPEG FRAME TO FASTAPI
        # ====================================================

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )

    # ========================================================
    # CLEANUP
    # ========================================================

    cap.release()

    print(
        f"[STREAM] Camera {camera_id} stopped. "
        f"Total events: {total_events}"
    )