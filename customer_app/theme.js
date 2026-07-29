// Shared color palette for the customer app. Pulled out into one place so
// MenuScreen / OrderStatusScreen / ScanScreen stay visually consistent
// without each screen inventing its own hex codes.

export const colors = {
  bg: "#faf9f6",
  surface: "#ffffff",
  ink: "#1c2420",
  inkMuted: "#767f78",
  border: "#ececea",

  brand: "#1f7a5c",      // deep leaf green — primary actions, brand
  brandDark: "#14513d",
  brandLight: "#e4f3ec",

  accent: "#ff7a45",     // warm coral — order bar / calls to action

  danger: "#d64545",
  dangerLight: "#fdecec",

  stepDone: "#1f7a5c",
  stepCurrent: "#2f8fd6",
  stepPending: "#e2e5e3",
};
