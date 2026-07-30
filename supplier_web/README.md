# Supplier web interface

Plain HTML/CSS/JS, no build step, no framework. Uses `html5-qrcode` (CDN) for
the drone QR scan step, with a manual-entry fallback if the browser has no
camera access (e.g. testing on a laptop with no webcam, or you'd rather type
`DRONE:drone_042` directly).

## Run on your phone (HTTPS required for the camera)

`python3 -m http.server` only serves `localhost` — a phone on your WiFi can't
reach that, and even if it could, `Html5Qrcode` requires HTTPS for camera
access once you're off `localhost`. Two ways to actually get this on a phone:

**Fastest (test right now, no config file):**
1. Go to https://app.netlify.com/drop in a browser.
2. Drag the whole `supplier_web/` folder onto the page.
3. It gives you an `https://...netlify.app` URL immediately — open that on
   your phone. Camera access will work since it's real HTTPS.
4. Every time you edit `app.js`/`style.css`, just drag the folder again for
   a new deploy (or connect it to your git repo in Netlify's dashboard for
   auto-deploy on push, if you want that instead of drag-and-drop each time).

**Permanent, same dashboard as your backend:**
Add this service to your repo's `render.yaml`, alongside the existing
backend entry:
```yaml
  - type: web
    name: hubdrone-supplier-web
    runtime: static
    rootDir: supplier_web
    buildCommand: "echo 'no build step'"
    staticPublishPath: .
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```
Push, and Render's Blueprint deploys it alongside the backend as
`https://hubdrone-supplier-web.onrender.com` (Render may append `-<random>`
if that name's taken — check your dashboard for the exact URL).

Either way — once deployed, edit `API_BASE_URL` at the top of `app.js` to
point at your live backend (`https://hubdrone-backend.onrender.com`, not
`localhost`) before deploying, or the phone won't be able to reach it.

## Local development

For testing on a laptop with a webcam (or manual drone-QR entry — plain
`http://localhost` is exempt from the HTTPS requirement):

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
   payload (expected format `DRONE:<drone_id>`). This binds the drone and
   the Pi uploads the mission — but does **not** arm or take off yet.
4. **Confirm & Launch** — a separate button (shown in the scan modal right
   after dispatch, and again on the order card if the modal gets closed
   first) that calls `POST /supplier/orders/{id}/confirm-launch`. This is
   the actual go/no-go moment: the onboard Pi polls for this flag and only
   arms + takes off once it's set, not the instant the QR gets scanned.
5. **Mark in flight** / **Mark delivered** — manual override/fallback if
   the drone-side telemetry reporting isn't available; normally the Pi
   itself calls the equivalent `/drones/{drone_id}/report-in-flight` and
   `/drones/{drone_id}/report-delivered` once it's actually airborne/landed.

## Note

`Html5Qrcode` requires camera permission and (outside `localhost`) HTTPS —
see the phone-deployment section above. Local `http://localhost` testing is
exempt from the HTTPS requirement, which is why that still works fine.
