import React, { useState, useEffect, useRef } from "react";
import { View, Text, StyleSheet, Alert, ActivityIndicator, Linking, Platform } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import { scanHub } from "../api";
import { colors } from "../theme";

// Scans the physical QR at a hub. The QR encodes ONLY a marker_id string
// (e.g. "HUBMARKER_A") — no GPS or menu data is in the code itself; that's
// looked up from the backend so menus/hub info can change without reprinting.
//
// PERMISSION HANDLING: in Expo Go, camera permission behavior is loose (often
// pre-granted or re-promptable). In a standalone installed APK it is not —
// once a user taps "Deny" a second time (or checks "Don't ask again"),
// Android permanently blocks the in-app system prompt and `requestPermission()`
// silently does nothing further. That state (`canAskAgain === false`) has to
// be handled explicitly by sending the user to device Settings instead of
// looping on a dead button.
export default function ScanScreen({ navigation }) {
  const [permission, requestPermission] = useCameraPermissions();
  const [busy, setBusy] = useState(false);
  const [scannedOnce, setScannedOnce] = useState(false);
  const hasAutoRequested = useRef(false);

  // Ask for permission automatically on first mount rather than waiting for
  // a tap — smoother first-run experience, and still falls through to the
  // explicit denied/blocked states below if the user says no.
  useEffect(() => {
    if (permission && permission.status === "undetermined" && !hasAutoRequested.current) {
      hasAutoRequested.current = true;
      requestPermission();
    }
  }, [permission]);

  if (!permission) {
    return <View style={styles.center}><ActivityIndicator /></View>;
  }

  if (!permission.granted) {
    const permanentlyBlocked = !permission.canAskAgain;
    return (
      <View style={styles.center}>
        <Text style={styles.title}>Camera access needed</Text>
        <Text style={styles.text}>
          This app scans the hub's QR code to know where to source your order
          from — it can't work without camera access.
        </Text>
        {permanentlyBlocked ? (
          <>
            <Text style={[styles.text, styles.warn]}>
              Camera permission was denied. You'll need to enable it manually
              in Settings to continue.
            </Text>
            <Text
              style={styles.link}
              onPress={() =>
                Platform.OS === "ios" ? Linking.openURL("app-settings:") : Linking.openSettings()
              }
            >
              Open device Settings
            </Text>
          </>
        ) : (
          <Text style={styles.link} onPress={requestPermission}>
            Grant camera permission
          </Text>
        )}
      </View>
    );
  }

  const handleScanned = async ({ data }) => {
    if (scannedOnce || busy) return;
    setScannedOnce(true);
    setBusy(true);
    try {
      const hub = await scanHub(data.trim());
      // Lock hub_id into this session by passing it forward — the app
      // now only shows menu items scoped to this hub.
      navigation.replace("Menu", { hub });
    } catch (err) {
      Alert.alert("Couldn't recognize this hub QR", err.message, [
        { text: "Try again", onPress: () => setScannedOnce(false) },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <CameraView
        style={StyleSheet.absoluteFillObject}
        barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
        onBarcodeScanned={scannedOnce ? undefined : handleScanned}
      />
      <View style={styles.overlay}>
        <View style={styles.frame} />
        <Text style={styles.hint}>
          {busy ? "Looking up hub..." : "Point camera at the hub's QR code"}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 },
  overlay: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  frame: {
    width: 240,
    height: 240,
    borderWidth: 3,
    borderColor: colors.brand,
    borderRadius: 20,
    backgroundColor: "transparent",
  },
  hint: {
    marginTop: 24,
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
    backgroundColor: "rgba(20,81,61,0.75)",
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 999,
  },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 12, textAlign: "center", color: colors.ink },
  text: { textAlign: "center", marginBottom: 12, color: colors.inkMuted },
  warn: { color: colors.danger },
  link: { color: colors.brand, fontWeight: "700", marginTop: 8 },
});
