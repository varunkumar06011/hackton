from django.db.models import Subquery, OuterRef
from orders.models import OrderState


def get_current_state(order_id):
    return OrderState.objects.filter(order_id=order_id).order_by("-version").first()


def get_state_at_version(order_id, version):
    return OrderState.objects.filter(order_id=order_id, version=version).first()


def get_state_at_timestamp(order_id, timestamp):
    return OrderState.objects.filter(
        order_id=order_id, last_event_timestamp__lte=timestamp
    ).order_by("-version").first()


def get_history(order_id):
    return list(OrderState.objects.filter(order_id=order_id).order_by("version"))


def list_all_orders():
    latest_ids = (
        OrderState.objects
        .filter(order_id=OuterRef("order_id"))
        .order_by("-version")
        .values("id")[:1]
    )
    return list(
        OrderState.objects
        .filter(id__in=Subquery(latest_ids))
        .order_by("-version")
    )
