// jsc test for /also.js (macOS): jsc -e "var ALSO_JSON='<data/also.json>', ALSO_JS='<also.js>'" scripts/test_also_js.js
// Stubs the browser bits also.js touches, loads a real also.json and checks get() and scoreFor() against its format.
var DATA = JSON.parse(readFile(ALSO_JSON)), fetched = 0, events = 0, fails = 0;
var window = globalThis;
globalThis.document = { readyState: "complete" };
globalThis.navigator = {};
globalThis.requestIdleCallback = function (f) { f(); };
globalThis.CustomEvent = function (n, o) { this.type = n; this.detail = o && o.detail; };
globalThis.dispatchEvent = function (e) { if (e.type === "pc:also") events++; };
globalThis.fetch = function (u) { fetched++; if (u !== "/data/also.json") throw new Error("url " + u); return Promise.resolve({ ok: true, json: function () { return Promise.resolve(DATA); } }); };
function ok(c, m) { if (!c) { fails++; print("FAIL " + m); } }
load(ALSO_JS);
ok(window.pcAlso && typeof pcAlso.get === "function", "pcAlso exists");
ok(pcAlso.get(DATA.ids[0]).length === 0, "empty before the data is in");
pcAlso.ready.then(function (api) {
  ok(api === pcAlso && api.ok, "ready resolves with pcAlso, ok");
  ok(fetched === 1 && events === 1, "one fetch, one pc:also event (" + fetched + "," + events + ")");
  var n = 0;
  for (var i = 0; i < DATA.ids.length; i++) {
    var id = DATA.ids[i], g = pcAlso.get(id), row = DATA.n[i];
    ok(g.length === row.length / 2, "length " + id);
    for (var x = 0; x < g.length; x++) {
      ok(g[x][0] === DATA.ids[i + row[2 * x]], "neighbour id " + id);
      ok(g[x][1] > 0 && g[x][1] < 1, "score range " + id);
      ok(g[x][2] === (row[2 * x + 1] >= 100), "co-like flag " + id);
      ok(g[x][0] !== id, "never itself " + id);
      n++;
    }
    if (fails > 5) break;
  }
  var a = DATA.ids[10], g = pcAlso.get(a);
  g[0][0] = "changed"; ok(pcAlso.get(a)[0][0] !== "changed", "get returns copies");
  ok(pcAlso.get(a, 3).length === 3, "k limits");
  ok(pcAlso.get("no-such-id").length === 0, "unknown id");
  var b = DATA.ids[20], s = pcAlso.scoreFor([[a, 1], [b, 0.5]]);
  ok(!(a in s) && !(b in s), "anchors left out");
  var first = pcAlso.get(a)[1][0], fromB = 0;
  pcAlso.get(b).forEach(function (e) { if (e[0] === first) fromB = 0.5 * e[1]; });
  ok(Math.abs(s[first] - (pcAlso.get(a)[1][1] + fromB)) < 1e-9, "scoreFor sums weight * score");
  ok(!(first in pcAlso.scoreFor([[a, 1]], { exclude: new Set([first]) })), "exclude Set");
  ok(Object.keys(pcAlso.scoreFor({})).length === 0, "empty anchors");
  print(fails ? "also.js: " + fails + " failures" : "also.js: all checks passed (" + n + " neighbours read)");
});
