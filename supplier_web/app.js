// ---- config (mocked auth, single test supplier) ----
const API_BASE_URL = "https://hubdrone-backend.onrender.com";
const SUPPLIER_TOKEN = "supplier-dev-token";
const POLL_INTERVAL_MS = 4000;

const ordersListEl = document.getElementById("orders-list");
const connStatusEl = document.getElementById("conn-status");
const scanModal = document.getElementById("scan-modal");
const scanCancelBtn = document.getElementById("scan-cancel");
const manualInput = document.getElementById("manual-drone-input");
const manualSubmit = document.getElementById("manual-drone-submit");
const routeConfirmEl = document.getElementById("route-confirm");
const routeConfirmFromEl = document.getElementById("route-confirm-from");
const routeConfirmToEl = document.getElementById("route-confirm-to");
const routeConfirmStatusEl = document.getElementById("route-confirm-status");
const qrReaderEl = document.getElementById("qr-reader");

let html5QrScanner = null;
let orderIdPendingDispatch = null;
let lastOrders = []; // cache of the most recent /supplier/orders render, for lookups by id

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${SUPPLIER_TOKEN}`,
      ...(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

function fmtMoney(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

function renderOrders(orders) {
  lastOrders = orders;

  if (orders.length === 0) {
    ordersListEl.innerHTML = `<p class="empty-state">No incoming orders right now.</p>`;
    return;
  }

  ordersListEl.innerHTML = orders.map(orderCardHtml).join("");

  // Wire up buttons after render (event delegation would also work, this is simpler for a prototype)
  orders.forEach((order) => {
    const prepBtn = document.getElementById(`prep-${order.order_id}`);
    if (prepBtn) prepBtn.onclick = () => handleMarkPrepared(order.order_id);

    const dispatchBtn = document.getElementById(`dispatch-${order.order_id}`);
    if (dispatchBtn) dispatchBtn.onclick = () => openDispatchModal(order.order_id);

    const inFlightBtn = document.getElementById(`inflight-${order.order_id}`);
    if (inFlightBtn) inFlightBtn.onclick = () => handleAction(order.order_id, "mark-in-flight");

    const deliveredBtn = document.getElementById(`delivered-${order.order_id}`);
    if (deliveredBtn) deliveredBtn.onclick = () => handleAction(order.order_id, "mark-delivered");

    const cancelBtn = document.getElementById(`cancel-${order.order_id}`);
    if (cancelBtn) cancelBtn.onclick = () => handleAction(order.order_id, "cancel");
  });
}

function orderCardHtml(order) {
  const itemsHtml = order.items
    .map((i) => `<div>${i.qty}× ${i.name} — ${fmtMoney(i.price_cents * i.qty)}</div>`)
    .join("");

  const originName = order.origin_hub_name || order.origin_hub_id;
  const destName = order.destination_hub_name || order.destination_hub_id;
  const routeHtml = `
    <div class="hub-route">
      <span class="hub-route-label">Route</span>
      <span class="hub-route-path">${originName} <span class="route-arrow">→</span> ${destName}</span>
    </div>
  `;

  return `
    <div class="order-card">
      <div class="order-card-top">
        <div>
          <div class="order-id">#${order.order_id.replace("ord_", "")}</div>
          <span class="status-badge status-${order.status}">${order.status.replace("_", " ")}</span>
        </div>
        <div class="order-total">${fmtMoney(order.total_cents)}</div>
      </div>
      ${routeHtml}
      <div class="items-list">${itemsHtml}</div>
      ${order.drone_id ? `<div class="drone-tag">Drone: ${order.drone_id}</div>` : ""}
      <div class="actions">
        ${actionButtonsHtml(order)}
      </div>
    </div>
  `;
}

function actionButtonsHtml(order) {
  switch (order.status) {
    case "placed":
    case "accepted":
      return `
        <button id="prep-${order.order_id}">Mark prepared</button>
        <button id="cancel-${order.order_id}" class="secondary danger">Cancel</button>
      `;
    case "preparing":
      return `<button id="dispatch-${order.order_id}">Scan drone & dispatch</button>`;
    case "dispatched":
      return `<button id="inflight-${order.order_id}" class="secondary">Mark in flight</button>`;
    case "in_flight":
      return `<button id="delivered-${order.order_id}">Mark delivered</button>`;
    default:
      return "";
  }
}

async function handleMarkPrepared(orderId) {
  try {
    await api(`/supplier/orders/${orderId}/mark-prepared`, { method: "POST" });
    await refreshOrders();
  } catch (err) {
    alert(err.message);
  }
}

async function handleAction(orderId, actionPath) {
  try {
    await api(`/supplier/orders/${orderId}/${actionPath}`, { method: "POST" });
    await refreshOrders();
  } catch (err) {
    alert(err.message);
  }
}

// ---- Drone QR scan -> bind + dispatch ----

function openDispatchModal(orderId) {
  orderIdPendingDispatch = orderId;
  scanModal.classList.remove("hidden");
  manualInput.value = "";
  routeConfirmEl.classList.add("hidden");
  qrReaderEl.classList.remove("hidden");
  startQrScanner();
}

function closeDispatchModal() {
  scanModal.classList.add("hidden");
  orderIdPendingDispatch = null;
  stopQrScanner();
}

function startQrScanner() {
  html5QrScanner = new Html5Qrcode("qr-reader");
  html5QrScanner
    .start(
      { facingMode: "environment" },
      { fps: 10, qrbox: 220 },
      (decodedText) => onDroneQrScanned(decodedText),
      () => {} // ignore per-frame scan failures
    )
    .catch((err) => {
      console.warn("Camera unavailable, falling back to manual entry:", err);
    });
}

function stopQrScanner() {
  if (html5QrScanner) {
    html5QrScanner.stop().catch(() => {});
    html5QrScanner = null;
  }
}

async function onDroneQrScanned(payload) {
  if (!orderIdPendingDispatch) return;
  const orderId = orderIdPendingDispatch;
  const order = lastOrders.find((o) => o.order_id === orderId);

  // Stop the camera and show the From -> To confirmation instead of closing
  // the modal immediately — the supplier should see where this is headed
  // before/while the dispatch call completes.
  stopQrScanner();
  qrReaderEl.classList.add("hidden");
  routeConfirmFromEl.textContent = order?.origin_hub_name || order?.origin_hub_id || "—";
  routeConfirmToEl.textContent = order?.destination_hub_name || order?.destination_hub_id || "—";
  routeConfirmStatusEl.textContent = "Confirming with drone…";
  routeConfirmEl.classList.remove("hidden");

  try {
    await api(`/supplier/orders/${orderId}/bind-drone-and-dispatch`, {
      method: "POST",
      body: JSON.stringify({ drone_qr_payload: payload }),
    });
    routeConfirmStatusEl.textContent = "Dispatched ✓";
    routeConfirmStatusEl.classList.add("ok");
    await refreshOrders();
    // Brief pause so the confirmation is actually readable before it closes.
    setTimeout(() => {
      routeConfirmStatusEl.classList.remove("ok");
      closeDispatchModal();
    }, 1100);
  } catch (err) {
    closeDispatchModal();
    alert(err.message);
  }
}

manualSubmit.onclick = () => {
  const value = manualInput.value.trim();
  if (value) onDroneQrScanned(value);
};
scanCancelBtn.onclick = closeDispatchModal;

// ---- polling loop ----

async function refreshOrders() {
  try {
    const orders = await api(`/supplier/orders`);
    renderOrders(orders);
    connStatusEl.textContent = "live";
    connStatusEl.className = "pill ok";
  } catch (err) {
    connStatusEl.textContent = "connection error";
    connStatusEl.className = "pill err";
  }
}

refreshOrders();
setInterval(refreshOrders, POLL_INTERVAL_MS);
