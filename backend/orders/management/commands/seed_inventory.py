from django.core.management.base import BaseCommand
from orders.models import Location, MenuItem


class Command(BaseCommand):
    help = "Seed sample locations and menu items for demo"

    def handle(self, *args, **options):
        loc1 = Location.objects.create(name="Downtown", address="123 Main St")
        loc2 = Location.objects.create(name="Uptown", address="456 Oak Ave")

        items_loc1 = [
            ("Burger", 10), ("Pizza", 8), ("Salad", 5),
            ("Pasta", 6), ("Soup", 4), ("Steak", 3),
            ("Fries", 15), ("Tacos", 7),
        ]
        for name, qty in items_loc1:
            MenuItem.objects.create(name=name, location=loc1, stock_quantity=qty)

        items_loc2 = [
            ("Burger", 5), ("Pizza", 3), ("Salad", 2),
            ("Rice", 8), ("Soup", 6), ("Tacos", 4),
        ]
        for name, qty in items_loc2:
            MenuItem.objects.create(name=name, location=loc2, stock_quantity=qty)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded 2 locations and {len(items_loc1) + len(items_loc2)} menu items"
        ))
