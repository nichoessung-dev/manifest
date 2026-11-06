// data/also.json (scripts/bake_also.py, every 6 hours in the Stats workflow): for every find, about 12 related finds,
// from members' favourites and opened finds counted together anonymously, blended with content similarity. Read like
// data/stats.json in site.js: once per isolate, kept for 10 minutes, a failed read retried after 30 s. A missing or
// broken file means "no related finds" and the product page simply has no "People also liked" row.
// Format (keep in step with bake_also.py encode() and /also.js): {"ids": [...], "n": [[d, c, ...], ...]};
// neighbour = ids[i + d], score = (c % 100) / 100, coLiked = c >= 100.
let _ids = null, _rows = null, _at = null, _gen = null, _t = 0;
const TTL = 10 * 60 * 1000, RETRY = 30 * 1000, WAIT = 1500;

export async function ensureAlso(origin) {
  if (_t && Date.now() - _t < TTL) return;
  const had = !!_at;
  _t = Date.now();
  let ok = false;
  try {
    const r = await Promise.race([fetch(origin + "/data/also.json"), new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), WAIT))]);
    if (r.ok) {
      const d = await r.json();
      if (d && Array.isArray(d.ids) && Array.isArray(d.n) && d.ids.length === d.n.length) {
        ok = true;
        if (!had || d.generated !== _gen) { _ids = d.ids; _rows = d.n; _gen = d.generated || null; _at = new Map(d.ids.map((x, i) => [String(x), i])); }
      }
    }
  } catch (e) {}
  if (!ok) _t = Date.now() - TTL + RETRY;
}

// [[id, score 0..1, coLiked], ...] best first; [] when the file is not read or the id is not in it.
export function alsoOf(id) {
  if (!_at) return [];
  const i = _at.get(String(id)), r = i === undefined ? null : _rows[i], out = [];
  if (!r) return out;
  for (let x = 0; x + 1 < r.length; x += 2) {
    const j = i + r[x], c = r[x + 1];
    if (j >= 0 && j < _ids.length && typeof c === "number") out.push([_ids[j], (c % 100) / 100, c >= 100]);
  }
  return out;
}
