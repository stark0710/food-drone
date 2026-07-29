# Supplier web interface

Plain HTML/CSS/JS, no build step, no framework. Uses `html5-qrcode` (CDN) for
the drone QR scan step, with a manual-entry fallback if the browser has no
camera access (e.g. testing on a laptop with no webcam, or you'd rather type
`DRONE:drone_042` directly).

## Run

Just open `index.html` in a browser. Easiest ways:

```bash
cd supplier_web
python3 -m http.server 5500
# then open http://localhost:5500
```

Edit `API_BASE_URL` at the top of `app.js` if your backend isn't on
`localhost:8000` (e.g. running the backend on a different machine/hub tablet).

## Flow

1. Polls `GET /supplier/orders` every 4s, renders each order as a card with
   status badge and the button(s) valid for its current state.
2. **Mark prepared** — `POST /supplier/orders/{id}/mark-prepared`
   (auto-accepts from `placed` first if needed, per the backend logic).
3. **Scan drone & dispatch** — opens the webcam, scans the QR physically
   printed on the drone, calls
   `POST /supplier/orders/{id}/bind-drone-and-dispatch` with the raw scanned
   payload (expected format `DRONE:<drone_id>`).
4. **Mark in flight** / **Mark delivered** — advance the remaining states.
   (`mark-in-flight` is also where the separate flight/drone team's system
   would call the same endpoint once the drone actually lifts off — it
   doesn't have to be the supplier who taps this.)

## Note

`Html5Qrcode` requires camera permission and (outside `localhost`) HTTPS —
fine for local prototype testing over `http://localhost`, but if you serve
this from a tablet over your LAN IP you may need a self-signed cert or a tool
like `ngrok` for camera access to work in the browser.
