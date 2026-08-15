from django.contrib import admin
from orders.models import (
    Event, OrderState, AuditLog, Location, MenuItem,
    InventoryReservation, AnomalyAlert, DriverNotification,
)

admin.site.register(Event)
admin.site.register(OrderState)
admin.site.register(AuditLog)
admin.site.register(Location)
admin.site.register(MenuItem)
admin.site.register(InventoryReservation)
admin.site.register(AnomalyAlert)
admin.site.register(DriverNotification)
