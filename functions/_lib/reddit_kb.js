// data/reddit_kb.json (scripts/reddit_kb.py, the weekly Reddit KB workflow): short community tips, in our own words, from
// public posts on rep subreddits. functions/api/chat.js adds the few that fit the visitor's question to the prompt.
// Read through the static assets, kept for 30 minutes per isolate. A missing or broken file means "no tips".
let _kb = [], _kbAt = 0;
export async function loadKb(env, origin) {
  if (_kbAt && Date.now() - _kbAt < 1800000) return _kb;
  _kbAt = Date.now();
  try {
    const req = new Request(origin + "/data/reddit_kb.json");
    const r = env && env.ASSETS ? await env.ASSETS.fetch(req) : await fetch(req);
    if (r.ok) { const j = await r.json(); if (j && Array.isArray(j.facts)) _kb = prepare(j.facts); }
  } catch (e) {}
  return _kb;
}

const fold = s => " " + String(s == null ? "" : s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
  .replace(/['’‘`]/g, "").replace(/[^\p{L}\p{N}]+/gu, " ").trim() + " ";
// Question words -> the topic a tip is filed under.
const TOPIC_WORDS = {
  sizing: ["size", "sizing", "fit", "fits", "tts", "true to size", "small", "large", "big", "tight", "loose", "measure", "measurements", "cm", "height", "tall", "weight", "kg", "lbs", "size up", "size down"],
  qc: ["qc", "gl", "rl", "green light", "red light", "flaw", "flaws", "check", "stitching", "logo", "quality", "photos", "return", "exchange", "legit", "good"],
  agents: ["agent", "agents", "warehouse", "mycnbox", "kakobuy", "cnfans", "superbuy", "sugargoo", "hoobuy", "oopbuy", "litbuy", "mulebuy", "allchinabuy", "acbuy", "joyabuy", "joyagoo", "orientdig", "lovegobuy", "itaobuy", "fishgoo", "basetao", "cssbuy", "gtbuy", "hubbuy", "loongbuy", "eastmallbuy", "cnshopper", "mycnbox"],
  shipping: ["ship", "shipping", "line", "lines", "parcel", "haul", "customs", "seized", "tax", "duty", "days", "weeks", "tracking", "ems", "dhl", "ups", "fedex", "eub", "rehearsal", "declare", "box", "boxes"],
  scams: ["scam", "scammed", "fake", "trust", "safe", "safety", "legit", "paypal", "refund", "dispute"],
  sellers: ["seller", "sellers", "store", "shop", "weidian", "taobao", "1688"],
  batches: ["batch", "batches", "version", "best version", "best batch", "pk", "ljr", "og"],
  materials: ["material", "fabric", "cotton", "leather", "wool", "down", "fill", "zipper", "hardware", "weight", "heavy"],
  seasonal: ["winter", "summer", "christmas", "black friday", "11 11", "singles day", "chinese new year", "cny", "holiday", "holidays", "sale"],
  ordering: ["order", "ordering", "buy", "how to", "pay", "payment", "first time", "beginner", "start"],
};
const TW = Object.fromEntries(Object.entries(TOPIC_WORDS).map(([k, ws]) => [k, ws.map(w => fold(w))]));

function prepare(facts) {
  return facts.filter(f => f && typeof f.t === "string" && f.t.length > 10).slice(0, 300).map(f => ({
    t: f.t.replace(/ ?\u2014 ?/g, ", "), topic: String(f.topic || "other"), sub: String(f.sub || "").replace(/[^A-Za-z0-9_]/g, ""),
    date: String(f.date || "").slice(0, 7), keys: (Array.isArray(f.keys) ? f.keys : []).map(k => fold(k)).filter(k => k.length > 3),
    hay: fold(f.t), w: (+f.sup || 1) + Math.min(+f.seen || 1, 4) / 2 }));
}

/**
 * The tips that fit: `text` is the visitor's latest message (plus the one before), `extra` the brand and category of
 * the find on screen. A tip needs a key match (brand, item, agent, line) or a topic match plus a word from its text.
 * Returns at most `n` tips, best first.
 */
export function pickTips(kb, text, extra, agentName, n = 6) {
  if (!kb || !kb.length) return [];
  const q = fold(text), x = fold(extra || ""), ag = agentName ? fold(agentName) : "";
  const topics = new Set();
  for (const [k, ws] of Object.entries(TW)) if (ws.some(w => q.includes(w))) topics.add(k);
  const qWords = new Set(q.trim().split(" ").filter(w => w.length > 3));
  const scored = [];
  for (const f of kb) {
    let s = 0;
    for (const k of f.keys) {
      if (q.includes(k)) s += 3;
      else if (x.includes(k)) s += 2;
      else if (ag && k === ag) s += 1;
    }
    if (topics.has(f.topic)) s += 2;
    let overlap = 0;
    for (const w of qWords) if (f.hay.includes(" " + w + " ")) overlap++;
    s += Math.min(overlap, 3) * 0.75;
    if (s < 2.5) continue;           // a topic match alone is not enough
    scored.push([s + f.w * 0.3, f]);
  }
  scored.sort((a, b) => b[0] - a[0]);
  const out = [], seenTopic = {};
  for (const [, f] of scored) {
    if ((seenTopic[f.topic] = (seenTopic[f.topic] || 0) + 1) > 3) continue;   // a mix, not six sizing tips
    out.push(f);
    if (out.length >= n) break;
  }
  return out;
}

// The prompt lines for the picked tips ("" when none).
export function tipsNote(tips) {
  if (!tips.length) return "";
  return ["Community tips (our own short summaries of public posts on rep subreddits; they can be out of date and are opinions, not facts):"]
    .concat(tips.map(f => "- [r/" + f.sub + ", " + f.date + "] " + f.t)).join("\n");
}
