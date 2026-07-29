# Customer app — Expo (React Native)

## Run

```bash
cd customer_app
npm install
# Edit api.js -> API_BASE_URL to your machine's LAN IP (not localhost) if testing
# on a physical phone via Expo Go, e.g. "http://192.168.1.42:8000"
npx expo start
```

Scan the QR Expo prints with the Expo Go app on your phone, or press `i` / `a`
for iOS/Android simulators (camera scanning only works on a real device or a
simulator with a virtual camera feed).

## Flow

1. **Scan** — camera opens, scans the physical hub QR (which encodes only
   `marker_id`), calls `GET /hubs/{marker_id}/scan`, locks that hub into the
   session by passing the resolved `hub` object forward.
2. **Menu** — renders only the supplier(s)/items returned for that hub.
   Quantity steppers build a cart; "Place order" calls `POST /orders`.
3. **OrderStatus** — polls `GET /orders/{id}/status` every 3s and renders a
   step timeline through `placed → accepted → preparing → dispatched →
   in_flight → delivered`. Polling stops automatically at delivered/cancelled.

## Building a standalone installable APK (EAS Build)

This produces a real `.apk` you can install on any Android phone without
Expo Go — needed once you're past dev-loop testing.

**Requires a free Expo account.** `eas login` will prompt you to sign up if
you don't have one (https://expo.dev — email/GitHub/Google all work).

```bash
cd customer_app
npm install -g eas-cli          # one-time, global CLI
eas login                       # prompts for your Expo account credentials

eas build:configure             # one-time per project. Prompts for platform
                                 # (choose Android). Writes an "extra.eas.projectId"
                                 # into app.json automatically — this links the
                                 # local project to an Expo-hosted project record.

eas build -p android --profile preview
```

What happens:
1. Before deciding this is worth doing yourself: **first update `eas.json`**
   — the `preview` profile's `EXPO_PUBLIC_API_BASE_URL` is currently set to
   a placeholder (`https://hubdrone-backend.onrender.com`). Replace it with
   your actual deployed backend URL from `backend/DEPLOY.md` before running
   the build, since this value gets compiled into the JS bundle at build
   time — you can't change it after the APK is built without rebuilding.
2. `eas build` uploads your project to Expo's cloud build servers (not run
   locally) and compiles a real Android APK using your `app.json`
   (package name, icon, permissions) and the `preview` profile from
   `eas.json` (`buildType: apk`, `distribution: internal` — this is the
   non-Play-Store path).
3. It prints a build progress URL like
   `https://expo.dev/accounts/<you>/projects/hubdrone-customer/builds/<id>`
   — open that in a browser to watch progress (usually 5-15 min).
4. When it finishes, **the same page shows a "Download" button** for the
   `.apk` file, plus a QR code you can scan directly with the phone's camera
   to download and install it (you'll need to allow "install from unknown
   sources" the first time, since this isn't from the Play Store).

## Test QR code

To test without a real printed hub QR, generate a QR image encoding exactly:

```
HUBMARKER_A
```

(matches the `marker_id` seeded in the backend). Any QR generator works —
e.g. `qrencode -o hub_a.png "HUBMARKER_A"` or any online QR generator.
