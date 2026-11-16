/**
 * Cloudflare Pages Function: one sample of "live viewers" (owner, 15 Nov 2026: "a statistic on /stats called avg live
 * viewers" + "a graph of the live viewers").
 * Route: POST /api/live-sample  ->  200 {"n": 12, "stored": true}
 *
 * The live count on /stats is the Supabase Realtime presence channel "online-viewers" (every open tab of the site joins
 * it, index.html). Nothing kept that number, so there was no average and no history. A Cloudflare Worker with a cron
 * trigger (puroclassico-live-sampler, every 5 minutes) calls this route. It reads the channel's presence state the way
 * /stats does (joins without being counted), and appends [slot, n] to stats/live-samples.json in the public "products"
 * storage bucket: 5-minute slots, the last 35 days. /stats reads that file for the average and the graph.
 * One sample per 5-minute slot: a second call in the same slot only answers the count. No visitor data is stored.
 * Env: SUPABASE_SERVICE_KEY (already set).
 */
const SUPA = "https://uptpghuduqjqmrxwatbm.supabase.co";
const ANON = "sb_publishable_qFcO570Cpl0_VWS6e_sAUg_noD-2XmY";   // the public key the site already ships
const OBJ = "products/stats/live-samples.json";
const SLOT = 300, KEEP = 35 * 86400;

const LOG = [];
function presenceCount() {
  return new Promise(async (resolve, reject) => {
    let ws;
    try {
      const r = await fetch(`${SUPA}/realtime/v1/websocket?apikey=${ANON}&vsn=1.0.0`, { headers: { Upgrade: "websocket" } });
      ws = r.webSocket;
      if (!ws) return reject(new Error("no websocket (" + r.status + ")"));
      ws.accept();
    } catch (e) { return reject(e); }
    const done = (fn, v) => { clearTimeout(t); try { ws.close(1000, "done"); } catch (e) {} fn(v); };
    const t = setTimeout(() => done(reject, new Error("no presence state in time")), 6000);
    ws.addEventListener("message", ev => {
      if (LOG.length < 6) LOG.push(String(ev.data).slice(0, 300));
      let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.event === "presence_state") {
        let n = 0; for (const k in m.payload || {}) n += ((m.payload[k] || {}).metas || []).length;
        done(resolve, n);
      }
    });
    ws.send(JSON.stringify({ topic: "realtime:online-viewers", event: "phx_join", ref: "1",
      payload: { config: { presence: { key: "", enabled: true }, broadcast: { self: false, ack: false }, private: false }, access_token: ANON } }));
  });
}

export async function onRequestPost({ env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json", "cache-control": "no-store" } });
  if (!env || !env.SUPABASE_SERVICE_KEY) return json({ error: "not configured" }, 501);
  // The open tabs of the site call this at a random moment in each 5-minute slot (index.html liveTick).
  const now = Math.floor(Date.now() / 1000), slot = now - (now % SLOT);
  let rows = [];
  try {
    const r = await fetch(`${SUPA}/storage/v1/object/public/${OBJ}?t=${now}`, { cf: { cacheTtl: 0 } });
    if (r.ok) { const d = await r.json(); if (Array.isArray(d.s)) rows = d.s; }
  } catch (e) {}
  // About 4 tabs call per slot: each reads the count and the slot keeps the highest, so a short spike between two
  // readings is caught more often (the peak on /stats). A slot whose reading is not higher is left as it is.
  let n;
  try { n = await presenceCount(); } catch (e) { return json({ error: String(e.message || e), log: LOG.splice(0) }, 502); }
  const last = rows.length ? rows[rows.length - 1] : null;
  if (last && last[0] >= slot) { if (n <= last[1]) return json({ n, stored: false, kept: last[1] }); last[1] = n; }
  else rows.push([slot, n]);
  rows = rows.filter(x => x[0] >= now - KEEP);
  const body = JSON.stringify({ updated: now, slot: SLOT, s: rows });
  const up = await fetch(`${SUPA}/storage/v1/object/${OBJ}`, { method: "POST", body,
    headers: { authorization: "Bearer " + env.SUPABASE_SERVICE_KEY, apikey: env.SUPABASE_SERVICE_KEY, "content-type": "application/json", "x-upsert": "true", "cache-control": "max-age=60" } });
  return json({ n, stored: up.ok, status: up.status });
}
