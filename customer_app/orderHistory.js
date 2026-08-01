import AsyncStorage from "@react-native-async-storage/async-storage";

// On-device order history. This prototype has no real customer accounts
// (every order uses the same mocked CUSTOMER_TOKEN from api.js), so there's
// no server-side "my orders" to fetch — the app has to remember locally
// which orders THIS device placed. Good enough for a prototype; swap for a
// real backend "GET /customers/me/orders" once there's real customer auth.

const STORAGE_KEY = "hubdrone:order_history";
const MAX_ENTRIES = 50; // plenty for a prototype, keeps AsyncStorage small

// Each entry: { orderId, hub, supplierName, itemCount, total, paymentMethod, placedAt }
// `hub` is stored in full (not just hub_id) so tapping into history can
// still offer "Order again" without an extra network round-trip.

export async function addOrderToHistory(entry) {
  try {
    const existing = await getOrderHistory();
    // De-dupe just in case (e.g. a double-tap on Confirm before navigation
    // away), newest first.
    const next = [entry, ...existing.filter((e) => e.orderId !== entry.orderId)].slice(0, MAX_ENTRIES);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch (err) {
    // Order history is a convenience feature, not critical path - never let
    // a storage failure block or crash the actual order-placement flow.
    console.warn("Failed to save order to local history:", err);
  }
}

export async function getOrderHistory() {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (err) {
    console.warn("Failed to read order history:", err);
    return [];
  }
}

export async function clearOrderHistory() {
  try {
    await AsyncStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    console.warn("Failed to clear order history:", err);
  }
}
