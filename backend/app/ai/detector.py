from ultralytics import YOLO

import cv2
import numpy as np

import os
import json

from app.services.event_service import create_intrusion_event


# ==========================================
# 1. LOAD YOLO MODEL
# ==========================================

model = YOLO("yolo11n.pt")


# ==========================================
# 2. OPEN CCTV VIDEO
# ==========================================

cap = cv2.VideoCapture("test.mp4")

if not cap.isOpened():
    print("ERROR: Could not open test.mp4")
    exit()


# ==========================================
# 3. CREATE DISPLAY WINDOW
# ==========================================

window_name = "SecureStack - Intelligent Border Surveillance"

cv2.namedWindow(
    window_name,
    cv2.WINDOW_NORMAL
)

cv2.resizeWindow(
    window_name,
    1280,
    720
)


# ==========================================
# 4. TRACKING SETTINGS
# ==========================================

# Number of consecutive frames a person
# must remain inside the zone before
# triggering an intrusion.

REQUIRED_FRAMES = 5


# Store the number of consecutive frames
# each tracked person has remained inside.

person_frames = {}


# ==========================================
# 5. CAMERA / SNAPSHOT SETTINGS
# ==========================================

CAMERA_ID = "CAM-01"

SNAPSHOT_DIR = "snapshots"

os.makedirs(
    SNAPSHOT_DIR,
    exist_ok=True
)


# ==========================================
# 6. ACTIVE INTRUSIONS
# ==========================================

# Prevent the same tracked person from
# creating duplicate events every frame.

active_intrusions = set()


# ==========================================
# 7. SESSION EVENTS
# ==========================================

# Used only for displaying a final
# session summary.

events = []


# ==========================================
# 8. MAIN VIDEO LOOP
# ==========================================

