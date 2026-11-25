// data/reported.json (scripts/bake_reports.py, the Reports workflow): finds removed after member reports. They are left out
// like dead listings: the app grid (index.html), Swipe Finds (feed.html), the server's first cards and the product sitemap
// (functions/_middleware.js), and their product page says so and is noindex (functions/product/[id].js).
// Read through the static assets, kept for 10 minutes per isolate. A missing or broken file means "none hidden".
// removedIds: only the finds members reported (j.removed, 19 Nov 2026). Finds hidden by the photo cleanup or the owner's
// hide list are in "hidden" too but their pages stay normal (they never got the "removed after reports" notice right).
// 25 Nov 2026 (SEO pass): a read that fails is tried again on the next request (it used to wait 10 minutes with nothing
// hidden), and reportedOk() says whether the list was read, so the middleware does not keep a page counted without it in
// the edge cache for an hour (a crawl on 25 Nov 2026 found /mycnbox-spreadsheet saying 1,938 finds with QC photos, the others 1,267).
let _rep = new Set(), _rm = new Set(), _repAt = 0, _ok = false;
export const reportedOk = () => _ok;
export async function reportedIds(env, origin) {
  if (_repAt && Date.now() - _repAt < 600000) return _rep;
  _repAt = Date.now();
  try {
    const req = new Request(origin + "/data/reported.json");
    const r = env && env.ASSETS ? await env.ASSETS.fetch(req) : await fetch(req);
    if (r.ok) { const j = await r.json(); if (j && Array.isArray(j.hidden)) _rep = new Set(j.hidden.map(String)); _rm = new Set(Array.isArray(j && j.removed) ? j.removed.map(String) : []); _ok = true; }
    else if (r.status === 404) _ok = true;   // no file: nothing hidden
    else if (!_ok) _repAt = 0;
  } catch (e) { if (!_ok) _repAt = 0; }
  return _rep;
}
export async function removedIds(env, origin) { await reportedIds(env, origin); return _rm; }
