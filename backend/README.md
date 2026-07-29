# Backend — FastAPI + Postgres

## Run locally

```bash
cd backend
cp .env.example .env
docker compose up -d          # starts Postgres on localhost:5432
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py                 # creates tables + seeds HUB_A / sup_test_1 / menu
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Docs / interactive test console: http://localhost:8000/docs

## Mocked auth

No real login. Two hardcoded bearer tokens (see `.env.example`):

- Customer app sends: `Authorization: Bearer customer-dev-token`
- Supplier web sends: `Authorization: Bearer supplier-dev-token`

## Endpoints

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/hubs/{marker_id}/scan` | customer | resolve scanned hub QR -> suppliers + menu |
| POST | `/orders` | customer | place an order |
| GET | `/orders/{order_id}` | customer | full order detail |
| GET | `/orders/{order_id}/status` | customer | lightweight status for polling |
| GET | `/supplier/orders` | supplier | incoming order queue |
| POST | `/supplier/orders/{id}/accept` | supplier | placed -> accepted |
| POST | `/supplier/orders/{id}/mark-prepared` | supplier | -> preparing |
| POST | `/supplier/orders/{id}/bind-drone-and-dispatch` | supplier | scans drone QR, binds drone_id, -> dispatched |
| POST | `/supplier/orders/{id}/mark-in-flight` | supplier/flight-team | -> in_flight |
| POST | `/supplier/orders/{id}/mark-delivered` | supplier | -> delivered |
| POST | `/supplier/orders/{id}/cancel` | supplier | -> cancelled |

## Notes for extension

- `hubs`, `suppliers`, `menu_items` are already normalized tables — adding a
  second hub/supplier is just a new seed row, no schema or endpoint changes.
- `origin_hub_id` / `destination_hub_id` are stored separately even though the
  prototype always sets them equal, so multi-hub routing later is a data change.
- Order status transitions are enforced server-side in `ALLOWED_TRANSITIONS`
  (models.py) so no client can skip a step (e.g. dispatch before prepared).
