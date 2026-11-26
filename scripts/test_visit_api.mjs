// Tests for functions/api/visit.js (no network). Run: node scripts/test_visit_api.mjs
import assert from "node:assert/strict";
import { visitRow, onRequestPost } from "../functions/api/visit.js";

const SID = "0b7e3c1a-5d2f-4e8a-9c3b-1f2e3d4c5b6a";
const UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";

// visitRow: cleans and caps everything
assert.equal(visitRow({ s: "not-a-uuid" }), null);
assert.equal(visitRow(null), null);
let r = visitRow({ s: SID.toUpperCase(), a: 99999, p: 0, f: "3", fs: -5, fn: 2, b: 1, e: "/brand/x?utm_source=tt#top", r: 1, src: "Google<script>" });
assert.deepEqual(r, { p_sid: SID, p_active: 14400, p_pages: 1, p_finds: 3, p_find_s: 0, p_find_n: 2, p_buys: 1, p_entry: "/brand/x",
  p_returning: true, p_source: "googlescript" });
assert.equal(visitRow({ s: SID, e: "javascript:alert(1)" }).p_entry, "");
assert.equal(visitRow({ s: SID, e: "/" + "a".repeat(300) }).p_entry.length, 120);
assert.equal(visitRow({ s: SID, r: 0 }).p_returning, false);

// onRequestPost: always 204; writes only for a real visit from our pages
async function post(body, headers = {}, env = { SUPABASE_SERVICE_KEY: "k" }) {
  const calls = []; const waits = [];
  globalThis.fetch = async (url, init) => { calls.push({ url, body: JSON.parse(init.body) }); return new Response(null, { status: 204 }); };
  const request = new Request("https://www.puroclassico.com/api/visit", { method: "POST", body: typeof body === "string" ? body : JSON.stringify(body),
    headers: { origin: "https://www.puroclassico.com", "user-agent": UA, "content-type": "application/json", ...headers } });
  const res = await onRequestPost({ request, env, waitUntil: p => waits.push(p) });
  await Promise.all(waits);
  return { status: res.status, calls };
}
let out = await post({ s: SID, a: 42, p: 2 });
assert.equal(out.status, 204);
assert.equal(out.calls.length, 1);
assert.match(out.calls[0].url, /\/rest\/v1\/rpc\/log_visit$/);
assert.equal(out.calls[0].body.p_active, 42);
assert.equal((await post({ s: SID }, { origin: "https://evil.example" })).calls.length, 0);
assert.equal((await post({ s: SID }, { "user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" })).calls.length, 0);
assert.equal((await post({ s: SID }, { "user-agent": UA.replace("Mobile", "HeadlessChrome") })).calls.length, 0);
assert.equal((await post({ s: SID }, {}, {})).calls.length, 0);                    // no key: nothing stored
assert.equal((await post("{" + "x".repeat(2000))).calls.length, 0);               // too big
assert.equal((await post("not json")).status, 204);
console.log("visit api: all tests passed");
