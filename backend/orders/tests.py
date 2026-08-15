from django.test import TestCase
from rest_framework.test import APIClient
from orders.models import Event, OrderState, AuditLog, Location, MenuItem


class DuplicateEventTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_duplicate_event_ignored(self):
        payload = {
            "event_id": "dup-test-1", "source": "pos", "order_id": "ORD-DUP-1",
            "timestamp": "2026-08-15T10:00:00Z",
            "items": [{"name": "Burger", "quantity": 2}], "status": "pending",
        }
        r1 = self._submit(payload)
        self.assertEqual(r1.status_code, 201)
        r2 = self._submit(payload)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data["status"], "duplicate_ignored")

    def test_duplicate_idempotent(self):
        payload = {
            "event_id": "dup-test-2", "source": "mobile", "order_id": "ORD-DUP-2",
            "timestamp": "2026-08-15T10:00:00Z",
            "items": [{"name": "Pizza", "quantity": 1}], "status": "pending",
        }
        self._submit(payload)
        self._submit(payload)
        self._submit(payload)
        states = OrderState.objects.filter(order_id="ORD-DUP-2")
        self.assertEqual(states.count(), 1)
        self.assertEqual(states.first().version, 0)

    def test_duplicate_does_not_create_new_event(self):
        payload = {
            "event_id": "dup-test-3", "source": "web", "order_id": "ORD-DUP-3",
            "timestamp": "2026-08-15T10:00:00Z", "items": [], "status": "pending",
        }
        self._submit(payload)
        self._submit(payload)
        events = Event.objects.filter(event_id="dup-test-3")
        self.assertEqual(events.count(), 1)


class LateEventTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_late_event_recomputes_state(self):
        self._submit({"event_id": "late-t-1", "source": "pos", "order_id": "ORD-LATE-1", "timestamp": "2026-08-15T10:05:00Z", "items": [{"name": "Pizza", "quantity": 1}], "status": "pending"})
        self._submit({"event_id": "late-t-2", "source": "mobile", "order_id": "ORD-LATE-1", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "preparing"})
        self._submit({"event_id": "late-t-3", "source": "web", "order_id": "ORD-LATE-1", "timestamp": "2026-08-15T10:02:00Z", "items": [{"name": "Salad", "quantity": 1}], "status": "pending"})

        state = OrderState.objects.filter(order_id="ORD-LATE-1").order_by("-version").first()
        self.assertEqual(state.status, "preparing")
        item_names = [i["name"] for i in state.items]
        self.assertIn("Pizza", item_names)
        self.assertIn("Salad", item_names)

    def test_late_event_items_merged_correctly(self):
        self._submit({"event_id": "late-t-4", "source": "pos", "order_id": "ORD-LATE-2", "timestamp": "2026-08-15T10:05:00Z", "items": [{"name": "Burger", "quantity": 2}], "status": "pending"})
        self._submit({"event_id": "late-t-5", "source": "web", "order_id": "ORD-LATE-2", "timestamp": "2026-08-15T10:02:00Z", "items": [{"name": "Fries", "quantity": 1}], "status": "pending"})

        state = OrderState.objects.filter(order_id="ORD-LATE-2").order_by("-version").first()
        item_names = sorted([i["name"] for i in state.items])
        self.assertEqual(item_names, ["Burger", "Fries"])


class ConflictResolutionTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_conflicting_status_same_timestamp_pos_wins(self):
        self._submit({"event_id": "conf-s-1", "source": "pos", "order_id": "ORD-CONF-1", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Pasta", "quantity": 1}], "status": "pending"})
        self._submit({"event_id": "conf-s-2", "source": "pos", "order_id": "ORD-CONF-1", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"})
        self._submit({"event_id": "conf-s-3", "source": "web", "order_id": "ORD-CONF-1", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"})

        state = OrderState.objects.filter(order_id="ORD-CONF-1").order_by("-version").first()
        self.assertEqual(state.status, "preparing")
        audit = AuditLog.objects.filter(order_id="ORD-CONF-1").order_by("-decision_timestamp").first()
        self.assertIn("priority", audit.rule_explanation.lower())

    def test_conflicting_status_different_timestamp_latest_wins(self):
        self._submit({"event_id": "conf-s-4", "source": "pos", "order_id": "ORD-CONF-2", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Rice", "quantity": 1}], "status": "pending"})
        self._submit({"event_id": "conf-s-5", "source": "mobile", "order_id": "ORD-CONF-2", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "preparing"})

        state = OrderState.objects.filter(order_id="ORD-CONF-2").order_by("-version").first()
        self.assertEqual(state.status, "preparing")

    def test_invalid_transition_rejected(self):
        self._submit({"event_id": "conf-s-6", "source": "pos", "order_id": "ORD-CONF-3", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Soup", "quantity": 1}], "status": "pending"})
        self._submit({"event_id": "conf-s-7", "source": "pos", "order_id": "ORD-CONF-3", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"})
        self._submit({"event_id": "conf-s-8", "source": "pos", "order_id": "ORD-CONF-3", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "ready"})
        self._submit({"event_id": "conf-s-9", "source": "mobile", "order_id": "ORD-CONF-3", "timestamp": "2026-08-15T10:15:00Z", "items": [], "status": "preparing"})

        state = OrderState.objects.filter(order_id="ORD-CONF-3").order_by("-version").first()
        self.assertEqual(state.status, "ready")

    def test_conflicting_reservation_within_order(self):
        self._submit({"event_id": "conf-res-1", "source": "pos", "order_id": "ORD-CONF-RES", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Steak", "quantity": 2}], "status": "pending"})
        self._submit({"event_id": "conf-res-2", "source": "mobile", "order_id": "ORD-CONF-RES", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Steak", "quantity": 1}], "status": "pending"})

        state = OrderState.objects.filter(order_id="ORD-CONF-RES").order_by("-version").first()
        steak = [i for i in state.items if i["name"] == "Steak"]
        self.assertTrue(len(steak) == 1)
        self.assertEqual(steak[0]["quantity"], 1)

    def test_audit_explanation_accuracy(self):
        self._submit({"event_id": "conf-s-1", "source": "pos", "order_id": "ORD-CONF-1", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Pasta", "quantity": 1}], "status": "pending"})
        self._submit({"event_id": "conf-s-2", "source": "pos", "order_id": "ORD-CONF-1", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"})
        self._submit({"event_id": "conf-s-3", "source": "web", "order_id": "ORD-CONF-1", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"})

        audit = AuditLog.objects.filter(order_id="ORD-CONF-1").order_by("-decision_timestamp").first()
        self.assertIn("priority", audit.rule_explanation.lower())
        self.assertNotIn("invalid transition", audit.rule_explanation.lower())


class ReplayTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_replay_matches_live_state(self):
        events = [
            {"event_id": "rep-1", "source": "pos", "order_id": "ORD-REP-1", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 2}], "status": "pending"},
            {"event_id": "rep-2", "source": "mobile", "order_id": "ORD-REP-1", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"},
            {"event_id": "rep-3", "source": "pos", "order_id": "ORD-REP-1", "timestamp": "2026-08-15T10:10:00Z", "items": [{"name": "Fries", "quantity": 1}], "status": "preparing"},
        ]
        for e in events:
            self._submit(e)

        live_state = OrderState.objects.filter(order_id="ORD-REP-1").order_by("-version").first()
        replay = self.client.get("/api/orders/ORD-REP-1/replay")
        self.assertEqual(replay.status_code, 200)
        replay_state = replay.data["final_state"]
        self.assertEqual(replay_state["status"], live_state.status)

    def test_replay_with_up_to(self):
        events = [
            {"event_id": "rep-4", "source": "pos", "order_id": "ORD-REP-2", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Pizza", "quantity": 1}], "status": "pending"},
            {"event_id": "rep-5", "source": "pos", "order_id": "ORD-REP-2", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"},
            {"event_id": "rep-6", "source": "pos", "order_id": "ORD-REP-2", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "ready"},
        ]
        for e in events:
            self._submit(e)

        replay = self.client.get("/api/orders/ORD-REP-2/replay?up_to=2026-08-15T10:05:00Z")
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.data["final_state"]["status"], "preparing")

    def test_replay_determinism(self):
        events = [
            {"event_id": "rep-7", "source": "web", "order_id": "ORD-REP-3", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Salad", "quantity": 1}], "status": "pending"},
            {"event_id": "rep-8", "source": "pos", "order_id": "ORD-REP-3", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"},
        ]
        for e in events:
            self._submit(e)

        r1 = self.client.get("/api/orders/ORD-REP-3/replay")
        r2 = self.client.get("/api/orders/ORD-REP-3/replay")
        self.assertEqual(r1.data, r2.data)


class AuditTrailTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_audit_contains_all_events(self):
        self._submit({"event_id": "aud-1", "source": "pos", "order_id": "ORD-AUD-1", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 1}], "status": "pending"})
        self._submit({"event_id": "aud-2", "source": "pos", "order_id": "ORD-AUD-1", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"})

        audits = AuditLog.objects.filter(order_id="ORD-AUD-1")
        self.assertEqual(audits.count(), 2)
        latest = audits.order_by("-decision_timestamp").first()
        self.assertIn("aud-1", latest.event_ids_considered)
        self.assertIn("aud-2", latest.event_ids_considered)

    def test_audit_has_resolution_rule(self):
        self._submit({"event_id": "aud-3", "source": "pos", "order_id": "ORD-AUD-2", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Pizza", "quantity": 1}], "status": "pending"})
        audit = AuditLog.objects.get(order_id="ORD-AUD-2")
        self.assertTrue(audit.resolution_rule)

    def test_audit_has_previous_and_final_state(self):
        self._submit({"event_id": "aud-4", "source": "pos", "order_id": "ORD-AUD-3", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Rice", "quantity": 1}], "status": "pending"})
        self._submit({"event_id": "aud-5", "source": "pos", "order_id": "ORD-AUD-3", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"})

        audits = AuditLog.objects.filter(order_id="ORD-AUD-3").order_by("decision_timestamp")
        first = audits[0]
        second = audits[1]
        self.assertEqual(first.previous_state, {})
        self.assertIn("status", first.final_state)
        self.assertEqual(second.previous_state["status"], "pending")
        self.assertEqual(second.final_state["status"], "preparing")

    def test_audit_explanation_readable(self):
        self._submit({"event_id": "aud-6", "source": "web", "order_id": "ORD-AUD-4", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Soup", "quantity": 2}], "status": "pending"})
        audit = AuditLog.objects.get(order_id="ORD-AUD-4")
        self.assertTrue(len(audit.rule_explanation) > 10)


class InventoryTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.loc = Location.objects.create(name="Downtown", address="123 Main St")
        MenuItem.objects.create(name="Burger", location=self.loc, stock_quantity=5)
        MenuItem.objects.create(name="Pizza", location=self.loc, stock_quantity=3)

    def test_inventory_check(self):
        from orders.services.inventory_manager import check_inventory
        result = check_inventory(self.loc.id, [{"name": "Burger", "quantity": 3}])
        self.assertTrue(result["available"])
        result = check_inventory(self.loc.id, [{"name": "Burger", "quantity": 10}])
        self.assertFalse(result["available"])

    def test_reservation_release(self):
        from orders.services.inventory_manager import reserve_inventory, release_inventory
        reservations = reserve_inventory("ORD-INV-1", [{"name": "Burger", "quantity": 2}], self.loc.id)
        self.assertEqual(len(reservations), 1)
        burger = MenuItem.objects.get(name="Burger", location=self.loc)
        self.assertEqual(burger.stock_quantity, 3)
        release_inventory("ORD-INV-1")
        burger.refresh_from_db()
        self.assertEqual(burger.stock_quantity, 5)


class ValidationTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_missing_required_field(self):
        r = self._submit({"source": "pos", "order_id": "X", "timestamp": "2026-08-15T10:00:00Z", "status": "pending"})
        self.assertEqual(r.status_code, 400)

    def test_invalid_source(self):
        r = self._submit({"event_id": "v-1", "source": "kitchen", "order_id": "X", "timestamp": "2026-08-15T10:00:00Z", "items": [], "status": "pending"})
        self.assertEqual(r.status_code, 400)

    def test_invalid_status(self):
        r = self._submit({"event_id": "v-2", "source": "pos", "order_id": "X", "timestamp": "2026-08-15T10:00:00Z", "items": [], "status": "cooking"})
        self.assertEqual(r.status_code, 400)

    def test_valid_event_accepted(self):
        r = self._submit({"event_id": "v-4", "source": "pos", "order_id": "ORD-VAL-1", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 1}], "status": "pending"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "processed")

    def test_quantity_zero_allowed(self):
        r = self._submit({"event_id": "v-5", "source": "pos", "order_id": "ORD-VAL-2", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 0}], "status": "pending"})
        self.assertEqual(r.status_code, 201)

    def test_negative_quantity_rejected(self):
        r = self._submit({"event_id": "v-6", "source": "pos", "order_id": "ORD-VAL-3", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": -1}], "status": "pending"})
        self.assertEqual(r.status_code, 400)


class EdgeCaseTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_get_nonexistent_order_404(self):
        r = self.client.get("/api/orders/NONEXISTENT-999")
        self.assertEqual(r.status_code, 404)

    def test_processing_time_in_response(self):
        r = self._submit({"event_id": "edge-1", "source": "pos", "order_id": "ORD-EDGE-1", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 1}], "status": "pending"})
        self.assertEqual(r.status_code, 201)
        self.assertIn("processing_time_ms", r.data)

    def test_partial_update_item_removal(self):
        self._submit({"event_id": "edge-2", "source": "web", "order_id": "ORD-EDGE-2", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 2}, {"name": "Fries", "quantity": 1}], "status": "pending"})
        self._submit({"event_id": "edge-3", "source": "pos", "order_id": "ORD-EDGE-2", "timestamp": "2026-08-15T10:05:00Z", "items": [{"name": "Fries", "quantity": 0}], "status": "preparing"})
        state = OrderState.objects.filter(order_id="ORD-EDGE-2").order_by("-version").first()
        item_names = [i["name"] for i in state.items]
        self.assertIn("Burger", item_names)
        self.assertNotIn("Fries", item_names)


class StatsEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_stats_endpoint(self):
        self._submit({"event_id": "stat-e-1", "source": "pos", "order_id": "ORD-STAT-1", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 1}], "status": "pending"})
        r = self.client.get("/api/stats")
        self.assertEqual(r.status_code, 200)
        self.assertIn("total_events", r.data)
        self.assertIn("total_orders", r.data)
        self.assertGreater(r.data["total_events"], 0)
        self.assertGreater(r.data["total_orders"], 0)


class IntegrityErrorTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_duplicate_integrity_error_handled(self):
        from unittest.mock import patch
        from django.db import IntegrityError

        payload = {"event_id": "integ-1", "source": "pos", "order_id": "ORD-INTEG-1", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 1}], "status": "pending"}
        self._submit(payload)

        with patch("orders.views.save_event", side_effect=IntegrityError("duplicate")):
            r = self._submit(payload)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "duplicate_ignored")


class PerformanceTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_processing_time_under_500ms(self):
        for i in range(10):
            self._submit({
                "event_id": f"perf-build-{i}",
                "source": "pos",
                "order_id": "ORD-PERF-1",
                "timestamp": f"2026-08-15T10:{i:02d}:00Z",
                "items": [{"name": f"Item{i}", "quantity": i + 1}],
                "status": "pending" if i == 0 else "preparing",
            })
        r = self._submit({
            "event_id": "perf-measure",
            "source": "pos",
            "order_id": "ORD-PERF-1",
            "timestamp": "2026-08-15T10:20:00Z",
            "items": [{"name": "NewItem", "quantity": 1}],
            "status": "preparing",
        })
        self.assertEqual(r.status_code, 201)
        self.assertLess(r.data["processing_time_ms"], 500)


class RejectedTransitionTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_rejected_transition_does_not_merge_items(self):
        self._submit({"event_id": "rej-1", "source": "pos", "order_id": "ORD-REJ-1", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 2}], "status": "pending"})
        self._submit({"event_id": "rej-2", "source": "pos", "order_id": "ORD-REJ-1", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"})
        self._submit({"event_id": "rej-3", "source": "pos", "order_id": "ORD-REJ-1", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "ready"})
        self._submit({"event_id": "rej-4", "source": "mobile", "order_id": "ORD-REJ-1", "timestamp": "2026-08-15T10:15:00Z", "items": [{"name": "Fries", "quantity": 3}], "status": "preparing"})

        state = OrderState.objects.filter(order_id="ORD-REJ-1").order_by("-version").first()
        self.assertEqual(state.status, "ready")
        item_names = [i["name"] for i in state.items]
        self.assertNotIn("Fries", item_names)

    def test_rejected_transition_source_of_truth_unchanged(self):
        self._submit({"event_id": "rej-5", "source": "pos", "order_id": "ORD-REJ-2", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 1}], "status": "pending"})
        self._submit({"event_id": "rej-6", "source": "pos", "order_id": "ORD-REJ-2", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"})
        self._submit({"event_id": "rej-7", "source": "pos", "order_id": "ORD-REJ-2", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "ready"})
        self._submit({"event_id": "rej-8", "source": "mobile", "order_id": "ORD-REJ-2", "timestamp": "2026-08-15T10:15:00Z", "items": [], "status": "preparing"})

        state = OrderState.objects.filter(order_id="ORD-REJ-2").order_by("-version").first()
        self.assertEqual(state.status, "ready")
        self.assertEqual(state.source_of_truth, "pos")
        self.assertEqual(state.last_event_id, "rej-7")


class TimestampValidationTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _submit(self, payload):
        return self.client.post("/api/events", payload, format="json")

    def test_invalid_timestamp_rejected(self):
        r = self._submit({"event_id": "ts-1", "source": "pos", "order_id": "ORD-TS-1", "timestamp": "not-a-date", "items": [], "status": "pending"})
        self.assertEqual(r.status_code, 400)

    def test_empty_timestamp_rejected(self):
        r = self._submit({"event_id": "ts-2", "source": "pos", "order_id": "ORD-TS-2", "timestamp": "", "items": [], "status": "pending"})
        self.assertEqual(r.status_code, 400)

    def test_valid_timestamp_accepted(self):
        r = self._submit({"event_id": "ts-3", "source": "pos", "order_id": "ORD-TS-3", "timestamp": "2026-08-15T10:00:00Z", "items": [], "status": "pending"})
        self.assertEqual(r.status_code, 201)
