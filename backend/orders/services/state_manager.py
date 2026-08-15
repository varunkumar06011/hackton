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
    order_ids = OrderState.objects.values_list("order_id", flat=True).distinct()
    return [get_current_state(oid) for oid in order_ids]
