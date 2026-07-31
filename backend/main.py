import os
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import Base, engine, get_db
import models
from models import Order, Hub, Supplier, MenuItem, OrderStatus, ALLOWED_TRANSITIONS
import schemas
from sqlalchemy import text, inspect

load_dotenv()

app = FastAPI(title="Hub-to-Hub Drone Delivery API")

# Wide open for prototype — lock down before anything but local/dev use.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Creates tables if they don't exist yet (fine for a 2-week prototype;
# swap for Alembic migrations if this grows past the prototype stage).
Base.metadata.create_all(bind=engine)

# create_all() ONLY creates missing tables — it never adds a column to a
# table that already exists. On Render's free tier there's no Shell tab to
# run a manual ALTER TABLE (that's a paid-plan feature), so instead: check
# for and add any newly-needed columns here, every startup. Checking via
# inspector (rather than "ADD COLUMN IF NOT EXISTS", which is Postgres-only
# syntax — SQLite errors on it) keeps this working the same way whether
# you're on Render's Postgres or a local SQLite dev DB. Add an entry here
# any time a new nullable column shows up in models.py; fine for a
# prototype, but swap for real Alembic migrations before this grows past
# that.
_NEW_ORDER_COLUMNS = {
    "launch_confirmed_at": "TIMESTAMPTZ" if engine.dialect.name == "postgresql" else "DATETIME",
    "mission_ack_at": "TIMESTAMPTZ" if engine.dialect.name == "postgresql" else "DATETIME",
    # Set by the Pi once RTL completes and it lands back home - the signal
    # that moves a delivered order from "active" to "previous" in the
    # supplier UI. Deliberately separate from delivered_at: an order
    # becomes "delivered" the moment it lands at the destination, but
    # should stay visible/active in the supplier's list until the drone
    # is actually back and free for the next dispatch.
    "drone_returned_home_at": "TIMESTAMPTZ" if engine.dialect.name == "postgresql" else "DATETIME",
    # Payload compartment lock state, toggled manually by the supplier.
    # BOOLEAN works the same way on Postgres and SQLite, no dialect branch
    # needed here unlike the timestamp columns above.
    "payload_locked": "BOOLEAN",
}
_existing_columns = {c["name"] for c in inspect(engine).get_columns("orders")}
with engine.connect() as _conn:
    for _col_name, _col_type in _NEW_ORDER_COLUMNS.items():
        if _col_name not in _existing_columns:
            _conn.execute(text(f"ALTER TABLE orders ADD COLUMN {_col_name} {_col_type}"))
    _conn.commit()

TEST_CUSTOMER_ID = os.getenv("TEST_CUSTOMER_ID", "cust_test_1")
TEST_CUSTOMER_TOKEN = os.getenv("TEST_CUSTOMER_TOKEN", "customer-dev-token")
TEST_SUPPLIER_ID = os.getenv("TEST_SUPPLIER_ID", "sup_test_1")
TEST_SUPPLIER_TOKEN = os.getenv("TEST_SUPPLIER_TOKEN", "supplier-dev-token")


# ---------------------------------------------------------------------------
# Mocked auth — single hardcoded customer + supplier identity via bearer token.
# Swap these dependency functions for real auth later without touching routes.
# ---------------------------------------------------------------------------

def require_customer(authorization: str = Header(default="")) -> str:
    token = authorization.replace("Bearer ", "").strip()
    if token != TEST_CUSTOMER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid customer token")
    return TEST_CUSTOMER_ID


def require_supplier(authorization: str = Header(default="")) -> str:
    token = authorization.replace("Bearer ", "").strip()
    if token != TEST_SUPPLIER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid supplier token")
    return TEST_SUPPLIER_ID


def now():
    return datetime.now(timezone.utc)


