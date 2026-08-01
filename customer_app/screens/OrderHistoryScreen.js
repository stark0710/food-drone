import React, { useState, useCallback } from "react";
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { colors } from "../theme";
import { formatINR } from "../format";
import { getOrderHistory } from "../orderHistory";

const PAYMENT_LABELS = {
  cash_on_delivery: "Cash on Delivery",
  upi: "UPI",
};

function timeAgo(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function OrderHistoryScreen({ navigation }) {
  const [history, setHistory] = useState(null); // null = still loading

  // useFocusEffect (not useEffect) so this refreshes every time the screen
  // comes back into view - e.g. after placing a new order and navigating
  // back here, without needing a manual pull-to-refresh.
  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      getOrderHistory().then((h) => {
        if (!cancelled) setHistory(h);
      });
      return () => {
        cancelled = true;
      };
    }, [])
  );

  if (history === null) {
    return <View style={styles.center} />;
  }

  if (history.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.emptyTitle}>No orders yet</Text>
        <Text style={styles.emptyText}>Orders you place will show up here.</Text>
        <TouchableOpacity style={styles.scanBtn} onPress={() => navigation.navigate("Scan")}>
          <Text style={styles.scanBtnText}>Scan a hub to order</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={history}
        keyExtractor={(entry) => entry.orderId}
        contentContainerStyle={{ padding: 16 }}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.card}
            onPress={() => navigation.navigate("OrderStatus", { orderId: item.orderId, hub: item.hub, fromHistory: true })}
          >
            <View style={styles.cardTop}>
              <Text style={styles.orderId}>#{item.orderId.replace("ord_", "")}</Text>
              <Text style={styles.total}>{formatINR(item.total)}</Text>
            </View>
            <Text style={styles.supplierName}>{item.supplierName}</Text>
            <Text style={styles.meta}>
              {item.itemCount} item{item.itemCount > 1 ? "s" : ""} ·{" "}
              {PAYMENT_LABELS[item.paymentMethod] || item.paymentMethod} · {timeAgo(item.placedAt)}
            </Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, backgroundColor: colors.bg },
  emptyTitle: { fontSize: 18, fontWeight: "800", color: colors.ink, marginBottom: 6 },
  emptyText: { fontSize: 14, color: colors.inkMuted, textAlign: "center", marginBottom: 20 },
  scanBtn: { backgroundColor: colors.brand, borderRadius: 14, paddingVertical: 14, paddingHorizontal: 24 },
  scanBtnText: { color: "#fff", fontWeight: "700", fontSize: 15 },
  card: {
    backgroundColor: colors.surface, borderRadius: 14, borderWidth: 1, borderColor: colors.border,
    padding: 16, marginBottom: 12,
  },
  cardTop: { flexDirection: "row", justifyContent: "space-between", marginBottom: 4 },
  orderId: {
    fontSize: 11, color: colors.brandDark, fontWeight: "700", textTransform: "uppercase",
    letterSpacing: 0.4, backgroundColor: colors.brandLight, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999,
  },
  total: { fontSize: 16, fontWeight: "800", color: colors.ink },
  supplierName: { fontSize: 16, fontWeight: "700", color: colors.ink, marginTop: 6 },
  meta: { fontSize: 13, color: colors.inkMuted, marginTop: 4 },
});
