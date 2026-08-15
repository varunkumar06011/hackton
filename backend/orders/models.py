from django.db import models


class Event(models.Model):
    event_id = models.CharField(max_length=100, unique=True, db_index=True)
    order_id = models.CharField(max_length=100, db_index=True)
    source = models.CharField(max_length=20)
    timestamp = models.DateTimeField()
    items = models.JSONField(default=list)
    status = models.CharField(max_length=20)
    location_id = models.CharField(max_length=100, blank=True, null=True)
    raw_payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]


class OrderState(models.Model):
    order_id = models.CharField(max_length=100, db_index=True)
    version = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default="pending")
    items = models.JSONField(default=list)
    last_event_id = models.CharField(max_length=100, blank=True)
    last_event_timestamp = models.DateTimeField(null=True, blank=True)
    source_of_truth = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        unique_together = ["order_id", "version"]


class AuditLog(models.Model):
    order_id = models.CharField(max_length=100, db_index=True)
    event_ids_considered = models.JSONField(default=list)
    events_detail = models.JSONField(default=list)
    resolution_rule = models.CharField(max_length=100)
    rule_explanation = models.TextField()
    previous_state = models.JSONField(default=dict)
    final_state = models.JSONField(default=dict)
    decision_timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["decision_timestamp"]


class Location(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MenuItem(models.Model):
    name = models.CharField(max_length=100)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="menu_items")
    stock_quantity = models.IntegerField(default=0)


class InventoryReservation(models.Model):
    order_id = models.CharField(max_length=100, db_index=True)
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, default="reserved")
    created_at = models.DateTimeField(auto_now_add=True)


class AnomalyAlert(models.Model):
    source = models.CharField(max_length=20)
    pattern_type = models.CharField(max_length=50)
    description = models.TextField()
    order_id = models.CharField(max_length=100, null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-detected_at"]


class DriverNotification(models.Model):
    order_id = models.CharField(max_length=100, db_index=True)
    driver_id = models.CharField(max_length=50, default="DRV-001")
    message = models.TextField()
    status = models.CharField(max_length=20, default="sent")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
