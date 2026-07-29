# Deploying the backend so a real phone (not on your Wi-Fi) can reach it

You need a public HTTPS URL baked into the APK before building it — an
installed app can't fall back to "ask the user for localhost." Two paths,
pick one:

## Path A (recommended): Render — persistent URL, free, no credit card

**Requires:** a free Render account (https://render.com — sign up with
GitHub is fastest).

1. Push this `food-drone` folder to a GitHub repo (Render deploys from Git).
2. In the Render dashboard: **New -> Blueprint**, pick the repo. Render
   detects `render.yaml` at the repo root and provisions:
   - a free Postgres instance (`hubdrone-db`)
   - the FastAPI web service (`hubdrone-backend`), wired to that database
     automatically via the `DATABASE_URL` env var
3. Click **Apply**. First deploy takes a few minutes (installs deps, runs
   `seed.py`, starts uvicorn).
4. Once live, Render gives you a URL like:
   `https://hubdrone-backend.onrender.com`
   Test it: `https://hubdrone-backend.onrender.com/health` should return
   `{"ok": true}`.

**Tradeoffs:**
- Free web services **spin down after 15 min of inactivity**. The first
  request after that takes 30-60s to wake up — hit `/health` a minute
  before you demo so it's warm.
- Free Postgres **expires after 30 days**. Fine for a 2-week prototype;
  re-run the blueprint if you need it longer.
- This URL is stable as long as the Render service exists — it doesn't
  depend on your laptop being on or online. This is the right choice for
  handing someone an APK to test on their own phone/network.

## Path B (faster, but session-bound): ngrok

**Requires:** a free ngrok account (needed for a stable-enough authtoken;
the fully anonymous mode now has tighter rate limits).

```bash
# one-time
brew install ngrok   # or download from ngrok.com
ngrok config add-authtoken <your-token-from-ngrok-dashboard>

# every time you want to demo
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
# in a second terminal:
ngrok http 8000
```

ngrok prints a URL like `https://a1b2c3d4.ngrok-free.app`. Use that as
`API_BASE_URL`.

**Tradeoff — read this carefully:** this URL **only works while that ngrok
process and your laptop are both running**, and on the free plan the URL
changes every time you restart ngrok (so you'd need to rebuild the APK, or
re-bake the URL, each session). Fine for "I'm demoing live in the next hour
from my laptop," wrong for "I'm handing this APK to someone else to try
later."

---

**I've wired the app to use Path A** (Render) as the default in `api.js`
below, since standalone APKs are usually installed and tested away from
your dev machine — that's the whole point of not using Expo Go anymore. If
you want Path B instead for a quick same-day demo, it's a one-line env
change (see `customer_app/README.md`).