def order_to_out(o: Order, db: Session) -> schemas.OrderOut:
    # Prototype has origin_hub_id == destination_hub_id, but look each up
    # independently so this is already correct once multi-hub routing lands.
    origin_hub = db.query(Hub).filter(Hub.hub_id == o.origin_hub_id).first()
    destination_hub = (
        origin_hub
        if o.destination_hub_id == o.origin_hub_id
        else db.query(Hub).filter(Hub.hub_id == o.destination_hub_id).first()
    )
    return schemas.OrderOut(
        order_id=o.order_id,
        origin_hub_id=o.origin_hub_id,
        origin_hub_name=origin_hub.name if origin_hub else None,
        origin_hub_lat=origin_hub.gps_lat if origin_hub else None,
        origin_hub_lng=origin_hub.gps_lng if origin_hub else None,
        destination_hub_id=o.destination_hub_id,
        destination_hub_name=destination_hub.name if destination_hub else None,
        destination_hub_lat=destination_hub.gps_lat if destination_hub else None,
        destination_hub_lng=destination_hub.gps_lng if destination_hub else None,
        supplier_id=o.supplier_id,
        customer_id=o.customer_id,
        items=[schemas.OrderItemOut(**i) for i in o.items],
        total_cents=o.total_cents,
        status=o.status,
        drone_id=o.drone_id,
        payment_method=o.payment_method,
        launch_confirmed_at=o.launch_confirmed_at,
        payload_locked=o.payload_locked,
        drone_returned_home_at=o.drone_returned_home_at,
        placed_at=o.placed_at,
        accepted_at=o.accepted_at,
        preparing_at=o.preparing_at,
        dispatched_at=o.dispatched_at,
        in_flight_at=o.in_flight_at,
        delivered_at=o.delivered_at,
        cancelled_at=o.cancelled_at,
    )


def transition(o: Order, new_status: OrderStatus, db: Session):
    allowed = ALLOWED_TRANSITIONS[o.status]
    if new_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move order from '{o.status.value}' to '{new_status.value}'",
        )
    o.status = new_status
    ts_field = {
        OrderStatus.accepted: "accepted_at",
        OrderStatus.preparing: "preparing_at",
        OrderStatus.dispatched: "dispatched_at",
        OrderStatus.in_flight: "in_flight_at",
        OrderStatus.delivered: "delivered_at",
        OrderStatus.cancelled: "cancelled_at",
    }.get(new_status)
    if ts_field:
        setattr(o, ts_field, now())
    db.commit()
    db.refresh(o)
    return o


# ===========================================================================
# CUSTOMER-FACING ENDPOINTS
# ===========================================================================

