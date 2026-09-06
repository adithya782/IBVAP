import os
import cv2
import json
import numpy as np

from app.database import SessionLocal
from app.Model.models import Camera, Zone


# ============================================================
# CONFIG
# ============================================================

CAMERA_NAME = os.getenv("CAMERA_NAME", "CAM-01")

WINDOW_NAME = "SecureStack - Virtual Fence Editor"

# Maximum display area
MAX_DISPLAY_WIDTH = 1000
MAX_DISPLAY_HEIGHT = 650


# ============================================================
# GLOBAL VARIABLES
# ============================================================

points = []

original_width = 0
original_height = 0

display_width = 0
display_height = 0

offset_x = 0
offset_y = 0


# ============================================================
# CALCULATE DISPLAY SIZE
# ============================================================

def calculate_display_size(video_width, video_height):

    scale = min(
        MAX_DISPLAY_WIDTH / video_width,
        MAX_DISPLAY_HEIGHT / video_height
    )

    width = int(video_width * scale)
    height = int(video_height * scale)

    return width, height


# ============================================================
# MOUSE CALLBACK
# ============================================================

def mouse_callback(event, x, y, flags, param):

    global points

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    # Ignore clicks outside the actual video
    if (
        x < offset_x
        or x >= offset_x + display_width
        or y < offset_y
        or y >= offset_y + display_height
    ):
        return

    # Convert display coordinates
    # to original video coordinates

    video_x = int(
        (x - offset_x)
        * original_width
        / display_width
    )

    video_y = int(
        (y - offset_y)
        * original_height
        / display_height
    )

    points.append([video_x, video_y])

    print(
        f"Point {len(points)} -> "
        f"({video_x}, {video_y})"
    )


# ============================================================
# GET CAMERA FROM DATABASE
# ============================================================

db = SessionLocal()

try:

    camera = (
        db.query(Camera)
        .filter(Camera.name == CAMERA_NAME)
        .first()
    )

    if not camera:
        raise RuntimeError(
            f"Camera '{CAMERA_NAME}' not found."
        )

    CAMERA_ID = camera.id
    VIDEO_SOURCE = camera.rtsp_url

    print()
    print("================================")
    print(" SECURESTACK VIRTUAL FENCE")
    print("================================")
    print(f"Camera ID : {CAMERA_ID}")
    print(f"Camera    : {CAMERA_NAME}")
    print(f"Source    : {VIDEO_SOURCE}")
    print("================================")
    print()

finally:

    db.close()


# ============================================================
# OPEN VIDEO
# ============================================================

cap = cv2.VideoCapture(VIDEO_SOURCE)

if not cap.isOpened():

    raise RuntimeError(
        f"Could not open video source: {VIDEO_SOURCE}"
    )


# ============================================================
# GET VIDEO DIMENSIONS
# ============================================================

ret, frame = cap.read()

if not ret:

    cap.release()

    raise RuntimeError(
        "Could not read video."
    )


original_height, original_width = frame.shape[:2]


display_width, display_height = calculate_display_size(
    original_width,
    original_height
)


print(
    f"Original video : "
    f"{original_width} x {original_height}"
)

print(
    f"Display size   : "
    f"{display_width} x {display_height}"
)


# ============================================================
# CREATE WINDOW
# ============================================================

cv2.namedWindow(
    WINDOW_NAME,
    cv2.WINDOW_NORMAL
)

cv2.resizeWindow(
    WINDOW_NAME,
    display_width,
    display_height
)

cv2.setMouseCallback(
    WINDOW_NAME,
    mouse_callback
)


# ============================================================
# MAIN LOOP
# ============================================================

