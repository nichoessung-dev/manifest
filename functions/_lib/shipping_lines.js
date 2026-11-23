// Shipping lines on the agent spreadsheets (23 Nov 2026, SEO pass): what each agent's own shipping estimator quoted for a
// 1 kg parcel of branded clothing to four of the countries with the most buy clicks (data/dashboard.json), read by hand in
// the browser on the day below. Per country: the three cheapest lines and the fastest one. Left out: rail and sea lines
// (45 to 75 days), lines only for shoes, cosmetics or batteries, and lines with a minimum weight above 1 kg. Prices are the
// estimator's list prices in US dollars, before coupons and before any charge for box size. They change often: read the
// estimators again (and update SHIP_READ) before relying on them for more than a few weeks.
//   KakoBuy:  kakobuy.com/tools/estimate, weight 1000 g, no goods type.
//   Sugargoo: sugargoo.com/freight-estimate, weight 1000 g, category "clothes(BD)" (branded clothing); the first state or
//             province listed for the country.
//   Oopbuy:   oopbuy.com/estimation (its public estimate service), weight 1000 g, category "International Brand Clothing";
//             Oopbuy gives delivery times in business days.
// MyCNBox's estimator needs an account, but its homepage publishes delivery figures and real parcel samples (MYCNBOX_SHIP).
// LoveGoBuy's site sits behind a browser check, so it has no table here.
export const SHIP_READ = "23 Nov 2026";
export const SHIP_TO = { us: "United States", gb: "United Kingdom", de: "Germany", se: "Sweden" };
// [line name as the agent writes it, US dollars, fewest days, most days]
export const SHIP_LINES = {
  kakobuy: { src: "KakoBuy's shipping estimator", days: "days", rows: {"us": [["USPS Tax-Free Line (Battery Accepted)", 39.42, 7, 13], ["UPS Duty-Free (No Batteries)", 39.43, 2, 6], ["EUB (Batteries and Perfume Not Allowed)", 39.49, 15, 25]], "gb": [["UK HG dedicated line PT", 17.11, 7, 19], ["UK Air Freight Direct Line (Economy)", 19.2, 6, 12], ["UK Line-B", 21.0, 5, 12], ["CN small package (Actual Weight)", 29.17, 7, 10]], "de": [["Europe DHL Line (Express Line)", 24.88, 8, 12], ["Europe Tariffless Line -K", 25.86, 7, 12], ["Europe Tariffless Line -M", 27.81, 8, 25], ["DHL Duty-Free Fast Line K (No Battery)", 31.27, 5, 10]], "se": [["Europe Tariffless Line -K", 27.81, 8, 12], ["NL-BRAM", 34.32, 15, 20], ["Europe DHL Line (Express Line)", 40.32, 7, 12], ["HKUPS-T", 102.47, 3, 8]]} },
  sugargoo: { src: "Sugargoo's shipping fee estimation page", days: "days", rows: {"us": [["EUB(US)", 24.75, 15, 25], ["US Fast Line", 27.75, 10, 15], ["TUB(US)", 31.5, 20, 25]], "gb": [["UK Fast Line", 15.75, 10, 15], ["UK clothing line", 15.75, 10, 15], ["UK Fast Line (Actual Weight)", 16.65, 10, 15], ["UPS(HK)", 52.2, 7, 12]], "de": [["EUB(GD)", 22.5, 15, 30], ["DHL Tax Free", 22.65, 17, 25], ["DHL Tax Free(Actual Weight)", 24.15, 15, 20], ["UPS(HK)", 52.2, 7, 12]], "se": [["EUB(GD)", 19.5, 15, 30], ["EUB-D(GD)", 28.5, 15, 30], ["EMS-60", 33.3, 10, 20], ["UPS(HK)", 52.2, 7, 12]]} },
  oopbuy: { src: "Oopbuy's shipping estimation page", days: "business days", rows: {"us": [["DDF-GOFO-US-1", 35.57, 15, 20], ["DDF-UNI-US-1", 35.57, 15, 20], ["DDF-USPS-US-1", 36.1, 10, 20], ["ZF-UPSMAX-US-1", 123.89, 8, 12]], "gb": [["DDF-RoyalMail-GB-1", 22.14, 10, 15], ["SF-RoyalMail-GB-1", 23.18, 7, 14], ["ZD-Roymail-GB-1", 24.37, 8, 16]], "de": [["ZF-DHL-DE-1", 31.03, 8, 16], ["ZSF-DHL-DE-1", 34.01, 8, 14], ["JF-DHL-DE-1", 36.93, 10, 18]], "se": [["JF-DHL-SE-1", 55.19, 10, 18], ["ZSF-DHL-SE-1", 57.19, 8, 14], ["DSF-DHL-SE-1", 57.68, 8, 14]]} },
};
// mycnbox.com homepage, read 23 Nov 2026: its delivery averages, six parcels it shows as real samples, and its warehouse
// times for the week 16 to 22 Nov 2026 (Beijing time).
export const MYCNBOX_SHIP = {
  read: "23 Nov 2026", avgDays: 12.5, china: 5.4, customs: 2.6, dest: 4.5, perKg: 15.95, avgKg: 4.79, inspected: 4.8, delivered: 99.5,
  // [country, line, parcel price in US dollars, days, US dollars per kg]
  samples: [["United States", "EMS-CD-US", 149.08, 15, 29.8], ["Canada", "EMS-CD", 82.73, 12, 16.55], ["United Kingdom", "UK Air Cargo-JDY Special", 60.69, 15, 12.14],
            ["Australia", "EMS-CD", 65.72, 12, 13.14], ["Netherlands", "EUR DHL Economy", 73.79, 15, 14.75], ["Germany", "EUR DHL Economy", 70.64, 14, 14.12]],
  week: { from: "16 Nov 2026", to: "22 Nov 2026", purchaseH: 12.62, toWarehouseH: 70.1, qcMin: 4.08, packedH: 5.62 },
};
