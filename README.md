# Hub-to-Hub Food Delivery Drone — Customer App + Backend Prototype

Scope: 1 origin hub, 1 supplier, 1 destination hub. Drone/flight control is
out of scope (separate team) — this system only needs a `drone_id` string to
bind to an order at dispatch time.

```
food-drone/
├── backend/           FastAPI + Postgres — schema, models, all REST endpoints
├── customer_app/      Expo (React Native) — scan, menu, order status
├── supplier_web/      Plain HTML/JS — incoming orders, prepare, dispatch
├── hub_a_test_qr.png       Test QR encoding "HUBMARKER_A" (scan this in the app)
└── drone_042_test_qr.png   Test QR encoding "DRONE:drone_042" (scan at dispatch)
```

## Get it running end-to-end (in order)

```bash
# 1. Backend
cd backend
cp .env.example .env
docker compose up -d
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn main:app --reload --port 8000

# 2. Supplier web (new terminal)
cd ../supplier_web
python3 -m http.server 5500
# open http://localhost:5500

# 3. Customer app (new terminal)
cd ../customer_app
npm install
npx expo start
# scan the Expo QR with Expo Go on your phone
# (set api.js API_BASE_URL to your machine's LAN IP first, not localhost)
```

Then:
1. In the customer app, scan `hub_a_test_qr.png` (open it on a laptop screen
   or print it) → menu for Hub A Kitchen appears.
2. Add items, place the order → status screen starts polling.
3. In the supplier web page, the order appears under "Incoming Orders."
   Click **Mark prepared**.
4. Click **Scan drone & dispatch**, scan `drone_042_test_qr.png` (or type
   `DRONE:drone_042` in the manual field) → order becomes `dispatched`.
5. Click **Mark in flight**, then **Mark delivered**.
6. Watch the customer app's status screen update through each step within
   ~3 seconds of each supplier action, with no app restart needed.

## What's already handled for you

- **Order state machine is enforced server-side** (`models.ALLOWED_TRANSITIONS`
  in the backend) — no client (customer app, supplier web, or a stray curl
  request) can skip a step, e.g. dispatch before prepared. Verified this with
  an automated end-to-end test through every state, including a rejected
  illegal transition (409).
- **hubs / suppliers / menu_items are separate normalized tables**, not
  hardcoded — a second hub is a new seed row, not a schema change.
- **Mocked auth** is two hardcoded bearer tokens (see `backend/.env.example`),
  swappable later without touching route logic.
- **Real-time-ish updates** via polling: customer app polls order status
  every 3s, supplier web polls the incoming queue every 4s.

## What's intentionally NOT built (matches your scope)

- No drone/flight control, no telemetry ingestion — the backend just accepts
  a `drone_id` string at dispatch and never talks to the drone itself.
- No real authentication, payments, or push notifications.
- No multi-hub routing UI (data model supports it, but there's only one hub
  seeded).

## Natural next steps once the prototype is validated

- Swap polling for Server-Sent Events or WebSockets on the status endpoint.
- Real auth (e.g. Supabase/Firebase auth or a simple JWT flow) in place of
  the two hardcoded tokens.
- A webhook or endpoint for the flight team's system to call
  `mark-in-flight` / `mark-delivered` automatically instead of a manual
  supplier tap.
