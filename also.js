/* "People who liked this also liked" for the app, the feed and any page: window.pcAlso.
   Data: /data/also.json, made every 6 hours by scripts/bake_also.py (Stats workflow) from members' favourites and opened
   finds counted together anonymously (a pair only when 3+ members hold both), blended with content similarity, so every
   find has about 12 related finds. Nothing is sent from here; the file is the same for everyone.

     pcAlso.ready            Promise, resolves with pcAlso once the file is read (or could not be: then get() gives []).
     pcAlso.ok               true once the data is in.
     pcAlso.get(id[, k])     [[id, score 0..1, coLiked], ...] best first; [] while loading or for an unknown id.
     pcAlso.scoreFor(anchors[, opt])
                             anchors: [[id, weight], ...] (or {id: weight}). Returns {id: summed weight * score} over
                             the anchors' neighbours, anchors themselves left out (opt.exclude: a Set or {id: 1} to
                             leave out more, opt.k: neighbours per anchor, default all).
     pcAlso.load()           start loading now (otherwise it starts once the page is idle, or on the first get()).
     window event "pc:also"  fired once the data is in, for pages that want to re-rank.

   Format (keep in step with bake_also.py encode() and functions/_lib/also.js): {"ids": [...], "n": [[d, c, ...], ...]};
   neighbour = ids[i + d], score = (c % 100) / 100, coLiked = c >= 100. */
(function () {
  if (window.pcAlso) return;
  var SRC = "/data/also.json";
  var ids = null, rows = null, at = null, memo = {}, state = 0;   // state: 0 idle, 1 loading, 2 done (ok or not)
  var done;
  var api = { ok: false, generated: null, size: 0 };
  api.ready = new Promise(function (r) { done = r; });

  function use(d) {
    if (!d || !Array.isArray(d.ids) || !Array.isArray(d.n) || d.ids.length !== d.n.length) return false;
    var m = Object.create(null);
    for (var i = 0; i < d.ids.length; i++) m[d.ids[i]] = i;
    ids = d.ids; rows = d.n; at = m; memo = Object.create(null);
    api.ok = true; api.generated = d.generated || null; api.size = ids.length;
    return true;
  }
  function finish() {
    state = 2; done(api);
    try { window.dispatchEvent(new CustomEvent("pc:also", { detail: { ok: api.ok } })); } catch (e) {}
  }
  api.load = function () {
    if (state) return api.ready;
    state = 1;
    try {
      fetch(SRC, { credentials: "omit" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { use(d); }, function () {})
        .then(finish, finish);
    } catch (e) { finish(); }
    return api.ready;
  };
  api.get = function (id, k) {
    if (!at) { if (!state) api.load(); return []; }
    id = String(id);
    var m = memo[id];
    if (!m) {
      var i = at[id], r = i === undefined ? null : rows[i];
      m = [];
      if (r) for (var x = 0; x + 1 < r.length; x += 2) {
        var j = i + r[x], c = r[x + 1];
        if (j >= 0 && j < ids.length && typeof c === "number") m.push([ids[j], (c % 100) / 100, c >= 100]);
      }
      memo[id] = m;
    }
    return (k ? m.slice(0, k) : m.slice()).map(function (e) { return e.slice(); });
  };
  api.scoreFor = function (anchors, opt) {
    opt = opt || {};
    var list = Array.isArray(anchors) ? anchors : Object.keys(anchors || {}).map(function (k) { return [k, anchors[k]]; });
    var ex = opt.exclude, own = Object.create(null), out = Object.create(null);
    var skip = function (id) { return own[id] || (ex && (typeof ex.has === "function" ? ex.has(id) : ex[id])); };
    list.forEach(function (a) { own[String(a[0])] = 1; });
    list.forEach(function (a) {
      var w = +a[1] || 0; if (!w) return;
      api.get(a[0], opt.k).forEach(function (e) { if (!skip(e[0])) out[e[0]] = (out[e[0]] || 0) + w * e[1]; });
    });
    return out;
  };
  api._use = use;                                                 // tests only
  window.pcAlso = api;

  // Lazy: after the page is idle (the file is about 300 KB compressed and nothing above the fold needs it).
  // With Data Saver on, only when a page asks for it.
  var save = false;
  try { save = !!(navigator.connection && navigator.connection.saveData); } catch (e) {}
  if (save) return;
  var go = function () {
    if (window.requestIdleCallback) requestIdleCallback(function () { api.load(); }, { timeout: 4000 });
    else setTimeout(api.load, 1500);
  };
  if (document.readyState === "complete") go(); else window.addEventListener("load", go, { once: true });
})();