@app.get("/hubs/{marker_id}/scan", response_model=schemas.ScanHubResponse)
def scan_hub(marker_id: str, db: Session = Depends(get_db)):
    """
    Resolve a scanned physical QR marker_id -> hub_id -> available suppliers + menus.
    This is the ONLY thing encoded in the hub QR code (marker_id); everything else
    is looked up server-side so menus can change without reprinting QR codes.
    """
    hub = db.query(Hub).filter(Hub.marker_id == marker_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Unknown hub QR code")

    suppliers = (
        db.query(Supplier)
        .filter(Supplier.hub_id == hub.hub_id, Supplier.active.is_(True))
        .all()
    )

    suppliers_out = []
    for s in suppliers:
        items = (
            db.query(MenuItem)
            .filter(MenuItem.supplier_id == s.supplier_id, MenuItem.available.is_(True))
            .all()
        )
        suppliers_out.append(
            schemas.SupplierWithMenuOut(
                supplier_id=s.supplier_id,
                name=s.name,
                menu_items=[schemas.MenuItemOut.model_validate(i) for i in items],
            )
        )

    return schemas.ScanHubResponse(
        hub_id=hub.hub_id, hub_name=hub.name, suppliers=suppliers_out
    )


@app.post("/orders", response_model=schemas.OrderOut)
def place_order(
    req: schemas.PlaceOrderRequest,
    db: Session = Depends(get_db),
    customer_id: str = Depends(require_customer),
):
    hub = db.query(Hub).filter(Hub.hub_id == req.hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")

    supplier = db.query(Supplier).filter(Supplier.supplier_id == req.supplier_id).first()
    if not supplier or supplier.hub_id != hub.hub_id:
        raise HTTPException(status_code=400, detail="Supplier does not belong to this hub")

    if not req.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    VALID_PAYMENT_METHODS = {"cash_on_delivery", "upi"}
    if req.payment_method is not None and req.payment_method not in VALID_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Invalid payment_method: {req.payment_method}")

    order_items = []
    total_cents = 0
    for line in req.items:
        item = db.query(MenuItem).filter(MenuItem.item_id == line.item_id).first()
        if not item or not item.available or item.supplier_id != supplier.supplier_id:
            raise HTTPException(status_code=400, detail=f"Item {line.item_id} unavailable")
        if line.qty < 1:
            raise HTTPException(status_code=400, detail="Quantity must be >= 1")
        order_items.append(
            {"item_id": item.item_id, "name": item.name, "qty": line.qty, "price_cents": item.price_cents}
        )
        total_cents += item.price_cents * line.qty

    # Prototype scope: destination hub == origin hub (single hub-to-hub route).
    # Kept as a separate field so multi-hub routing is a config change, not a schema change.
    order = Order(
        order_id=f"ord_{uuid.uuid4().hex[:10]}",
        origin_hub_id=hub.hub_id,
        destination_hub_id=hub.hub_id,
        supplier_id=supplier.supplier_id,
        customer_id=customer_id,
        items=order_items,
        total_cents=total_cents,
        status=OrderStatus.placed,
        payment_method=req.payment_method,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order_to_out(order, db)


@app.get("/orders/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_to_out(order, db)


@app.get("/orders/{order_id}/status", response_model=schemas.OrderStatusOut)
def get_order_status(order_id: str, db: Session = Depends(get_db)):
    """Lightweight endpoint for the customer app to poll (every ~3s)."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updated_at = next(
        (getattr(order, f) for f in
         ["delivered_at", "in_flight_at", "dispatched_at", "preparing_at", "accepted_at", "placed_at"]
         if getattr(order, f) is not None),
        None,
    )
    return schemas.OrderStatusOut(
        order_id=order.order_id, status=order.status, drone_id=order.drone_id, updated_at=updated_at
    )


# ===========================================================================
# SUPPLIER-FACING ENDPOINTS
# ===========================================================================

@app.get("/supplier/orders", response_model=List[schemas.OrderOut])
def list_incoming_orders(
    db: Session = Depends(get_db),
    supplier_id: str = Depends(require_supplier),
):
    """
    ACTIVE queue. Deliberately includes orders that are already "delivered"
    as long as the drone hasn't made it back home yet (drone_returned_home_at
    still null) - the order should stay visible with its status simply
    updated to "delivered", not vanish the instant the food is dropped off.
    It only moves to the /previous list once the drone is actually back and
    free for the next dispatch.
    """
    orders = (
        db.query(Order)
        .filter(
            Order.supplier_id == supplier_id,
            Order.status != OrderStatus.cancelled,
            ~((Order.status == OrderStatus.delivered) & (Order.drone_returned_home_at.isnot(None))),
        )
        .order_by(Order.placed_at.desc())
        .all()
    )
    return [order_to_out(o, db) for o in orders]


@app.get("/supplier/orders/previous", response_model=List[schemas.OrderOut])
def list_previous_orders(
    db: Session = Depends(get_db),
    supplier_id: str = Depends(require_supplier),
):
    """Archive view: cancelled orders, plus delivered orders whose drone has
    confirmed it's back home. Most recent first."""
    orders = (
        db.query(Order)
        .filter(
            Order.supplier_id == supplier_id,
            (Order.status == OrderStatus.cancelled)
            | ((Order.status == OrderStatus.delivered) & (Order.drone_returned_home_at.isnot(None))),
        )
        .order_by(Order.placed_at.desc())
        .limit(50)
        .all()
    )
    return [order_to_out(o, db) for o in orders]


@app.post("/supplier/orders/{order_id}/accept", response_model=schemas.OrderOut)
def accept_order(order_id: str, db: Session = Depends(get_db), supplier_id: str = Depends(require_supplier)):
    order = _get_supplier_order(db, order_id, supplier_id)
    return order_to_out(transition(order, OrderStatus.accepted, db), db)


@app.post("/supplier/orders/{order_id}/mark-prepared", response_model=schemas.OrderOut)
def mark_prepared(order_id: str, db: Session = Depends(get_db), supplier_id: str = Depends(require_supplier)):
    order = _get_supplier_order(db, order_id, supplier_id)
    # Allow calling mark-prepared directly from 'placed' too (auto-accept) to keep
    # the supplier UI to a single obvious button per prototype requirement.
    if order.status == OrderStatus.placed:
        transition(order, OrderStatus.accepted, db)
    return order_to_out(transition(order, OrderStatus.preparing, db), db)


@app.post("/supplier/orders/{order_id}/bind-drone-and-dispatch", response_model=schemas.OrderOut)
def bind_drone_and_dispatch(
    order_id: str,
    req: schemas.BindDroneRequest,
    db: Session = Depends(get_db),
    supplier_id: str = Depends(require_supplier),
):
    order = _get_supplier_order(db, order_id, supplier_id)
    if order.status != OrderStatus.preparing:
        raise HTTPException(status_code=409, detail="Order must be 'preparing' before dispatch")

    # Drone QR is expected as "DRONE:<drone_id>" — parse defensively.
    payload = req.drone_qr_payload.strip()
    drone_id = payload.split(":", 1)[1].strip() if ":" in payload else payload
    if not drone_id:
        raise HTTPException(status_code=400, detail="Could not parse drone_id from QR payload")

    order.drone_id = drone_id
    db.commit()
    db.refresh(order)
    return order_to_out(transition(order, OrderStatus.dispatched, db), db)


@app.post("/supplier/orders/{order_id}/confirm-launch", response_model=schemas.OrderOut)
def confirm_launch(order_id: str, db: Session = Depends(get_db), supplier_id: str = Depends(require_supplier)):
    """
    Called when the supplier taps "Confirm & Launch" in the web UI, after
    bind-drone-and-dispatch. This is the human go/no-go moment: the Pi
    uploads the mission the instant it's dispatched (inert - no motors),
    but does NOT arm or take off until it polls /drones/{drone_id}/assignment
    and sees launch_confirmed=True, which this sets. Doesn't change
    order.status - the drone itself reports 'in_flight' once it's actually
    airborne (see report_in_flight below).
    """
    order = _get_supplier_order(db, order_id, supplier_id)
    if order.status != OrderStatus.dispatched:
        raise HTTPException(status_code=409, detail="Order must be 'dispatched' before confirming launch")
    if not order.drone_id:
        raise HTTPException(status_code=409, detail="No drone bound to this order yet")
    order.launch_confirmed_at = now()
    db.commit()
    db.refresh(order)
    return order_to_out(order, db)


@app.post("/supplier/orders/{order_id}/mark-in-flight", response_model=schemas.OrderOut)
def mark_in_flight(order_id: str, db: Session = Depends(get_db), supplier_id: str = Depends(require_supplier)):
    """
    Called by the flight-side system (or manually in this prototype) once the
    drone actually lifts off. Kept separate from dispatch since 'dispatched'
    (handed to drone) and 'in_flight' (airborne) are different real-world moments.
    """
    order = _get_supplier_order(db, order_id, supplier_id)
    return order_to_out(transition(order, OrderStatus.in_flight, db), db)


@app.post("/supplier/orders/{order_id}/mark-delivered", response_model=schemas.OrderOut)
def mark_delivered(order_id: str, db: Session = Depends(get_db), supplier_id: str = Depends(require_supplier)):
    order = _get_supplier_order(db, order_id, supplier_id)
    return order_to_out(transition(order, OrderStatus.delivered, db), db)


@app.post("/supplier/orders/{order_id}/cancel", response_model=schemas.OrderOut)
def cancel_order(order_id: str, db: Session = Depends(get_db), supplier_id: str = Depends(require_supplier)):
    order = _get_supplier_order(db, order_id, supplier_id)
    return order_to_out(transition(order, OrderStatus.cancelled, db), db)


def _get_supplier_order(db: Session, order_id: str, supplier_id: str) -> Order:
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.supplier_id != supplier_id:
        raise HTTPException(status_code=403, detail="Order does not belong to this supplier")
    return order


@app.get("/drones/{drone_id}/assignment")
def get_drone_assignment(drone_id: str, db: Session = Depends(get_db)):
    order = (
        db.query(Order)
        .filter(
            Order.drone_id == drone_id,
            Order.status.in_([OrderStatus.dispatched, OrderStatus.in_flight]),
        )
        .order_by(Order.dispatched_at.desc())
        .first()
    )
    if not order:
        return {"has_assignment": False}

    destination_hub = db.query(Hub).filter(Hub.hub_id == order.destination_hub_id).first()
    return {
        "has_assignment": True,
        "order_id": order.order_id,
        "status": order.status,
        "destination_hub_id": order.destination_hub_id,
        "destination_hub_name": destination_hub.name if destination_hub else None,
        "destination_lat": destination_hub.gps_lat if destination_hub else None,
        "destination_lng": destination_hub.gps_lng if destination_hub else None,
        # The Pi uploads the mission the moment it sees a new assignment
        # (inert - no motors), but waits for this to flip True (supplier
        # taps "Confirm & Launch" in the web UI -> confirm-launch endpoint
        # above) before it arms/launches.
        "launch_confirmed": order.launch_confirmed_at is not None,
        # Servo target state - True/False/None (never touched yet). The Pi
        # is responsible for actually driving the servo and should treat
        # None as "leave as-is" rather than forcing a default.
        "payload_locked": order.payload_locked,
    }


@app.post("/drones/{drone_id}/report-in-flight")
def report_in_flight(drone_id: str, db: Session = Depends(get_db)):
    """
    Called by the Pi (not the supplier app) right after it detects the
    vehicle has actually armed and taken off. No supplier bearer token is
    involved here — the drone authenticates itself only by drone_id, which
    is fine for a prototype but is NOT something to expose on the open
    internet as-is before adding a per-drone shared secret/device token.
    """
    order = (
        db.query(Order)
        .filter(Order.drone_id == drone_id, Order.status == OrderStatus.dispatched)
        .order_by(Order.dispatched_at.desc())
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="No dispatched order for this drone")
    return order_to_out(transition(order, OrderStatus.in_flight, db), db)


@app.post("/drones/{drone_id}/report-delivered")
def report_delivered(drone_id: str, db: Session = Depends(get_db)):
    """
    Called by the Pi once it sees the vehicle disarm after completing the
    outbound (delivery) leg of the mission — i.e. it landed at the
    destination. Same device-trust caveat as report-in-flight above.
    """
    order = (
        db.query(Order)
        .filter(Order.drone_id == drone_id, Order.status == OrderStatus.in_flight)
        .order_by(Order.dispatched_at.desc())
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="No in-flight order for this drone")
    return order_to_out(transition(order, OrderStatus.delivered, db), db)


@app.post("/drones/{drone_id}/report-returned-home")
def report_returned_home(drone_id: str, db: Session = Depends(get_db)):
    """
    Called by the Pi once it detects the vehicle has disarmed after the
    RETURN (RTL) leg - i.e. it's physically back home, not just delivered.
    Does not change order.status (delivered is already the correct final
    business status) - this only sets drone_returned_home_at, which is what
    moves the order from the supplier's "Active" list to "Previous" once
    the drone is actually free again, rather than the instant the food
    itself was dropped off.
    """
    order = (
        db.query(Order)
        .filter(
            Order.drone_id == drone_id,
            Order.status == OrderStatus.delivered,
            Order.drone_returned_home_at.is_(None),
        )
        .order_by(Order.delivered_at.desc())
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="No delivered-but-not-yet-returned order for this drone")
    order.drone_returned_home_at = now()
    db.commit()
    db.refresh(order)
    return order_to_out(order, db)


@app.post("/supplier/orders/{order_id}/set-payload-lock", response_model=schemas.OrderOut)
def set_payload_lock(
    order_id: str,
    locked: bool,
    db: Session = Depends(get_db),
    supplier_id: str = Depends(require_supplier),
):
    """
    Toggled from the supplier web page once a drone is bound to the order
    (shown right after the drone QR scan, alongside the drone_id). Purely
    manual - no auto-lock/unlock tied to dispatch or landing, per the
    explicit design decision this matches. The Pi polls this via the
    /drones/{drone_id}/assignment response (payload_locked field) and
    drives the actual servo; this endpoint just records the requested
    state; it does not itself move anything.
    """
    order = _get_supplier_order(db, order_id, supplier_id)
    order.payload_locked = locked
    db.commit()
    db.refresh(order)
    return order_to_out(order, db)


@app.get("/health")
def health():
    return {"ok": True}