from fastapi import APIRouter
import json
import os


router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


EVENTS_FILE = "events.json"


# ==========================================
# LOAD EVENTS
# ==========================================

def load_events():

    if not os.path.exists(EVENTS_FILE):
        return []

    try:

        with open(EVENTS_FILE, "r") as file:
            return json.load(file)

    except json.JSONDecodeError:

        return []


# ==========================================
# GET ALL EVENTS
# ==========================================

@router.get("/")
def get_events():

    return load_events()


# ==========================================
# GET SINGLE EVENT
# ==========================================

@router.get("/{event_id}")
def get_event(event_id: int):

    events = load_events()

    for event in events:

        if event.get("id") == event_id:
            return event

    return {
        "message": "Event not found"
    }