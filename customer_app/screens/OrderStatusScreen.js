import React, { useEffect, useRef, useState } from "react";
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from "react-native";
import { getOrderStatus } from "../api";
import { colors } from "../theme";

const STEPS = [
  { key: "placed", label: "Order placed" },
  { key: "accepted", label: "Accepted by kitchen" },
  { key: "preparing", label: "Preparing" },
  { key: "dispatched", label: "Handed to drone" },
  { key: "in_flight", label: "In flight" },
  { key: "delivered", label: "Delivered" },
];

const POLL_INTERVAL_MS = 3000;

export default function OrderStatusScreen({ route, navigation }) {
  const { orderId, hub } = route.params;
  const [status, setStatus] = useState(null);
  const [droneId, setDroneId] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const data = await getOrderStatus(orderId);
        if (cancelled) return;
        setStatus(data.status);
        setDroneId(data.drone_id);
        setError(null);
        // Stop polling once we hit a terminal state.
        if (data.status === "delivered" || data.status === "cancelled") {
          clearInterval(intervalRef.current);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    };

    poll(); // fetch immediately, then start interval
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalRef.current);
    };
  }, [orderId]);

  if (!status && !error) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  const activeIndex = STEPS.findIndex((s) => s.key === status);
  const isCancelled = status === "cancelled";
  const isTerminal = status === "delivered" || status === "cancelled";

  // navigation.reset (not .navigate/.replace) so this finished order doesn't
  // linger in the back stack once the customer starts over.
  const handleBackToHome = () => {
    navigation.reset({ index: 0, routes: [{ name: "Scan" }] });
  };

  // Skips re-scanning the hub QR since we already know the hub from this
  // session — jumps straight back to the menu for the same hub.
  const handleReorder = () => {
    navigation.reset({ index: 0, routes: [{ name: "Menu", params: { hub } }] });
  };

  return (
    <View style={styles.container}>
      <Text style={styles.orderId}>Order #{orderId.replace("ord_", "")}</Text>

      {isCancelled ? (
        <Text style={styles.cancelled}>This order was cancelled.</Text>
      ) : (
        <View style={styles.timeline}>
          {STEPS.map((step, i) => {
            const done = i <= activeIndex;
            const current = i === activeIndex;
            return (
              <View key={step.key} style={styles.stepRow}>
                <View style={[styles.dot, done && styles.dotDone, current && styles.dotCurrent]} />
                <Text style={[styles.stepLabel, done && styles.stepLabelDone]}>{step.label}</Text>
              </View>
            );
          })}
        </View>
      )}

      {droneId && (
        <Text style={styles.droneInfo}>Assigned drone: {droneId}</Text>
      )}

      {error && <Text style={styles.error}>Connection issue: {error}. Retrying…</Text>}

      {isTerminal && (
        <View style={styles.terminalActions}>
          {hub && (
            <TouchableOpacity style={styles.reorderBtn} onPress={handleReorder}>
              <Text style={styles.reorderBtnText}>Order again from {hub.hub_name}</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity style={styles.homeBtn} onPress={handleBackToHome}>
            <Text style={styles.homeBtnText}>Back to Home</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, paddingTop: 80, paddingHorizontal: 24 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  orderId: {
    fontSize: 12, color: colors.brandDark, fontWeight: "700", marginBottom: 32,
    textTransform: "uppercase", letterSpacing: 0.5,
    backgroundColor: colors.brandLight, alignSelf: "flex-start",
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999,
  },
  timeline: {},
  stepRow: { flexDirection: "row", alignItems: "center", marginBottom: 24 },
  dot: {
    width: 16, height: 16, borderRadius: 8, backgroundColor: colors.stepPending, marginRight: 16,
  },
  dotDone: { backgroundColor: colors.stepDone },
  dotCurrent: { backgroundColor: colors.stepCurrent },
  stepLabel: { fontSize: 16, color: "#b3b8b5" },
  stepLabelDone: { color: colors.ink, fontWeight: "700" },
  droneInfo: { marginTop: 16, fontSize: 14, color: colors.inkMuted, fontWeight: "600" },
  cancelled: { fontSize: 18, color: colors.danger, fontWeight: "700" },
  error: { marginTop: 24, color: colors.danger, fontSize: 13 },
  terminalActions: { marginTop: 40, gap: 12 },
  reorderBtn: {
    backgroundColor: colors.accent, borderRadius: 14, paddingVertical: 16, alignItems: "center",
  },
  reorderBtnText: { color: "#fff", fontWeight: "800", fontSize: 15 },
  homeBtn: {
    backgroundColor: colors.surface, borderRadius: 14, paddingVertical: 16, alignItems: "center",
    borderWidth: 1, borderColor: colors.border,
  },
  homeBtnText: { color: colors.ink, fontWeight: "700", fontSize: 15 },
});
