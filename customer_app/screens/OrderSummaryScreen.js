import React, { useState } from "react";
import { View, Text, StyleSheet, FlatList, TouchableOpacity, Alert, ActivityIndicator } from "react-native";
import { placeOrder } from "../api";
import { colors } from "../theme";
import { formatINR } from "../format";

const PAYMENT_LABELS = {
  cash_on_delivery: "Cash on Delivery",
  upi: "UPI",
};

// Last stop before an order actually exists server-side. Everything above
// this screen (Menu -> PaymentMethod) is just building up navigation
// params - POST /orders only happens here, on Confirm.
export default function OrderSummaryScreen({ route, navigation }) {
  const { hub, supplier, orderLines, total, paymentMethod } = route.params;
  const [placing, setPlacing] = useState(false);

  const handleConfirm = async () => {
    setPlacing(true);
    try {
      const items = orderLines.map(({ item_id, qty }) => ({ item_id, qty }));
      const order = await placeOrder({
        hubId: hub.hub_id,
        supplierId: supplier.supplier_id,
        items,
        paymentMethod,
      });
      navigation.replace("OrderStatus", { orderId: order.order_id, hub });
    } catch (err) {
      Alert.alert("Couldn't place order", err.message);
    } finally {
      setPlacing(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Order summary</Text>
      <Text style={styles.hubLabel}>{hub.hub_name} · {supplier.name}</Text>

      <FlatList
        data={orderLines}
        keyExtractor={(line) => line.item_id}
        contentContainerStyle={{ paddingBottom: 12 }}
        renderItem={({ item: line }) => (
          <View style={styles.lineRow}>
            <Text style={styles.lineQty}>{line.qty}×</Text>
            <Text style={styles.lineName}>{line.name}</Text>
            <Text style={styles.lineAmount}>{formatINR(line.price_cents * line.qty)}</Text>
          </View>
        )}
        ListFooterComponent={
          <View style={styles.totalsBlock}>
            <View style={styles.totalRow}>
              <Text style={styles.subtotalLabel}>Subtotal</Text>
              <Text style={styles.subtotalAmount}>{formatINR(total)}</Text>
            </View>
            <View style={styles.totalRow}>
              <Text style={styles.totalLabel}>Total</Text>
              <Text style={styles.totalAmount}>{formatINR(total)}</Text>
            </View>
            <View style={styles.paymentRow}>
              <Text style={styles.paymentLabel}>Payment method</Text>
              <Text style={styles.paymentValue}>{PAYMENT_LABELS[paymentMethod] || paymentMethod}</Text>
            </View>
          </View>
        }
      />

      <TouchableOpacity style={styles.confirmBtn} onPress={handleConfirm} disabled={placing}>
        {placing ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.confirmBtnText}>Confirm Order · {formatINR(total)}</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, paddingTop: 32, paddingHorizontal: 20 },
  title: { fontSize: 22, fontWeight: "800", color: colors.ink },
  hubLabel: { fontSize: 13, color: colors.inkMuted, marginTop: 4, marginBottom: 20, fontWeight: "600" },
  lineRow: {
    flexDirection: "row", alignItems: "center", paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  lineQty: { width: 32, fontSize: 14, fontWeight: "700", color: colors.inkMuted },
  lineName: { flex: 1, fontSize: 15, fontWeight: "600", color: colors.ink },
  lineAmount: { fontSize: 15, fontWeight: "600", color: colors.ink },
  totalsBlock: { marginTop: 16, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.border },
  totalRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 8 },
  subtotalLabel: { fontSize: 14, color: colors.inkMuted },
  subtotalAmount: { fontSize: 14, color: colors.inkMuted },
  totalLabel: { fontSize: 18, fontWeight: "800", color: colors.ink },
  totalAmount: { fontSize: 18, fontWeight: "800", color: colors.ink },
  paymentRow: {
    flexDirection: "row", justifyContent: "space-between", marginTop: 12,
    paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.border,
  },
  paymentLabel: { fontSize: 14, color: colors.inkMuted, fontWeight: "600" },
  paymentValue: { fontSize: 14, color: colors.brandDark, fontWeight: "800" },
  confirmBtn: {
    marginTop: 12, marginBottom: 24, backgroundColor: colors.accent, borderRadius: 14,
    paddingVertical: 17, alignItems: "center",
    shadowColor: colors.accent, shadowOpacity: 0.35, shadowRadius: 12, shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  confirmBtnText: { color: "#fff", fontWeight: "800", fontSize: 16, letterSpacing: 0.2 },
});
