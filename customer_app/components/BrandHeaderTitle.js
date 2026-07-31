import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../theme";

// Rendered as the native-stack headerTitle for every screen (see App.js),
// so it's the one persistent brand element visible no matter where the
// customer is in the flow, without eating into each screen's own header
// back-button slot.
export default function BrandHeaderTitle() {
  return (
    <View style={styles.wrap}>
      <Text style={styles.torq}>Torq</Text>
      <Text style={styles.wings}>Wings</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: "row", alignItems: "center" },
  torq: { fontSize: 17, fontWeight: "800", color: colors.brandBarText, letterSpacing: 0.3 },
  wings: { fontSize: 17, fontWeight: "800", color: colors.brandBarAccent, letterSpacing: 0.3 },
});
