// Shared color palette for the customer app. Pulled out into one place so
// MenuScreen / OrderStatusScreen / ScanScreen stay visually consistent
// without each screen inventing its own hex codes.
//
// TorqWings brand colors (brandBar*) are kept separate from the in-app
// green/coral palette (brand/accent) rather than replacing it wholesale.
// The brand bar at the very top of every screen carries the TorqWings
// identity (navy background, cyan wordmark); everything below it - buttons,
// steppers, status dots - keeps using the existing green/coral scheme,
// which is already tuned for food/ordering UI and doesn't need to change
// just because the header now carries a different brand.

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

  // TorqWings brand bar - visible at the top of every screen via the
  // navigator's header. #0a0f1c is TorqWings' actual site background navy.
  // The cyan accent is a placeholder pending their exact secondary brand
  // color - swap brandBarAccent below once confirmed, nothing else needs
  // to change since every screen references this one constant.
  brandBarBg: "#0a0f1c",
  brandBarAccent: "#34d3e0",
  brandBarText: "#ffffff",
};
