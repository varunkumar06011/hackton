from datetime import timedelta
from django.utils import timezone
from orders.models import Event, AnomalyAlert


def detect_anomalies(order_id, source):
    alerts = []
    now = timezone.now()

    recent_events = Event.objects.filter(
        order_id=order_id,
        source=source,
        received_at__gte=now - timedelta(minutes=10),
    ).order_by("received_at")

    late_count = 0
    for e in recent_events:
        if e.timestamp < e.received_at - timedelta(minutes=1):
            late_count += 1

    if late_count > 3:
        alert = AnomalyAlert.objects.create(
            source=source,
            pattern_type="repeated_late",
            description=f"{late_count} late events from source '{source}' for order '{order_id}' in the last 10 minutes.",
            order_id=order_id,
        )
        alerts.append(alert)

    all_events = Event.objects.filter(order_id=order_id).order_by("timestamp")
    statuses = [e.status for e in all_events]
    oscillations = 0
    for i in range(1, len(statuses) - 1):
        if statuses[i] != statuses[i - 1] and statuses[i] != statuses[i + 1]:
            oscillations += 1
    if oscillations > 3:
        alert = AnomalyAlert.objects.create(
            source=source,
            pattern_type="status_oscillation",
            description=f"Status oscillated {oscillations} times for order '{order_id}'.",
            order_id=order_id,
        )
        alerts.append(alert)

    return alerts
