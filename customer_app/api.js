// API_BASE_URL is baked in at BUILD TIME from the EXPO_PUBLIC_API_BASE_URL
// env var (see eas.json -> build.preview.env, and .env for local dev). Any
// env var prefixed EXPO_PUBLIC_ gets inlined into the JS bundle by Expo/Metro
// at build time — that's what makes it work in a standalone APK, since an
// installed app has no dev server to read a runtime "localhost" from.
//
// - Running in Expo Go on your dev machine: falls back to your LAN IP below.
//   Swap this for your machine's actual LAN IP (not "localhost" — the phone
//   is a separate device and can't resolve your laptop's localhost).
// - Building the APK: set EXPO_PUBLIC_API_BASE_URL in eas.json's preview
//   profile to your deployed Render URL (see backend/DEPLOY.md), and this
//   constant will use that instead.
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL || "http://192.168.1.42:8000";

export const CUSTOMER_TOKEN = "customer-dev-token"; // mocked auth, single test customer

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${CUSTOMER_TOKEN}`,
      ...(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

export function scanHub(markerId) {
  return request(`/hubs/${encodeURIComponent(markerId)}/scan`);
}

export function placeOrder({ hubId, supplierId, items }) {
  return request(`/orders`, {
    method: "POST",
    body: JSON.stringify({ hub_id: hubId, supplier_id: supplierId, items }),
  });
}

export function getOrder(orderId) {
  return request(`/orders/${orderId}`);
}

export function getOrderStatus(orderId) {
  return request(`/orders/${orderId}/status`);
}
