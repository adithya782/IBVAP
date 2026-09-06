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

CAMERA_NAME = "CAM-01"

MODEL_PATH = "yolo11n.pt"

CONFIDENCE = 0.30
IMAGE_SIZE = 640

REQUIRED_INSIDE_FRAMES = 5

SNAPSHOT_DIR = "snapshots"

WINDOW_NAME = "SecureStack - Border Surveillance"


# ============================================================
# LOAD CAMERA + ZONES
# ============================================================

db: Session = SessionLocal()

try:
    camera = (
        db.query(Camera)
        .filter(Camera.name == CAMERA_NAME)
        .first()
    )

    if not camera:
        raise RuntimeError(
            f"Camera '{CAMERA_NAME}' not found in database."
        )

    camera_id = camera.id

    zones = (
        db.query(Zone)
        .filter(Zone.camera_id == camera_id)
        .all()
    )

finally:
    db.close()


if not zones:
    raise RuntimeError(
        f"No virtual fence found for camera '{CAMERA_NAME}'. "
        "Create one using virtual_fence.py first."
    )


# ============================================================
# PREPARE ZONES
# ============================================================

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


if not zone_polygons:
    raise RuntimeError("No valid virtual fence polygons found.")


# ============================================================
# LOAD YOLO
# ============================================================

model = YOLO(MODEL_PATH)

print()
print("==============================================")
print(" SECURESTACK IBVAP - BORDER SURVEILLANCE")
print("==============================================")
print(f"Camera      : {CAMERA_NAME}")
print(f"Camera ID   : {camera_id}")
print(f"Fences      : {len(zone_polygons)}")
print(f"Confidence  : {CONFIDENCE}")
print(f"Image Size  : {IMAGE_SIZE}")
print("==============================================")
print()


# ============================================================
# OPEN VIDEO / CAMERA
# ============================================================

video_source = camera.rtsp_url

cap = cv2.VideoCapture(video_source)

if not cap.isOpened():
    raise RuntimeError(
        f"Could not open camera/video: {video_source}"
    )


# ============================================================
# STATE
# ============================================================

inside_counter = {}

confirmed_tracks = set()

total_events = 0

frame_number = 0


# ============================================================
# SNAPSHOT DIRECTORY
# ============================================================

os.makedirs(SNAPSHOT_DIR, exist_ok=True)


# ============================================================
# DISPLAY
# ============================================================

cv2.namedWindow(
    WINDOW_NAME,
    cv2.WINDOW_NORMAL
)

cv2.resizeWindow(
    WINDOW_NAME,
    1100,
    700
)


# ============================================================
# MAIN LOOP
# ============================================================

while True:

    ret, frame = cap.read()

    if not ret:
        print()
        print("Video ended / camera disconnected.")
        break

    frame_number += 1


    # ========================================================
    # YOLO + BYTE TRACK
    # ========================================================

    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",

        # Person + car + motorcycle + bus + truck
        classes=[0, 2, 3, 5, 7],

        conf=CONFIDENCE,
        imgsz=IMAGE_SIZE,
        verbose=False
    )


    # ========================================================
    # DRAW VIRTUAL FENCES
    # ========================================================

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


    # ========================================================
    # PROCESS DETECTIONS
    # ========================================================

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


        # ----------------------------------------------------
        # PRINT TRACK IDS
        # ----------------------------------------------------

        print(
            f"[FRAME {frame_number}] "
            f"TRACKED IDS: {track_ids}"
        )


        # ====================================================
        # PROCESS EACH OBJECT
        # ====================================================

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


            # =================================================
            # VEHICLE
            # =================================================

            if is_vehicle(class_id):

                vehicle_name = get_vehicle_name(class_id)

                print(
                    f"    🚗 {vehicle_name} "
                    f"| ID={track_id} "
                    f"| Confidence={confidence:.2f}"
                )


                # Vehicle box
                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (255, 180, 0),
                    2
                )


                # Vehicle label
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


            # =================================================
            # PERSON
            # =================================================

            if class_id != 0:
                continue


            # -------------------------------------------------
            # FOOT POINT
            # -------------------------------------------------

            foot_x = int((x1 + x2) / 2)
            foot_y = int(y2)

            foot_point = (
                foot_x,
                foot_y
            )


            # -------------------------------------------------
            # CHECK VIRTUAL FENCES
            # -------------------------------------------------

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


            # =================================================
            # PERSON INSIDE ZONE
            # =================================================

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


                print(
                    f"    👤 ID={track_id} | "
                    f"Foot={foot_point} | "
                    f"🚨 INSIDE | "
                    f"Zone={zone_id} | "
                    f"Frames={current_frames}"
                )


                # Person box - red
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


                # =================================================
                # CONFIRM INTRUSION
                # =================================================

                if (
                    current_frames >= REQUIRED_INSIDE_FRAMES
                    and key not in confirmed_tracks
                ):

                    print()
                    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    print("🚨 INTRUSION CONFIRMED")
                    print(f"Track ID : {track_id}")
                    print(f"Zone     : {zone_id}")
                    print(f"Frames   : {current_frames}")
                    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    print()


                    # ------------------------------------------------
                    # SNAPSHOT
                    # ------------------------------------------------

                    timestamp = datetime.now()

                    filename = (
                        f"intrusion_"
                        f"{camera_id}_"
                        f"{track_id}_"
                        f"{timestamp.strftime('%Y%m%d_%H%M%S')}"
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


                    # ------------------------------------------------
                    # DATABASE EVENT
                    # ------------------------------------------------

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


            # =================================================
            # PERSON OUTSIDE ZONE
            # =================================================

            else:

                print(
                    f"    👤 ID={track_id} | "
                    f"Foot={foot_point} | "
                    f"OUTSIDE"
                )


                # Reset inside counters for this track
                for key in list(inside_counter.keys()):

                    if key[0] == track_id:

                        inside_counter[key] = 0


                # Person box - green
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


    # ========================================================
    # NO TRACKS
    # ========================================================

    else:

        if frame_number % 10 == 0:

            print(
                f"[FRAME {frame_number}] "
                "❌ NO TRACKS"
            )


    # ========================================================
    # SHOW FRAME
    # ========================================================

    cv2.imshow(
        WINDOW_NAME,
        frame
    )


    # ========================================================
    # QUIT
    # ========================================================

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q") or key == 27:
        print()
        print("Detector stopped.")
        break


# ============================================================
# CLEANUP
# ============================================================

cap.release()

cv2.destroyAllWindows()


# ============================================================
# SESSION SUMMARY
# ============================================================

print()
print("================================================")
print(" SESSION SUMMARY")
print("================================================")
print(f"Camera       : {CAMERA_NAME}")
print(f"Fences       : {len(zone_polygons)}")
print(f"Events       : {total_events}")
print("================================================")