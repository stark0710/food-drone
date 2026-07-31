import React, { useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { colors } from "../theme";

const METHODS = [
  { key: "cash_on_delivery", label: "Cash on Delivery", blurb: "Pay when your order arrives" },
  { key: "upi", label: "UPI", blurb: "Pay by UPI (no gateway in this prototype - choice only)" },
];

// Doesn't place the order - just captures the choice and hands the whole
// order context (hub, supplier, orderLines, total) forward to
// OrderSummaryScreen, which is where the order actually gets POSTed.
export default function PaymentMethodScreen({ route, navigation }) {
  const { hub, supplier, orderLines, total } = route.params;
  const [selected, setSelected] = useState(null);

  const handleContinue = () => {
    if (!selected) return;
    navigation.navigate("OrderSummary", {
      hub, supplier, orderLines, total, paymentMethod: selected,
    });
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>How would you like to pay?</Text>

      {METHODS.map((m) => {
        const active = selected === m.key;
        return (
          <TouchableOpacity
            key={m.key}
            style={[styles.option, active && styles.optionActive]}
            onPress={() => setSelected(m.key)}
          >
            <View style={[styles.radio, active && styles.radioActive]}>
              {active && <View style={styles.radioDot} />}
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.optionLabel, active && styles.optionLabelActive]}>{m.label}</Text>
              <Text style={styles.optionBlurb}>{m.blurb}</Text>
            </View>
          </TouchableOpacity>
        );
      })}

      <TouchableOpacity
        style={[styles.continueBtn, !selected && styles.continueBtnDisabled]}
        onPress={handleContinue}
        disabled={!selected}
      >
        <Text style={styles.continueBtnText}>Continue</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, paddingTop: 32, paddingHorizontal: 20 },
  title: { fontSize: 22, fontWeight: "800", color: colors.ink, marginBottom: 20 },
  option: {
    flexDirection: "row", alignItems: "center", padding: 16, borderRadius: 14,
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, marginBottom: 12,
  },
  optionActive: { borderColor: colors.brand, backgroundColor: colors.brandLight },
  radio: {
    width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: colors.border,
    marginRight: 14, justifyContent: "center", alignItems: "center",
  },
  radioActive: { borderColor: colors.brand },
  radioDot: { width: 11, height: 11, borderRadius: 6, backgroundColor: colors.brand },
  optionLabel: { fontSize: 16, fontWeight: "700", color: colors.ink },
  optionLabelActive: { color: colors.brandDark },
  optionBlurb: { fontSize: 13, color: colors.inkMuted, marginTop: 2 },
  continueBtn: {
    marginTop: 24, backgroundColor: colors.accent, borderRadius: 14, paddingVertical: 17, alignItems: "center",
  },
  continueBtnDisabled: { opacity: 0.4 },
  continueBtnText: { color: "#fff", fontWeight: "800", fontSize: 16, letterSpacing: 0.2 },
});
