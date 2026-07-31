import React, { useState, useMemo } from "react";
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity, Image,
} from "react-native";
import { colors } from "../theme";
import { formatINR } from "../format";

// hub.suppliers already comes back scoped to the locked hub_id from scan-hub.
// Prototype has exactly one supplier, but this renders generically off the array.
export default function MenuScreen({ route, navigation }) {
  const { hub } = route.params;
  const [cart, setCart] = useState({}); // item_id -> qty

  // Prototype scope: one supplier. Grab the first (only) one.
  const supplier = hub.suppliers[0];

  const total = useMemo(() => {
    if (!supplier) return 0;
    return supplier.menu_items.reduce((sum, item) => {
      const qty = cart[item.item_id] || 0;
      return sum + qty * item.price_cents;
    }, 0);
  }, [cart, supplier]);

  const itemCount = Object.values(cart).reduce((a, b) => a + b, 0);

  const changeQty = (itemId, delta) => {
    setCart((prev) => {
      const next = { ...prev };
      const qty = Math.max(0, (next[itemId] || 0) + delta);
      if (qty === 0) delete next[itemId];
      else next[itemId] = qty;
      return next;
    });
  };

  const handleProceedToPayment = () => {
    if (itemCount === 0) return;
    // Build the line items now, while we still have full menu_items in
    // scope (name/price), so PaymentMethod/OrderSummary don't need their
    // own copy of the menu - they just carry this array forward.
    const orderLines = Object.entries(cart).map(([item_id, qty]) => {
      const menuItem = supplier.menu_items.find((m) => m.item_id === item_id);
      return { item_id, qty, name: menuItem.name, price_cents: menuItem.price_cents };
    });
    navigation.navigate("PaymentMethod", {
      hub, supplier, orderLines, total,
    });
  };

  if (!supplier) {
    return (
      <View style={styles.center}>
        <Text>No suppliers available at {hub.hub_name} right now.</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.hubLabel}>Ordering at: {hub.hub_name}</Text>
      <Text style={styles.supplierName}>{supplier.name}</Text>

      <FlatList
        data={supplier.menu_items}
        keyExtractor={(item) => item.item_id}
        contentContainerStyle={{ paddingBottom: 100 }}
        renderItem={({ item }) => {
          const qty = cart[item.item_id] || 0;
          return (
            <View style={styles.row}>
              {item.image_url ? (
                <Image source={{ uri: item.image_url }} style={styles.thumb} />
              ) : (
                <View style={[styles.thumb, styles.thumbFallback]}>
                  <Text style={styles.thumbFallbackText}>{item.name.charAt(0)}</Text>
                </View>
              )}
              <View style={{ flex: 1 }}>
                <Text style={styles.itemName}>{item.name}</Text>
                <Text style={styles.itemPrice}>{formatINR(item.price_cents)}</Text>
              </View>
              <View style={styles.stepper}>
                <TouchableOpacity style={styles.stepBtn} onPress={() => changeQty(item.item_id, -1)}>
                  <Text style={styles.stepBtnText}>–</Text>
                </TouchableOpacity>
                <Text style={[styles.qty, qty > 0 && styles.qtyActive]}>{qty}</Text>
                <TouchableOpacity
                  style={[styles.stepBtn, styles.stepBtnAdd]}
                  onPress={() => changeQty(item.item_id, 1)}
                >
                  <Text style={[styles.stepBtnText, styles.stepBtnTextAdd]}>+</Text>
                </TouchableOpacity>
              </View>
            </View>
          );
        }}
      />

      {itemCount > 0 && (
        <TouchableOpacity style={styles.orderBar} onPress={handleProceedToPayment}>
          <Text style={styles.orderBarText}>
            Place order · {itemCount} item{itemCount > 1 ? "s" : ""} · {formatINR(total)}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, paddingTop: 60, paddingHorizontal: 16 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 },
  hubLabel: {
    fontSize: 12, color: colors.brandDark, fontWeight: "700",
    textTransform: "uppercase", letterSpacing: 0.4,
    backgroundColor: colors.brandLight, alignSelf: "flex-start",
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, marginBottom: 8,
  },
  supplierName: { fontSize: 24, fontWeight: "800", marginBottom: 16, color: colors.ink },
  row: {
    flexDirection: "row", alignItems: "center", paddingVertical: 14, paddingHorizontal: 14,
    backgroundColor: colors.surface, borderRadius: 14, marginBottom: 10,
    borderWidth: 1, borderColor: colors.border,
  },
  itemName: { fontSize: 16, fontWeight: "600", color: colors.ink },
  itemPrice: { fontSize: 14, color: colors.inkMuted, marginTop: 2 },
  thumb: {
    width: 56, height: 56, borderRadius: 12, marginRight: 12, backgroundColor: colors.border,
  },
  thumbFallback: { justifyContent: "center", alignItems: "center" },
  thumbFallbackText: { fontSize: 20, fontWeight: "800", color: colors.inkMuted },
  stepper: { flexDirection: "row", alignItems: "center" },
  stepBtn: {
    width: 34, height: 34, borderRadius: 17, backgroundColor: colors.border,
    justifyContent: "center", alignItems: "center",
  },
  stepBtnAdd: { backgroundColor: colors.brand },
  stepBtnText: { fontSize: 18, fontWeight: "700", color: colors.ink },
  stepBtnTextAdd: { color: "#fff" },
  qty: { minWidth: 30, textAlign: "center", fontSize: 16, fontWeight: "700", color: colors.inkMuted },
  qtyActive: { color: colors.ink },
  orderBar: {
    position: "absolute", bottom: 24, left: 16, right: 16,
    backgroundColor: colors.accent, borderRadius: 14, paddingVertical: 17, alignItems: "center",
    shadowColor: colors.accent, shadowOpacity: 0.35, shadowRadius: 12, shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  orderBarText: { color: "#fff", fontWeight: "800", fontSize: 16, letterSpacing: 0.2 },
});
