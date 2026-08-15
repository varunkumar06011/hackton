from django.conf import settings
from orders.models import Event, OrderState, AuditLog

SOURCE_PRIORITY = settings.SOURCE_PRIORITY
VALID_TRANSITIONS = settings.VALID_TRANSITIONS


def canonical_sort_key(event):
    return (event.timestamp, SOURCE_PRIORITY.get(event.source, 99), event.event_id)


def merge_items(current_items, new_items):
    if not new_items:
        return current_items

    result = {item["name"]: item["quantity"] for item in current_items}

    for item in new_items:
        name = item["name"]
        qty = item["quantity"]
        if qty == 0:
            result.pop(name, None)
        else:
            result[name] = qty

    return [{"name": k, "quantity": v} for k, v in result.items()]


def is_valid_transition(current_status, new_status):
    if current_status is None:
        return True
    allowed = VALID_TRANSITIONS.get(current_status, [])
    return new_status in allowed


def reducer(events, up_to=None):
    if up_to:
        events = [e for e in events if e.timestamp <= up_to]

    sorted_events = sorted(events, key=canonical_sort_key)

    state = {
        "status": None,
        "items": [],
        "last_event_id": None,
        "last_event_timestamp": None,
        "source_of_truth": None,
    }

    timeline = []
    rejected_events = []
    step = 0

    for event in sorted_events:
        step += 1
        current_status = state["status"]

        if current_status is None:
            rule = "initial_event"
            state["status"] = event.status
        elif event.status == current_status:
            rule = "no_status_change"
        elif is_valid_transition(current_status, event.status):
            rule = "valid_transition"
            state["status"] = event.status
        else:
            rule = "invalid_transition_rejected"
            rejected_events.append(event.event_id)

        state["items"] = merge_items(state["items"], event.items)
        state["last_event_id"] = event.event_id
        state["last_event_timestamp"] = event.timestamp.isoformat()
        state["source_of_truth"] = event.source

        snapshot = {
            "step": step,
            "event_id": event.event_id,
            "source": event.source,
            "timestamp": event.timestamp.isoformat(),
            "rule": rule,
            "state_after": {
                "status": state["status"],
                "items": list(state["items"]),
                "last_event_id": state["last_event_id"],
                "last_event_timestamp": state["last_event_timestamp"],
                "source_of_truth": state["source_of_truth"],
            },
        }
        timeline.append(snapshot)

    return state, timeline, rejected_events


def generate_explanation(rule, event, state, rejected_events, timeline=None):
    if timeline and len(timeline) >= 2:
        same_ts_events = []
        last_ts = timeline[-1]["timestamp"]
        for step in timeline:
            if step["timestamp"] == last_ts:
                same_ts_events.append(step)
        if len(same_ts_events) > 1:
            first = same_ts_events[0]
            second = same_ts_events[1]
            if second["rule"] == "invalid_transition_rejected":
                return (
                    f"Events {first['event_id']} ({first['source']}) and {second['event_id']} ({second['source']}) "
                    f"share timestamp {last_ts}. {first['source']} processed first (priority). "
                    f"{second['event_id']} was then rejected: invalid transition "
                    f"{state['status']}→{second.get('state_after', {}).get('status', 'unknown')}. "
                    f"Status remains '{state['status']}'."
                )
            elif second["rule"] == "no_status_change":
                return (
                    f"Events {first['event_id']} ({first['source']}) and {second['event_id']} ({second['source']}) "
                    f"share timestamp {last_ts}. {first['source']} processed first (priority tiebreak). "
                    f"{second['event_id']} confirmed same status '{state['status']}'. No conflict."
                )
            else:
                return (
                    f"Events {first['event_id']} ({first['source']}) and {second['event_id']} ({second['source']}) "
                    f"share timestamp {last_ts}. {first['source']} won priority tiebreak (processed first). "
                    f"Final status: '{state['status']}'."
                )

    explanations = {
        "initial_event": f"First event for order {event.order_id}. Status set to '{event.status}' from source '{event.source}'.",
        "no_status_change": f"Event {event.event_id} from '{event.source}' confirmed status '{event.status}'. Items merged.",
        "valid_transition": f"Event {event.event_id} from '{event.source}' transitioned status to '{event.status}'. Valid transition.",
        "invalid_transition_rejected": f"Event {event.event_id} from '{event.source}' proposed invalid status transition to '{event.status}'. Rejected. Status remains '{state['status']}'.",
        "duplicate_ignored": f"Event {event.event_id} was already processed. No state change.",
    }
    return explanations.get(rule, f"Rule '{rule}' applied for event {event.event_id}.")


def resolve_event(event):
    all_events = list(Event.objects.filter(order_id=event.order_id))

    final_state, timeline, rejected = reducer(all_events)

    prev_state = OrderState.objects.filter(order_id=event.order_id).order_by("-version").first()
    prev_version = prev_state.version if prev_state else -1
    new_version = prev_version + 1

    last_snapshot = timeline[-1] if timeline else None
    rule = last_snapshot["rule"] if last_snapshot else "initial_event"

    event_snapshot = None
    for step in timeline:
        if step["event_id"] == event.event_id:
            event_snapshot = step
            rule = step["rule"]
            break
    if not event_snapshot and last_snapshot:
        rule = last_snapshot["rule"]

    order_state = OrderState.objects.create(
        order_id=event.order_id,
        version=new_version,
        status=final_state["status"] or "pending",
        items=final_state["items"],
        last_event_id=final_state["last_event_id"] or event.event_id,
        last_event_timestamp=event.timestamp,
        source_of_truth=final_state["source_of_truth"] or event.source,
    )

    events_detail = [
        {
            "event_id": e.event_id,
            "source": e.source,
            "timestamp": e.timestamp.isoformat(),
            "status": e.status,
            "items": e.items,
        }
        for e in sorted(all_events, key=canonical_sort_key)
    ]

    explanation = generate_explanation(rule, event, final_state, rejected, timeline=timeline)

    audit = AuditLog.objects.create(
        order_id=event.order_id,
        event_ids_considered=[e.event_id for e in sorted(all_events, key=canonical_sort_key)],
        events_detail=events_detail,
        resolution_rule=rule,
        rule_explanation=explanation,
        previous_state={
            "status": prev_state.status,
            "items": prev_state.items,
            "version": prev_state.version,
        } if prev_state else {},
        final_state={
            "status": order_state.status,
            "items": order_state.items,
            "version": order_state.version,
        },
    )

    if event.location_id and final_state["items"]:
        try:
            from orders.services.inventory_manager import check_inventory, reserve_inventory
            inv_check = check_inventory(event.location_id, final_state["items"])
            if inv_check["available"]:
                reserve_inventory(event.order_id, final_state["items"], event.location_id)
            else:
                shortage_names = ", ".join(s["name"] for s in inv_check["shortages"])
                audit.rule_explanation += f" Inventory shortage for: {shortage_names}."
                audit.save()
        except Exception:
            pass

    event.processed = True
    event.save()

    return order_state, audit
