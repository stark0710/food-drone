import enum
from sqlalchemy import (
    Column, String, Boolean, Float, Integer, ForeignKey, JSON, DateTime, Enum
)
from sqlalchemy.sql import func
from database import Base


class OrderStatus(str, enum.Enum):
    placed = "placed"
    accepted = "accepted"
    preparing = "preparing"
    dispatched = "dispatched"
    in_flight = "in_flight"
    delivered = "delivered"
    cancelled = "cancelled"


# Valid forward transitions for the order state machine.
# Enforced in main.py so the supplier interface (or any client) can't skip steps.
ALLOWED_TRANSITIONS = {
    OrderStatus.placed: {OrderStatus.accepted, OrderStatus.cancelled},
    OrderStatus.accepted: {OrderStatus.preparing, OrderStatus.cancelled},
    OrderStatus.preparing: {OrderStatus.dispatched, OrderStatus.cancelled},
    OrderStatus.dispatched: {OrderStatus.in_flight},
    OrderStatus.in_flight: {OrderStatus.delivered},
    OrderStatus.delivered: set(),
    OrderStatus.cancelled: set(),
}


class Hub(Base):
    __tablename__ = "hubs"

    hub_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    gps_lat = Column(Float, nullable=False)
    gps_lng = Column(Float, nullable=False)
    marker_id = Column(String(50), nullable=False, unique=True)
    is_origin = Column(Boolean, nullable=False, default=True)
    is_destination = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(String(50), primary_key=True)
    hub_id = Column(String(50), ForeignKey("hubs.hub_id"), nullable=False)
    name = Column(String(100), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MenuItem(Base):
    __tablename__ = "menu_items"

    item_id = Column(String(50), primary_key=True)
    supplier_id = Column(String(50), ForeignKey("suppliers.supplier_id"), nullable=False)
    name = Column(String(150), nullable=False)
    price_cents = Column(Integer, nullable=False)
    available = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(50), primary_key=True)
    origin_hub_id = Column(String(50), ForeignKey("hubs.hub_id"), nullable=False)
    destination_hub_id = Column(String(50), ForeignKey("hubs.hub_id"), nullable=False)
    supplier_id = Column(String(50), ForeignKey("suppliers.supplier_id"), nullable=False)
    customer_id = Column(String(50), nullable=False)
    items = Column(JSON, nullable=False)          # [{item_id, name, qty, price_cents}]
    total_cents = Column(Integer, nullable=False)
    status = Column(Enum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.placed)
    drone_id = Column(String(50), nullable=True)

    placed_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    preparing_at = Column(DateTime(timezone=True), nullable=True)
    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    in_flight_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
