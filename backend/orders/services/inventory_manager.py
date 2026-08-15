from orders.models import Location, MenuItem, InventoryReservation


def check_inventory(location_id, items):
    shortages = []
    for item in items:
        menu_item = MenuItem.objects.filter(name=item["name"], location_id=location_id).first()
        if not menu_item or menu_item.stock_quantity < item["quantity"]:
            available = menu_item.stock_quantity if menu_item else 0
            shortages.append({
                "name": item["name"],
                "requested": item["quantity"],
                "available": available,
            })
    return {"available": len(shortages) == 0, "shortages": shortages}


def reserve_inventory(order_id, items, location_id):
    reservations = []
    for item in items:
        menu_item = MenuItem.objects.filter(name=item["name"], location_id=location_id).first()
        if menu_item and menu_item.stock_quantity >= item["quantity"]:
            menu_item.stock_quantity -= item["quantity"]
            menu_item.save()
            res = InventoryReservation.objects.create(
                order_id=order_id,
                item=menu_item,
                quantity=item["quantity"],
                status="reserved",
            )
            reservations.append(res)
    return reservations


def release_inventory(order_id):
    reservations = InventoryReservation.objects.filter(order_id=order_id, status="reserved")
    for res in reservations:
        res.item.stock_quantity += res.quantity
        res.item.save()
        res.status = "released"
        res.save()


def get_location_inventory(location_id):
    items = MenuItem.objects.filter(location_id=location_id)
    return [
        {"name": item.name, "stock_quantity": item.stock_quantity, "id": item.id}
        for item in items
    ]
