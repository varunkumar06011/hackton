from orders.models import DriverNotification


def notify_driver(order_id, status):
    if status not in ["ready", "delivered"]:
        return None

    message = f"Order {order_id} is now {status}. Please proceed."
    notification = DriverNotification.objects.create(
        order_id=order_id,
        driver_id="DRV-001",
        message=message,
        status="sent",
    )
    return notification
