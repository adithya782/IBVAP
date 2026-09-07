import os

import cv2
import requests

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.Model.models import Camera


# ============================================================
# CONFIGURATION
# ============================================================

CAMERA_NAME = os.getenv("CAMERA_NAME", "CAM-01")

API_URL = os.getenv(
    "API_URL",
    "http://127.0.0.1:8000/zones/"
)

WINDOW_NAME = "Virtual Border Zone Builder"


# ============================================================
# DRAWING STATE
# ============================================================

current_points = []


# ============================================================
# MOUSE CALLBACK
# ============================================================

def draw_polygon_event(event, x, y, flags, param):

    global current_points

    # LEFT CLICK → add point
    if event == cv2.EVENT_LBUTTONDOWN:

        current_points.append((x, y))

        print(
            f"Point added: ({x}, {y})"
        )

    # RIGHT CLICK → undo
    elif event == cv2.EVENT_RBUTTONDOWN:

        if current_points:

            removed = current_points.pop()

            print(
                f"Point removed: {removed}"
            )


# ============================================================
# FETCH CAMERA FROM DATABASE
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
            f"Camera '{CAMERA_NAME}' "
            "not found in database."
        )

    camera_id = camera.id
    video_source = camera.rtsp_url

finally:

    db.close()


# ============================================================
# START
# ============================================================

print()
print("=" * 60)
print("        SECURESTACK VIRTUAL BORDER BUILDER")
print("=" * 60)

print(
    "Camera       : "
    f"{CAMERA_NAME}"
)

print(
    "Camera ID    : "
    f"{camera_id}"
)

print(
    "Video Source : "
    f"{video_source}"
)

print()
print("CONTROLS")
print("-" * 60)
print("LEFT CLICK   → Add polygon point")
print("RIGHT CLICK  → Remove last point")
print("S            → Save zone")
print("R            → Reset polygon")
print("Q / ESC      → Quit")
print("=" * 60)
print()


# ============================================================
# OPEN VIDEO
# ============================================================

cap = cv2.VideoCapture(
    video_source
)

if not cap.isOpened():

    raise RuntimeError(
        f"Could not open video source: "
        f"{video_source}"
    )


cv2.namedWindow(
    WINDOW_NAME,
    cv2.WINDOW_NORMAL
)

cv2.setMouseCallback(
    WINDOW_NAME,
    draw_polygon_event
)


# ============================================================
# VIDEO LOOP
# ============================================================

while True:

    ret, frame = cap.read()

    if not ret:

        # Restart video if it is a file
        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            0
        )

        ret, frame = cap.read()

        if not ret:

            print(
                "⚠️ Failed to read video frame."
            )

            break

    # --------------------------------------------------------
    # DRAW POINTS
    # --------------------------------------------------------

    if current_points:

        # Draw points

        for point in current_points:

            cv2.circle(
                frame,
                point,
                5,
                (0, 255, 0),
                -1
            )

        # Draw connecting lines

        if len(current_points) >= 2:

            for i in range(
                len(current_points) - 1
            ):

                cv2.line(
                    frame,
                    current_points[i],
                    current_points[i + 1],
                    (0, 255, 0),
                    2
                )

        # Close polygon visually

        if len(current_points) >= 3:

            cv2.line(
                frame,
                current_points[-1],
                current_points[0],
                (0, 255, 255),
                2
            )

    # --------------------------------------------------------
    # INFORMATION ON SCREEN
    # --------------------------------------------------------

    cv2.putText(
        frame,
        "Draw ONE zone at a time",
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame,
        "S = Save | R = Reset | Q = Quit",
        (20, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    # --------------------------------------------------------
    # SHOW
    # --------------------------------------------------------

    cv2.imshow(
        WINDOW_NAME,
        frame
    )

    key = cv2.waitKey(20) & 0xFF

    # ========================================================
    # SAVE
    # ========================================================

    if key == ord("s") or key == ord("S"):

        if len(current_points) < 3:

            print()
            print(
                "⚠️ Need at least "
                "3 points."
            )

            continue

        print()
        print("=" * 50)
        print("          SAVE ZONE")
        print("=" * 50)

        print(
            "[1] PROXIMITY"
        )

        print(
            "    Near-border monitoring zone"
        )

        print()

        print(
            "[2] PROTECTED"
        )

        print(
            "    Our protected area"
        )

        print("=" * 50)

        choice = input(
            "Enter choice (1 or 2): "
        ).strip()

        # ----------------------------------------------------
        # PROXIMITY
        # ----------------------------------------------------

        if choice == "1":

            zone_name = (
                "Border Proximity Zone"
            )

            zone_type = "PROXIMITY"

        # ----------------------------------------------------
        # PROTECTED
        # ----------------------------------------------------

        elif choice == "2":

            zone_name = (
                "Protected Area"
            )

            zone_type = "PROTECTED"

        # ----------------------------------------------------
        # INVALID
        # ----------------------------------------------------

        else:

            print(
                "❌ Invalid choice."
            )

            continue

        # ====================================================
        # CREATE API PAYLOAD
        # ====================================================

        payload = {

            "camera_id": camera_id,

            "name": zone_name,

            "zone_type": zone_type,

            "coordinates": {

                "points": [
                    [
                        int(point[0]),
                        int(point[1])
                    ]

                    for point in current_points
                ]

            }

        }

        print()
        print(
            "Saving zone..."
        )

        print(
            f"Name : {zone_name}"
        )

        print(
            f"Type : {zone_type}"
        )

        # ====================================================
        # SEND TO FASTAPI
        # ====================================================

        try:

            response = requests.post(
                API_URL,
                json=payload,
                timeout=5
            )

            if response.status_code in (
                200,
                201
            ):

                print()
                print(
                    f"✅ Zone '{zone_name}' "
                    "saved successfully!"
                )

                try:

                    print(
                        "API Response:",
                        response.json()
                    )

                except Exception:

                    pass

                # Clear drawing

                current_points = []

                print()

            else:

                print()

                print(
                    "❌ Failed to save zone."
                )

                print(
                    "HTTP Status:",
                    response.status_code
                )

                print(
                    "Response:",
                    response.text
                )

        except requests.exceptions.RequestException as e:

            print()

            print(
                "❌ Could not connect "
                "to FastAPI."
            )

            print(
                f"API URL: {API_URL}"
            )

            print(
                f"Error: {e}"
            )

    # ========================================================
    # RESET
    # ========================================================

    elif key == ord("r") or key == ord("R"):

        current_points = []

        print(
            "🔄 Current polygon cleared."
        )

    # ========================================================
    # QUIT
    # ========================================================

    elif (
        key == ord("q")
        or key == 27
    ):

        print(
            "Exiting Virtual Border Builder."
        )

        break


# ============================================================
# CLEANUP
# ============================================================

cap.release()

cv2.destroyAllWindows()

print()
print(
    "Virtual Border Builder closed."
)