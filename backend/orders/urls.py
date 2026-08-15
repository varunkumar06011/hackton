from django.urls import path
from orders import views

urlpatterns = [
    path("events", views.submit_event),
    path("orders", views.list_orders),
    path("orders/<str:order_id>", views.get_order),
    path("orders/<str:order_id>/history", views.get_order_history),
    path("orders/<str:order_id>/audit", views.get_audit),
    path("orders/<str:order_id>/replay", views.replay_order),
    path("orders/<str:order_id>/state", views.get_state),
    path("health", views.health_check),
    path("locations", views.list_locations),
    path("inventory/<int:location_id>", views.get_inventory),
    path("notify/driver", views.notify_driver_endpoint),
    path("anomalies", views.list_anomalies),
    path("stats", views.get_stats),
]