while True:

    ret, frame = cap.read()

    if not ret:

        # Restart video when it reaches the end
        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            0
        )

        continue


    display_frame = cv2.resize(
        frame,
        (display_width, display_height),
        interpolation=cv2.INTER_AREA
    )


    # ========================================================
    # DRAW POINTS
    # ========================================================

    for i, point in enumerate(points):

        x, y = point

        screen_x = int(
            x * display_width / original_width
        )

        screen_y = int(
            y * display_height / original_height
        )

        cv2.circle(
            display_frame,
            (screen_x, screen_y),
            6,
            (0, 255, 255),
            -1
        )

        cv2.putText(
            display_frame,
            str(i + 1),
            (
                screen_x + 8,
                screen_y - 8
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2
        )


    # ========================================================
    # DRAW LINES
    # ========================================================

    if len(points) >= 2:

        screen_points = []

        for x, y in points:

            screen_x = int(
                x * display_width / original_width
            )

            screen_y = int(
                y * display_height / original_height
            )

            screen_points.append(
                [screen_x, screen_y]
            )


        polygon = np.array(
            screen_points,
            dtype=np.int32
        )

        cv2.polylines(
            display_frame,
            [polygon],
            False,
            (0, 255, 255),
            2
        )


    # ========================================================
    # DRAW CLOSED POLYGON
    # ========================================================

    if len(points) >= 3:

        screen_points = []

        for x, y in points:

            screen_x = int(
                x * display_width / original_width
            )

            screen_y = int(
                y * display_height / original_height
            )

            screen_points.append(
                [screen_x, screen_y]
            )


        polygon = np.array(
            screen_points,
            dtype=np.int32
        )


        # Transparent fill

        overlay = display_frame.copy()

        cv2.fillPoly(
            overlay,
            [polygon],
            (0, 255, 255)
        )

        display_frame = cv2.addWeighted(
            overlay,
            0.12,
            display_frame,
            0.88,
            0
        )


        # Polygon border

        cv2.polylines(
            display_frame,
            [polygon],
            True,
            (0, 255, 255),
            2
        )


    # ========================================================
    # INSTRUCTIONS
    # ========================================================

    instruction_height = 65

    cv2.rectangle(
        display_frame,
        (0, 0),
        (
            display_width,
            instruction_height
        ),
        (0, 0, 0),
        -1
    )


    cv2.putText(
        display_frame,
        "VIRTUAL FENCE EDITOR",
        (15, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2
    )


    cv2.putText(
        display_frame,
        "Click = Add Point | ENTER/S = Save | R = Reset | Q = Quit",
        (15, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (255, 255, 255),
        1
    )


    # ========================================================
    # SHOW
    # ========================================================

    cv2.imshow(
        WINDOW_NAME,
        display_frame
    )


    # ========================================================
    # KEYBOARD
    # ========================================================

    key = cv2.waitKey(20) & 0xFF


    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    if key == 13 or key == ord("s"):

        if len(points) < 3:

            print()
            print(
                "❌ Need at least 3 points "
                "to create a fence."
            )

            continue


        print()
        print("================================")
        print(" FENCE CREATED")
        print("================================")

        print(
            json.dumps(
                {
                    "points": points
                },
                indent=4
            )
        )


        # ====================================================
        # SAVE TO DATABASE
        # ====================================================

        db = SessionLocal()

        try:

            zone = Zone(
                camera_id=CAMERA_ID,

                name="Border Restricted Zone",

                zone_type="RESTRICTED",

                coordinates={
                    "points": points
                }
            )


            db.add(zone)

            db.commit()

            db.refresh(zone)


            print()
            print("✅ FENCE SAVED TO POSTGRESQL")
            print(f"Zone ID : {zone.id}")
            print(f"Camera  : {CAMERA_ID}")
            print(f"Points  : {len(points)}")
            print()


        except Exception as e:

            db.rollback()

            print()
            print("❌ DATABASE ERROR")
            print(e)
            print()


        finally:

            db.close()


    # --------------------------------------------------------
    # RESET
    # --------------------------------------------------------

    elif key == ord("r"):

        points.clear()

        print()
        print("🔄 Fence cleared.")
        print()


    # --------------------------------------------------------
    # QUIT
    # --------------------------------------------------------

    elif key == ord("q") or key == 27:

        print()
        print("Exiting...")
        break


# ============================================================
# CLEANUP
# ============================================================

cap.release()

cv2.destroyAllWindows()

print()
print("Virtual Fence Editor stopped.")