while True:

    success, frame = cap.read()

    if not success:
        break


    # ======================================
    # GET ACTUAL VIDEO SIZE
    # ======================================

    height, width = frame.shape[:2]


    # ======================================
    # CREATE RESTRICTED ZONE
    # ======================================

    # Right-side restricted area.
    #
    # Percentages make the zone independent
    # of the video's resolution.

    zone = np.array([

        [int(width * 0.65), int(height * 0.10)],

        [int(width * 0.95), int(height * 0.10)],

        [int(width * 0.95), int(height * 0.90)],

        [int(width * 0.65), int(height * 0.90)]

    ], np.int32)


    # ======================================
    # YOLO + BYTE TRACK
    # ======================================

    results = model.track(

        frame,

        persist=True,

        tracker="bytetrack.yaml",

        # Class 0 = person
        classes=[0],

        # Ignore weak detections
        conf=0.60,

        verbose=False
    )


    # ======================================
    # DRAW YOLO DETECTIONS
    # ======================================

    annotated_frame = results[0].plot()


    # ======================================
    # DRAW RESTRICTED ZONE
    # ======================================

    overlay = annotated_frame.copy()


    # Fill restricted area

    cv2.fillPoly(

        overlay,

        [zone],

        (0, 0, 255)
    )


    # Blend transparent zone

    annotated_frame = cv2.addWeighted(

        overlay,

        0.20,

        annotated_frame,

        0.80,

        0
    )


    # Draw zone boundary

    cv2.polylines(

        annotated_frame,

        [zone],

        isClosed=True,

        color=(0, 0, 255),

        thickness=5
    )


    # ======================================
    # FENCE LABEL
    # ======================================

    cv2.putText(

        annotated_frame,

        "RESTRICTED ZONE",

        (
            zone[0][0] + 10,
            zone[0][1] + 35
        ),

        cv2.FONT_HERSHEY_SIMPLEX,

        0.8,

        (0, 0, 255),

        3
    )


    # ======================================
    # INTRUSION STATUS
    # ======================================

    intrusion_detected = False


    # ======================================
    # CHECK TRACKED PERSONS
    # ======================================

    if results[0].boxes.id is not None:

        # Bounding boxes

        boxes = (
            results[0]
            .boxes
            .xyxy
            .cpu()
            .numpy()
        )


        # Track IDs

        track_ids = (

            results[0]
            .boxes
            .id
            .int()
            .cpu()
            .tolist()

        )


        # Detection confidence

        confidences = (

            results[0]
            .boxes
            .conf
            .cpu()
            .numpy()

        )


        # ==================================
        # LOOP THROUGH PERSONS
        # ==================================

        for index, (box, track_id) in enumerate(

            zip(boxes, track_ids)

        ):

            # ==================================
            # BOUNDING BOX
            # ==================================

            x1, y1, x2, y2 = map(
                int,
                box
            )


            # ==================================
            # PERSON'S FOOT POINT
            # ==================================

            # Bottom-center of bounding box.
            #
            # This approximates where the person
            # is standing on the ground.

            foot_x = int(
                (x1 + x2) / 2
            )

            foot_y = int(y2)


            # Draw foot point

            cv2.circle(

                annotated_frame,

                (foot_x, foot_y),

                7,

                (255, 255, 0),

                -1
            )


            # ==================================
            # CHECK ZONE
            # ==================================

            inside = cv2.pointPolygonTest(

                zone,

                (foot_x, foot_y),

                False
            )


            # ==================================
            # PERSON INSIDE ZONE
            # ==================================

            if inside >= 0:

                person_frames[track_id] = (

                    person_frames.get(
                        track_id,
                        0
                    ) + 1

                )


            # ==================================
            # PERSON OUTSIDE ZONE
            # ==================================

            else:

                person_frames[track_id] = 0


                # Allow the same person to
                # trigger another event if they
                # leave and re-enter.

                active_intrusions.discard(
                    track_id
                )


            # ==================================
            # INTRUSION CONFIRMED
            # ==================================

            if person_frames.get(
                track_id,
                0
            ) >= REQUIRED_FRAMES:

                intrusion_detected = True


                # ==================================
                # CREATE EVENT ONLY ONCE
                # ==================================

                if track_id not in active_intrusions:

                    # Mark this person as having
                    # an active intrusion.

                    active_intrusions.add(
                        track_id
                    )


                    # ==================================
                    # GET CONFIDENCE
                    # ==================================

                    confidence = float(
                        confidences[index]
                    )


                    # ==================================
                    # CREATE TIMESTAMP FOR FILE
                    # ==================================

                    from datetime import datetime

                    timestamp = datetime.now()

                    timestamp_string = (

                        timestamp.strftime(
                            "%Y%m%d_%H%M%S"
                        )

                    )


                    # ==================================
                    # SNAPSHOT FILENAME
                    # ==================================

                    snapshot_filename = (

                        f"intrusion_"
                        f"{CAMERA_ID}_"
                        f"{timestamp_string}_"
                        f"ID{track_id}.jpg"

                    )


                    snapshot_path = os.path.join(

                        SNAPSHOT_DIR,

                        snapshot_filename

                    )


                    # ==================================
                    # SAVE SNAPSHOT
                    # ==================================

                    cv2.imwrite(

                        snapshot_path,

                        annotated_frame

                    )


                    # ==================================
                    # CREATE EVENT THROUGH SERVICE
                    # ==================================

                    event = create_intrusion_event(

                        camera_id=CAMERA_ID,

                        track_id=track_id,

                        confidence=confidence,

                        snapshot_path=snapshot_path

                    )


                    # Keep for session summary

                    events.append(
                        event
                    )


                    # ==================================
                    # PRINT EVENT
                    # ==================================

                    print()
                    print(
                        "🚨 NEW INTRUSION EVENT"
                    )

                    print(
                        json.dumps(
                            event,
                            indent=4
                        )
                    )


                # ==================================
                # MARK PERSON AS INTRUDER
                # ==================================

                cv2.rectangle(

                    annotated_frame,

                    (x1, y1),

                    (x2, y2),

                    (0, 0, 255),

                    3

                )


                # ==================================
                # INTRUSION LABEL
                # ==================================

                cv2.putText(

                    annotated_frame,

                    f"INTRUSION - ID {track_id}",

                    (

                        x1,

                        max(
                            y1 - 10,
                            30
                        )

                    ),

                    cv2.FONT_HERSHEY_SIMPLEX,

                    0.7,

                    (0, 0, 255),

                    2

                )


    # ======================================
    # DISPLAY STATUS
    # ======================================

    if intrusion_detected:

        # ==================================
        # RED ALERT BANNER
        # ==================================

        cv2.rectangle(

            annotated_frame,

            (0, 0),

            (width, 65),

            (0, 0, 255),

            -1

        )


        cv2.putText(

            annotated_frame,

            "!!! INTRUSION ALERT !!!",

            (20, 45),

            cv2.FONT_HERSHEY_SIMPLEX,

            1.0,

            (255, 255, 255),

            3

        )


        print(
            "🚨 INTRUSION ALERT!"
        )


    else:

        # ==================================
        # SECURE STATUS
        # ==================================

        cv2.putText(

            annotated_frame,

            "STATUS: SECURE",

            (20, 40),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.9,

            (0, 255, 0),

            3

        )


    # ======================================
    # SHOW RESOLUTION
    # ======================================

    cv2.putText(

        annotated_frame,

        f"Frame: {width} x {height}",

        (
            20,
            height - 20
        ),

        cv2.FONT_HERSHEY_SIMPLEX,

        0.6,

        (255, 255, 255),

        2

    )


    # ======================================
    # DISPLAY VIDEO
    # ======================================

    cv2.imshow(

        window_name,

        annotated_frame

    )


    # ======================================
    # PRESS Q TO EXIT
    # ======================================

    if cv2.waitKey(1) & 0xFF == ord("q"):

        break


# ==========================================
# CLEANUP
# ==========================================

cap.release()

cv2.destroyAllWindows()


# ==========================================
# FINAL SESSION SUMMARY
# ==========================================

print()
print("==========================================")
print("SECURESTACK SESSION SUMMARY")
print("==========================================")

print(
    f"Total intrusion events: {len(events)}"
)


for event in events:

    print(

        f"- {event['event_type']} | "
        f"Camera: {event['camera_id']} | "
        f"Track: {event['track_id']} | "
        f"Time: {event['timestamp']}"

    )


print("==========================================")