// Shipping lines on the agent spreadsheets (23 Nov 2026, SEO pass; read again and widened to ten countries on 28 Nov 2026,
// SEO report: most Google visitors of the agent pages are in Europe outside the UK): what each agent's own shipping
// estimator quoted for a 1 kg parcel (branded clothing where the estimator asks for a goods type) to the ten countries
// with the most search clicks. Per country: the two cheapest lines and the fastest one (a fastest line counts only at up
// to 5 times the cheapest price). Left out: rail and sea lines, lines of 30 days or more, lines only for shoes, cosmetics,
// liquids, perfume or batteries ("electrified"), and lines with a minimum weight above 1 kg. Prices are the estimators'
// list prices in US dollars, before coupons and before any charge for box size. They change often: read the estimators
// again (and update SHIP_READ) before relying on them for more than a few weeks.
//   KakoBuy:  kakobuy.com/tools/estimate in a browser, weight 1000 g, no goods type.
//   Sugargoo: sugargoo.com/freight-estimate in a browser, weight 1000 g, category "clothes(BD)" (branded clothing); the
//             first state or province listed for the country.
//   Oopbuy:   oopbuy.com/estimation (its public estimate service), weight 1000 g, category "International Brand Clothing";
//             Oopbuy gives delivery times in business days.
// MyCNBox's estimator needs an account, but its homepage publishes delivery figures and real parcel samples (MYCNBOX_SHIP).
// LoveGoBuy's site sits behind a browser check, so it has no table here.
export const SHIP_READ = "28 Nov 2026";
export const SHIP_TO = { us: "United States", gb: "United Kingdom", de: "Germany", se: "Sweden", dk: "Denmark", pl: "Poland", nl: "Netherlands", cz: "Czechia", ca: "Canada", au: "Australia" };
// [line name as the agent writes it, US dollars, fewest days, most days]
export const SHIP_LINES = {
  kakobuy: { src: "KakoBuy's shipping estimator", what: "a 1 kg parcel (no goods type given)", days: "days", rows: {"us": [["UPS Duty-Free (No Batteries)", 39.5, 2, 6], ["USPS Tax-Free Line (Battery Accepted)", 39.5, 7, 13]], "gb": [["UK HG dedicated line PT", 17.15, 7, 19], ["UK Air Freight Direct Line (Economy)", 19.24, 6, 12], ["HKUPS", 71.47, 5, 10]], "de": [["Europe DHL Line(Express Line)", 24.93, 8, 12], ["Europe Tariffless Line -K", 25.91, 7, 12], ["HKUPS", 67.59, 5, 10]], "se": [["Europe Tariffless Line -K", 27.86, 8, 12], ["NL-BRAM", 34.38, 15, 20], ["HKUPS-T", 102.66, 3, 8]], "dk": [["Europe Tariffless Line -K", 27.56, 7, 15], ["DPD Line", 35.61, 7, 12], ["HKUPS", 82.24, 5, 10]], "pl": [["HKUPS-T", 25.53, 7, 13], ["HKUPS", 29.11, 5, 10]], "nl": [["Europe Tariffless Line -K", 28.15, 7, 15], ["Europe DHL Small Parcel (Economy)", 31.75, 13, 17], ["HKUPS", 82.24, 5, 10]], "cz": [["Europe Tariffless Line -K", 29.04, 7, 15], ["Europe DHL Small Parcel (Economy)", 30.65, 13, 17], ["HKUPS", 106.36, 5, 10]], "ca": [["Canada HD Line", 23.62, 7, 18], ["Canada HG Line-H", 25.35, 5, 20], ["UPS(HK)-X", 50.96, 5, 10]], "au": [["Australia Special Line -B", 18.94, 7, 10], ["AU-EXPRESS", 23.47, 3, 15], ["HKUPS", 69.13, 4, 10]]} },
  sugargoo: { src: "Sugargoo's shipping fee estimation page", what: "a 1 kg parcel of branded clothing", days: "days", rows: {"us": [["EUB(US)", 24.8, 15, 25], ["US Fast Line", 27.81, 10, 15]], "gb": [["UK Fast Line", 15.78, 10, 15], ["UK clothing line", 15.78, 10, 15], ["UPS(HK)", 52.3, 7, 12]], "de": [["DHL Tax Free", 22.7, 17, 25], ["DHL Tax Free(Actual Weight)", 24.2, 15, 20], ["UPS(HK)", 52.3, 7, 12]], "se": [["EUB(GD)", 19.54, 15, 30], ["EUB-D(GD)", 28.56, 15, 30], ["UPS(HK)", 52.3, 7, 12]], "dk": [["EUB-D(GD)", 24.8, 15, 30], ["SAL", 26.15, 20, 40], ["UPS(HK)", 52.3, 7, 12]], "pl": [["PL clothing line", 22.55, 12, 20], ["EUB(GD)", 23.0, 15, 30], ["UPS(HK)", 52.3, 7, 12]], "nl": [["NL clothing line", 24.05, 10, 17], ["SAL", 24.65, 20, 40], ["UPS(HK)", 52.3, 7, 12]], "cz": [["SAL", 24.65, 20, 40], ["DHL Tax Free", 27.05, 17, 25], ["DHL Tax Free Express(Actual Weight)", 31.26, 12, 18]], "ca": [["SAL", 20.89, 20, 40], ["CA clothing line", 22.55, 10, 20], ["UPS(HK)-D", 49.3, 7, 12]], "au": [["EUB(GD)", 18.04, 15, 30], ["EMS-CY-60", 22.39, 15, 26], ["UPS(HK)-X", 56.36, 7, 12]]} },
  oopbuy: { src: "Oopbuy's shipping estimation page", what: "a 1 kg parcel of branded clothing", days: "business days", rows: {"us": [["DDF-GOFO-US-1", 35.67, 15, 20], ["DDF-UNI-US-1", 35.67, 15, 20], ["ZF-UPSMAX-US-1", 124.26, 8, 12]], "gb": [["DDF-RoyalMail-GB-1", 22.21, 10, 15], ["SF-RoyalMail-GB-1", 23.25, 7, 14]], "de": [["DDF-DHL-DE-1", 32.71, 8, 16], ["ZSF-DHL-DE-1", 34.11, 8, 14]], "se": [["JF-DHL-SE-1", 55.36, 10, 18], ["ZSF-DHL-SE-1", 57.36, 8, 14]], "dk": [["JF-DHL-DK-1", 51.03, 10, 18], ["ZSF-DHL-DK-1", 51.15, 8, 14]], "pl": [["STF-IP-PL-1", 35.4, 8, 16], ["ZTF-INPOST-PL-1", 35.67, 10, 16], ["ZSF-DHL-PL-1", 39.8, 8, 14]], "nl": [["ZTF-DHL-NL-1", 38.09, 10, 16], ["STF-DHL-NL-1", 38.6, 8, 16], ["ZSF-DHL-NL-1", 40.6, 8, 14]], "cz": [["ZSF-DHL-CZ-1", 37.95, 8, 14], ["DDF-DHL-CZ-1", 39.71, 8, 16]], "ca": [["BF-Canada Post-CA-1", 32.98, 10, 20], ["BD-Canada Post-CA-1", 33.25, 10, 20], ["ZF-UNI-CA-1", 34.06, 8, 16]], "au": [["HF-EUB-AU-1", 24.47, 9, 20], ["ZF-POST-AU-1", 26.13, 15, 25]]} },
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
