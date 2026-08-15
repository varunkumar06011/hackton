from datetime import datetime
from orders.models import Event
from orders.services.conflict_resolver import reducer


def replay_order(order_id, up_to=None):
    events = list(Event.objects.filter(order_id=order_id))

    if not events:
        return None

    up_to_dt = None
    if up_to:
        try:
            up_to_dt = datetime.fromisoformat(up_to.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            up_to_dt = None

    final_state, timeline, rejected = reducer(events, up_to=up_to_dt)

    return {
        "order_id": order_id,
        "events_replayed": len(timeline),
        "timeline": timeline,
        "final_state": final_state,
        "rejected_events": rejected,
    }
