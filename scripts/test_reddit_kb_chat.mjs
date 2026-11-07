// Node test for the community tips in the chat assistant: node scripts/test_reddit_kb_chat.mjs
// Stubs fetch (the tips file and the Anthropic stream) and the edge cache, sends one chat message through
// functions/api/chat.js and checks which tips reached the prompt. No network, no API key.
import assert from "node:assert/strict";

const KB = { facts: [
  { t: "People on the sub say Stussy hoodies run big, most size down one.", topic: "sizing", keys: ["stussy", "hoodie"], sub: "FashionReps", date: "2026-11-07", seen: 2, sup: 2 },
  { t: "Remove shoe boxes before shipping a sneaker haul to save weight.", topic: "shipping", keys: ["sneakers", "shoe box"], sub: "Repsneakers", date: "2026-11-07", seen: 1, sup: 2 },
  { t: "Check the moncler badge stitching and the down fill on QC photos.", topic: "qc", keys: ["moncler", "puffer"], sub: "QualityReps", date: "2026-11-01", seen: 1, sup: 1 },
  { t: "Several buyers say customs checks are stricter in December, so ship earlier.", topic: "seasonal", keys: ["customs"], sub: "FashionReps", date: "2026-11-07", seen: 1, sup: 2 },
] };

let lastBody = null;
globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
globalThis.fetch = async (input, init) => {
  const url = typeof input === "string" ? input : input.url;
  if (url.endsWith("/data/reddit_kb.json")) return new Response(JSON.stringify(KB), { headers: { "content-type": "application/json" } });
  if (url.includes("/data/") || url.includes("stats")) return new Response("{}", { status: 404 });
  if (url.startsWith("https://api.anthropic.com/")) {
    lastBody = JSON.parse(init.body);
    const ev = [
      { type: "message_start", message: {} },
      { type: "content_block_start", index: 0, content_block: { type: "text", text: "" } },
      { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "Size down one \u2014 they run big." } },
      { type: "content_block_stop", index: 0 },
      { type: "message_delta", delta: { stop_reason: "end_turn" } },
      { type: "message_stop" },
    ].map(e => "event: " + e.type + "\ndata: " + JSON.stringify(e) + "\n\n").join("");
    return new Response(ev, { headers: { "content-type": "text/event-stream" } });
  }
  return new Response("not stubbed: " + url, { status: 404 });
};

const chat = await import("../functions/api/chat.js");
const kbmod = await import("../functions/_lib/reddit_kb.js");

async function ask(text, ctx) {
  lastBody = null;
  const req = new Request("https://www.puroclassico.com/api/chat", { method: "POST",
    headers: { "content-type": "application/json", origin: "https://www.puroclassico.com", "user-agent": "Mozilla/5.0 (Macintosh) Safari/605" },
    body: JSON.stringify({ messages: [{ role: "user", content: text }], ctx: ctx || {}, v: 2 }) });
  const res = await chat.onRequestPost({ request: req, env: { ANTHROPIC_API_KEY: "test" }, waitUntil: () => {} });
  const out = await res.text();
  return { out, note: lastBody ? lastBody.system[1].text : "", system: lastBody ? lastBody.system[0].text : "" };
}

// 1. a sizing question about Stussy hoodies gets the Stussy tip, not the sneaker one
let r = await ask("do stussy hoodies fit true to size? i'm 180cm");
assert.match(r.note, /Community tips/);
assert.match(r.note, /\[r\/FashionReps, 2026-11\] People on the sub say Stussy hoodies run big/);
assert.doesNotMatch(r.note, /shoe boxes/);
assert.doesNotMatch(r.out, /\u2014/, "em dash reached the visitor");
assert.match(r.system, /Community tips/);
assert.ok(r.system.indexOf("\u2014") < 0, "em dash in the system prompt");

// 2. shipping question
r = await ask("how do i save on shipping for a sneaker haul");
assert.match(r.note, /shoe boxes/);

// 3. unrelated greeting: no tips block at all
r = await ask("hi");
assert.doesNotMatch(r.note, /Community tips/);

// 4. the find on screen adds its brand: "how do I check this" on a Moncler puffer gets the Moncler QC tip
const { P } = await import("../functions/_lib/site.js");
const mon = P.find(p => /moncler/i.test(p.brand || "") && /puffer|jacket|down/i.test(p.title || ""));
if (mon) {
  r = await ask("what should i look for in the qc photos of this?", { pid: String(mon.id) });
  assert.match(r.note, /moncler badge stitching/i);
}

// 5. picker unit checks: cap, no tips without a match
const many = Array.from({ length: 20 }, (_, i) => ({ t: "Sizing tip number " + i + " for stussy hoodies and tees", topic: "sizing", keys: ["stussy"], sub: "FashionReps", date: "2026-11-07" }));
const prepared = (await (async () => { kbmod; return many; })());
const picked = kbmod.pickTips(prepared.map(f => ({ ...f, keys: [" stussy "], hay: " " + f.t.toLowerCase() + " ", w: 1 })), "stussy size", "", "");
assert.ok(picked.length <= 3, "more than 3 tips of one topic: " + picked.length);
assert.equal(kbmod.pickTips([], "anything", "", "").length, 0);
assert.equal(kbmod.tipsNote([]), "");

console.log("reddit kb chat tests: ok" + (mon ? "" : " (no Moncler find for test 4)"));
