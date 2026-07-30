from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from models import OrderStatus


# ---------- Hub / scan-hub ----------

class MenuItemOut(BaseModel):
    item_id: str
    name: str
    price_cents: int
    available: bool

    class Config:
        from_attributes = True


class SupplierWithMenuOut(BaseModel):
    supplier_id: str
    name: str
    menu_items: List[MenuItemOut]


class ScanHubResponse(BaseModel):
    hub_id: str
    hub_name: str
    suppliers: List[SupplierWithMenuOut]


# ---------- Orders ----------

class OrderItemIn(BaseModel):
    item_id: str
    qty: int


class PlaceOrderRequest(BaseModel):
    hub_id: str            # locked from the customer's scanned session
    supplier_id: str
    items: List[OrderItemIn]


class OrderItemOut(BaseModel):
    item_id: str
    name: str
    qty: int
    price_cents: int


class OrderOut(BaseModel):
    order_id: str
    origin_hub_id: str
    origin_hub_name: Optional[str] = None
    origin_hub_lat: Optional[float] = None
    origin_hub_lng: Optional[float] = None
    destination_hub_id: str
    destination_hub_name: Optional[str] = None
    destination_hub_lat: Optional[float] = None
    destination_hub_lng: Optional[float] = None
    supplier_id: str
    customer_id: str
    items: List[OrderItemOut]
    total_cents: int
    status: OrderStatus
    drone_id: Optional[str] = None
    launch_confirmed_at: Optional[datetime] = None
    placed_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    preparing_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    in_flight_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderStatusOut(BaseModel):
    order_id: str
    status: OrderStatus
    drone_id: Optional[str] = None
    updated_at: Optional[datetime] = None


# ---------- Supplier actions ----------

class BindDroneRequest(BaseModel):
    drone_qr_payload: str   # raw scanned string, e.g. "DRONE:drone_042"
