# vehicle.py

VEHICLE_CLASSES = {
    2: "CAR",
    3: "MOTORCYCLE",
    5: "BUS",
    7: "TRUCK",
}


def is_vehicle(class_id: int) -> bool:
    return int(class_id) in VEHICLE_CLASSES


def get_vehicle_name(class_id: int) -> str:
    return VEHICLE_CLASSES.get(int(class_id), "VEHICLE")
