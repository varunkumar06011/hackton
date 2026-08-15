import json
import os
from django.core.management.base import BaseCommand
from orders.services.ingestion import validate_event, check_duplicate, save_event
from orders.services.conflict_resolver import resolve_event
from orders.models import Location, MenuItem


class Command(BaseCommand):
    help = "Load fixture JSON file(s) through the event ingestion pipeline"

    def add_arguments(self, parser):
        parser.add_argument(
            "fixture_path",
            type=str,
            help="Path to fixture JSON file (relative to backend/ or absolute)",
        )
        parser.add_argument(
            "--seed-inventory",
            action="store_true",
            default=False,
            help="Seed default Location and MenuItems before loading fixtures",
        )

    def handle(self, *args, **options):
        fixture_path = options["fixture_path"]
        seed_inventory = options["seed_inventory"]

        if not os.path.isabs(fixture_path):
            fixture_path = os.path.join(os.getcwd(), fixture_path)

        if not os.path.exists(fixture_path):
            self.stderr.write(self.style.ERROR(f"File not found: {fixture_path}"))
            return

        if seed_inventory:
            self._seed_inventory()

        with open(fixture_path, "r") as f:
            events = json.load(f)

        processed = 0
        duplicates = 0
        rejected = 0
        errors = 0

        for event_data in events:
            valid, result = validate_event(event_data)
            if not valid:
                self.stderr.write(self.style.WARNING(
                    f"  REJECTED event {event_data.get('event_id', '?')}: {result}"
                ))
                rejected += 1
                continue

            existing = check_duplicate(result["event_id"])
            if existing:
                self.stdout.write(f"  DUPLICATE skipped: {result['event_id']}")
                duplicates += 1
                continue

            try:
                event = save_event(result)
                order_state, audit = resolve_event(event)
                processed += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  PROCESSED {result['event_id']} -> order {result['order_id']} "
                    f"status={order_state.status} rule={audit.resolution_rule}"
                ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f"  ERROR processing {result['event_id']}: {e}"
                ))
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nSummary: {processed} processed, {duplicates} duplicates, "
            f"{rejected} rejected, {errors} errors"
        ))

    def _seed_inventory(self):
        loc, created = Location.objects.get_or_create(
            name="Downtown",
            defaults={"address": "123 Main St"},
        )
        items = [
            ("Burger", 10),
            ("Pizza", 8),
            ("Steak", 5),
            ("Pasta", 6),
            ("Fries", 15),
            ("Salad", 12),
            ("Soup", 7),
            ("Tacos", 9),
            ("Rice", 10),
        ]
        for name, qty in items:
            MenuItem.objects.get_or_create(
                name=name,
                location=loc,
                defaults={"stock_quantity": qty},
            )
        self.stdout.write(self.style.SUCCESS(
            f"Seeded inventory: Location '{loc.name}' with {len(items)} menu items"
        ))
