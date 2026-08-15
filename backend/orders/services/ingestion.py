from django.conf import settings
from orders.models import Event

VALID_SOURCES = ["pos", "mobile", "web"]
VALID_STATUSES = ["pending", "preparing", "ready", "delivered", "cancelled"]


def validate_event(data):
    errors = []

    required_fields = ["event_id", "source", "order_id", "timestamp", "status"]
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"Missing required field: {field}")

    if errors:
        return False, errors

    if data.get("source") not in VALID_SOURCES:
        errors.append(f"Invalid source. Must be one of: {VALID_SOURCES}")

    if data.get("status") not in VALID_STATUSES:
        errors.append(f"Invalid status. Must be one of: {VALID_STATUSES}")

    items = data.get("items", [])
    if items is not None:
        if not isinstance(items, list):
            errors.append("items must be a list")
        else:
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"items[{i}] must be an object")
                    continue
                if "name" not in item or not item["name"]:
                    errors.append(f"items[{i}].name is required")
                if "quantity" not in item or not isinstance(item.get("quantity"), int) or item["quantity"] < 0:
                    errors.append(f"items[{i}].quantity must be a non-negative integer")

    if errors:
        return False, errors

    cleaned = {
        "event_id": data["event_id"],
        "source": data["source"],
        "order_id": data["order_id"],
        "timestamp": data["timestamp"],
        "items": data.get("items", []),
        "status": data["status"],
        "location_id": data.get("location_id"),
    }

    return True, cleaned


def check_duplicate(event_id):
    return Event.objects.filter(event_id=event_id).first()


def save_event(data):
    event = Event.objects.create(
        event_id=data["event_id"],
        order_id=data["order_id"],
        source=data["source"],
        timestamp=data["timestamp"],
        items=data.get("items", []),
        status=data["status"],
        location_id=data.get("location_id"),
        raw_payload=data,
        processed=False,
    )
    return event
