from datetime import datetime
import time
from django.http import JsonResponse
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from orders.models import (
    Event, OrderState, AuditLog, Location, MenuItem,
    AnomalyAlert, DriverNotification,
)
from orders.serializers import (
    EventSerializer, OrderStateSerializer, AuditLogSerializer,
    LocationSerializer, MenuItemSerializer, AnomalyAlertSerializer,
    DriverNotificationSerializer,
)
from orders.services.ingestion import validate_event, check_duplicate, save_event
from orders.services.conflict_resolver import resolve_event
from orders.services.state_manager import (
    get_current_state, get_state_at_version, get_state_at_timestamp,
    get_history, list_all_orders,
)
from orders.services.audit_generator import get_audit_trail
from orders.services.replay_engine import replay_order as do_replay
from orders.services.driver_notifier import notify_driver
from orders.services.anomaly_detector import detect_anomalies
from orders.services.inventory_manager import get_location_inventory


@api_view(["POST"])
def submit_event(request):
    data = request.data
    valid, result = validate_event(data)

    if not valid:
        return Response({"status": "rejected", "errors": result}, status=400)

    existing = check_duplicate(result["event_id"])
    if existing:
        current = get_current_state(result["order_id"])
        return Response({
            "status": "duplicate_ignored",
            "event_id": result["event_id"],
            "existing_state": OrderStateSerializer(current).data if current else None,
        }, status=200)

    try:
        event = save_event(result)
    except IntegrityError:
        current = get_current_state(result["order_id"])
        return Response({
            "status": "duplicate_ignored",
            "event_id": result["event_id"],
            "existing_state": OrderStateSerializer(current).data if current else None,
        }, status=200)

    t0 = time.perf_counter()
    order_state, audit = resolve_event(event)
    t1 = time.perf_counter()
    processing_time_ms = round((t1 - t0) * 1000, 2)

    try:
        notify_driver(order_state.order_id, order_state.status)
    except Exception:
        pass

    try:
        detect_anomalies(order_state.order_id, event.source)
    except Exception:
        pass

    return Response({
        "status": "processed",
        "processing_time_ms": processing_time_ms,
        "order_state": OrderStateSerializer(order_state).data,
        "audit": {
            "resolution_rule": audit.resolution_rule,
            "explanation": audit.rule_explanation,
            "event_ids_considered": audit.event_ids_considered,
        },
    }, status=201)


@api_view(["GET"])
def list_orders(request):
    states = list_all_orders()
    return Response(OrderStateSerializer(states, many=True).data)


@api_view(["GET"])
def get_order(request, order_id):
    state = get_current_state(order_id)
    if not state:
        return Response({"error": "Order not found"}, status=404)
    return Response(OrderStateSerializer(state).data)


@api_view(["GET"])
def get_order_history(request, order_id):
    history = get_history(order_id)
    if not history:
        return Response({"error": "Order not found"}, status=404)
    return Response(OrderStateSerializer(history, many=True).data)


@api_view(["GET"])
def get_audit(request, order_id):
    trail = get_audit_trail(order_id)
    if not trail:
        return Response({"error": "No audit trail found"}, status=404)
    return Response(AuditLogSerializer(trail, many=True).data)


@api_view(["GET"])
def replay_order(request, order_id):
    up_to = request.GET.get("up_to")
    result = do_replay(order_id, up_to=up_to)
    if not result:
        return Response({"error": "Order not found"}, status=404)
    return Response(result)


@api_view(["GET"])
def get_state(request, order_id):
    version = request.GET.get("version")
    timestamp = request.GET.get("timestamp")

    if version:
        state = get_state_at_version(order_id, int(version))
    elif timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            state = get_state_at_timestamp(order_id, dt)
        except ValueError:
            return Response({"error": "Invalid timestamp format"}, status=400)
    else:
        return Response({"error": "Provide 'version' or 'timestamp' query param"}, status=400)

    if not state:
        return Response({"error": "State not found"}, status=404)
    return Response(OrderStateSerializer(state).data)


@api_view(["GET"])
def health_check(request):
    return Response({"status": "healthy", "timestamp": timezone.now().isoformat()})


@api_view(["GET"])
def list_locations(request):
    locations = Location.objects.all()
    return Response(LocationSerializer(locations, many=True).data)


@api_view(["GET"])
def get_inventory(request, location_id):
    items = get_location_inventory(location_id)
    return Response({"location_id": location_id, "items": items})


@api_view(["POST"])
def notify_driver_endpoint(request):
    order_id = request.data.get("order_id")
    status = request.data.get("status", "ready")
    notification = notify_driver(order_id, status)
    if notification:
        return Response(DriverNotificationSerializer(notification).data, status=201)
    return Response({"error": "Notification not triggered for this status"}, status=400)


@api_view(["GET"])
def list_anomalies(request):
    anomalies = AnomalyAlert.objects.all()
    return Response(AnomalyAlertSerializer(anomalies, many=True).data)


@api_view(["GET"])
def get_stats(request):
    total_events = Event.objects.count()
    total_orders = OrderState.objects.values_list("order_id", flat=True).distinct().count()
    total_states = OrderState.objects.count()
    total_audit = AuditLog.objects.count()
    rejected_events = AuditLog.objects.filter(resolution_rule="invalid_transition_rejected").count()
    duplicate_events = AuditLog.objects.filter(resolution_rule="duplicate_ignored").count()
    return Response({
        "total_events": total_events,
        "total_orders": total_orders,
        "total_state_versions": total_states,
        "total_audit_entries": total_audit,
        "rejected_events": rejected_events,
        "duplicate_events": duplicate_events,
        "timestamp": timezone.now().isoformat(),
    })
