"""
Seeds exactly the prototype scope: 1 hub, 1 supplier, a small menu.
Run with:  python seed.py
Safe to re-run - it upserts rather than duplicating.

IMPORTANT: commits happen in three separate stages (hub, then supplier, then
menu items) rather than one commit at the end. SQLAlchemy only guarantees
cross-table insert ordering when models have explicit relationship() links;
ours use plain FK columns without relationship(), so a single end-of-script
commit can (and did, once) emit the INSERT statements in the wrong order and
violate the foreign key constraints. Committing after each stage forces each
parent row to exist before its children are inserted, regardless of what
order the ORM would otherwise choose.
"""
from database import SessionLocal, Base, engine
from models import Hub, Supplier, MenuItem

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    db.merge(Hub(
        hub_id="HUB_A",
        name="Downtown Hub A",
        gps_lat=12.2527857
        gps_lng=79.0131810,
        marker_id="HUBMARKER_A",   # <-- this string is the ONLY thing the physical QR encodes
        is_origin=True,
        is_destination=True,
    ))
    db.commit()

    db.merge(Supplier(
        supplier_id="sup_test_1",
        hub_id="HUB_A",
        name="Hub A Kitchen",
        active=True,
    ))
    db.commit()

    menu_items = [
        MenuItem(item_id="item_burger", supplier_id="sup_test_1", name="Chicken Burger", price_cents=699, available=True),
        MenuItem(item_id="item_fries", supplier_id="sup_test_1", name="Fries", price_cents=299, available=True),
        MenuItem(item_id="item_salad", supplier_id="sup_test_1", name="Garden Salad", price_cents=599, available=True),
        MenuItem(item_id="item_soda", supplier_id="sup_test_1", name="Soda", price_cents=199, available=True),
    ]
    for item in menu_items:
        db.merge(item)
    db.commit()

    print("Seeded: hub=HUB_A (marker_id=HUBMARKER_A), supplier=sup_test_1, 4 menu items")
finally:
    db.close()