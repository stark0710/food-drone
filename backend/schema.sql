-- ============================================================
-- Hub-to-Hub Drone Delivery — Schema
-- Prototype scope: 1 origin hub, 1 supplier, 1 destination hub,
-- but tables are fully normalized for multi-hub extension later.
-- ============================================================

CREATE TABLE hubs (
    hub_id      VARCHAR(50) PRIMARY KEY,      -- e.g. "HUB_A", encoded in the physical QR
    name        VARCHAR(100) NOT NULL,
    gps_lat     DOUBLE PRECISION NOT NULL,
    gps_lng     DOUBLE PRECISION NOT NULL,
    marker_id   VARCHAR(50) NOT NULL UNIQUE,  -- physical QR marker printed at the hub
    is_origin   BOOLEAN NOT NULL DEFAULT TRUE,  -- can this hub originate orders?
    is_destination BOOLEAN NOT NULL DEFAULT TRUE, -- can this hub receive deliveries?
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE suppliers (
    supplier_id VARCHAR(50) PRIMARY KEY,
    hub_id      VARCHAR(50) NOT NULL REFERENCES hubs(hub_id),
    name        VARCHAR(100) NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_suppliers_hub ON suppliers(hub_id);

CREATE TABLE menu_items (
    item_id     VARCHAR(50) PRIMARY KEY,
    supplier_id VARCHAR(50) NOT NULL REFERENCES suppliers(supplier_id),
    name        VARCHAR(150) NOT NULL,
    price_cents INTEGER NOT NULL,
    available   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_menu_items_supplier ON menu_items(supplier_id);

-- Order status state machine:
-- placed -> accepted -> preparing -> dispatched -> in_flight -> delivered
-- (a 'cancelled' escape hatch is included since real kitchens reject orders)
CREATE TYPE order_status AS ENUM (
    'placed', 'accepted', 'preparing', 'dispatched', 'in_flight', 'delivered', 'cancelled'
);

CREATE TABLE orders (
    order_id        VARCHAR(50) PRIMARY KEY,
    origin_hub_id   VARCHAR(50) NOT NULL REFERENCES hubs(hub_id),      -- where the customer scanned in
    destination_hub_id VARCHAR(50) NOT NULL REFERENCES hubs(hub_id),   -- prototype: same as origin, but modeled separately
    supplier_id     VARCHAR(50) NOT NULL REFERENCES suppliers(supplier_id),
    customer_id     VARCHAR(50) NOT NULL,       -- mocked, single test customer
    items           JSONB NOT NULL,             -- [{item_id, name, qty, price_cents}]
    total_cents     INTEGER NOT NULL,
    status          order_status NOT NULL DEFAULT 'placed',
    drone_id        VARCHAR(50),                -- bound at dispatch time via drone QR scan
    placed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_at     TIMESTAMPTZ,
    preparing_at    TIMESTAMPTZ,
    dispatched_at   TIMESTAMPTZ,
    in_flight_at    TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ
);
CREATE INDEX idx_orders_supplier ON orders(supplier_id);
CREATE INDEX idx_orders_status ON orders(status);
