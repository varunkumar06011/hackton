from rest_framework import serializers
from orders.models import Event, OrderState, AuditLog, Location, MenuItem, AnomalyAlert, DriverNotification


class EventSerializer(serializers.Serializer):
    event_id = serializers.CharField(max_length=100)
    source = serializers.ChoiceField(choices=["pos", "mobile", "web"])
    order_id = serializers.CharField(max_length=100)
    timestamp = serializers.DateTimeField()
    items = serializers.ListField(
        child=serializers.DictField(), required=False, allow_empty=True, default=list
    )
    status = serializers.ChoiceField(
        choices=["pending", "preparing", "ready", "delivered", "cancelled"]
    )


class OrderStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderState
        fields = "__all__"


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = "__all__"


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = "__all__"


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = "__all__"


class AnomalyAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyAlert
        fields = "__all__"


class DriverNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverNotification
        fields = "__all__"
