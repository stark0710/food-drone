import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";

import ScanScreen from "./screens/ScanScreen";
import MenuScreen from "./screens/MenuScreen";
import PaymentMethodScreen from "./screens/PaymentMethodScreen";
import OrderSummaryScreen from "./screens/OrderSummaryScreen";
import OrderStatusScreen from "./screens/OrderStatusScreen";
import BrandHeaderTitle from "./components/BrandHeaderTitle";
import { colors } from "./theme";

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Stack.Navigator
        initialRouteName="Scan"
        screenOptions={{
          // TorqWings brand bar - applied once here so every screen gets
          // the navy header + wordmark automatically, rather than each
          // screen file setting its own header options. headerTitle (not
          // headerLeft) carries the wordmark, so it doesn't collide with
          // the native back button on screens that have one.
          headerStyle: { backgroundColor: colors.brandBarBg },
          headerTitle: () => <BrandHeaderTitle />,
          headerTintColor: colors.brandBarText,
        }}
      >
        <Stack.Screen name="Scan" component={ScanScreen} />
        <Stack.Screen name="Menu" component={MenuScreen} options={{ headerBackVisible: false }} />
        <Stack.Screen name="PaymentMethod" component={PaymentMethodScreen} />
        <Stack.Screen name="OrderSummary" component={OrderSummaryScreen} />
        <Stack.Screen name="OrderStatus" component={OrderStatusScreen} options={{ headerBackVisible: false }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

