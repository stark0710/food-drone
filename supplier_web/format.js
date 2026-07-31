// Shared money formatting. Backend stores prices as integer paise (still
// named price_cents in the schema/DB - not renamed, to avoid a migration -
// but it's paise now that the app displays ₹). Pulled into one place so
// MenuScreen and OrderSummaryScreen can't drift into different formats.
export function formatINR(paise) {
  return `₹${(paise / 100).toFixed(2)}`;
}
