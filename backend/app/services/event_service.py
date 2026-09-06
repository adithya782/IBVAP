from datetime import datetime
import json
import os


EVENTS_FILE = "events.json"


def create_intrusion_event(
    camera_id,
    track_id,
    confidence,
    snapshot_path
):
    """
    Create a standardized intrusion event.
    """

    event = {
        "camera_id": camera_id,
        "track_id": int(track_id),
        "timestamp": datetime.now().isoformat(),
        "event_type": "INTRUSION",
        "severity": "CRITICAL",
        "confidence": round(float(confidence), 2),
        "snapshot": snapshot_path,
        "status": "NEW"
    }

    # --------------------------------------
    # TEMPORARY STORAGE
    # --------------------------------------
    # For now we store events in JSON.
    # PostgreSQL will replace this later.

    events = []

    if os.path.exists(EVENTS_FILE):

        try:

            with open(EVENTS_FILE, "r") as file:
                events = json.load(file)

        except (json.JSONDecodeError, FileNotFoundError):

            events = []

    # Generate simple event ID

    event["id"] = len(events) + 1

    events.append(event)

    with open(EVENTS_FILE, "w") as file:

        json.dump(
            events,
            file,
            indent=4
        )

    return event