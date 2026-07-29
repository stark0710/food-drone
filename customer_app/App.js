import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";

import ScanScreen from "./screens/ScanScreen";
import MenuScreen from "./screens/MenuScreen";
import OrderStatusScreen from "./screens/OrderStatusScreen";

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="dark" />
      <Stack.Navigator initialRouteName="Scan">
        <Stack.Screen name="Scan" component={ScanScreen} options={{ title: "Scan hub QR" }} />
        <Stack.Screen name="Menu" component={MenuScreen} options={{ title: "Menu", headerBackVisible: false }} />
        <Stack.Screen name="OrderStatus" component={OrderStatusScreen} options={{ title: "Order status", headerBackVisible: false }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
