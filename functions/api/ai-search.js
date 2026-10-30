/**
 * Cloudflare Pages Function: optional AI help for searches that found nothing on the site (round 4, 29 Oct 2026).
 * Route: POST /api/ai-search  {"q": "warm winter jacket"}  ->  200 {"terms":["puffer jacket"],"via":"embed","ai":true}
 * The page calls it only when its own search (in index.html, no network) has zero results. It answers with words from
 * the catalogue vocabulary (functions/_lib/search_vocab.js); the page shows a "Try ..." chip only if those words find
 * something. Needs a Workers AI binding named AI (Pages > Settings > Functions > Bindings); without it: 501 and the site
 * works as before. No keys in code, no logging of queries, no other network calls.
 *   1. embeddings (@cf/baai/bge-small-en-v1.5): the query against the vocabulary, best 3 with similarity >= MIN_SIM
 *   2. only if 1 found nothing: @cf/meta/llama-3.1-8b-instruct picks up to 4 terms from the 200 most common ones
 * Both race a 2 s timer. Answers are cached per query for a day (caches.default), vocabulary vectors for 30 days.
 */
import { VOCAB } from "../_lib/search_vocab.js";

const EMBED = "@cf/baai/bge-small-en-v1.5";
const LLM = "@cf/meta/llama-3.1-8b-instruct";
const MIN_SIM = 0.72;
const TIMEOUT = 2000;
const J = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };

function out(status, body) { return new Response(JSON.stringify(body), { status, headers: J }); }
function fold(s) {
  return String(s == null ? "" : s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/['’‘`´]/g, "").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}
const TERMS = VOCAB.map((v) => fold(v.t));
const SET = new Set(TERMS);
const TOP = VOCAB.map((v, i) => [TERMS[i], v.n]).sort((a, b) => b[1] - a[1]).slice(0, 200).map((x) => x[0]);
function hash(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(36); }
const VKEY = "https://ai-search.cache/vocab-" + hash(TERMS.join("|"));
let VEC = null;   /* vocabulary vectors, kept for the life of this isolate */

function vecs(r) { return (r && (r.data || (r.result && r.result.data))) || []; }
function cos(a, b) { let d = 0, x = 0, y = 0; for (let i = 0; i < a.length; i++) { d += a[i] * b[i]; x += a[i] * a[i]; y += b[i] * b[i]; } return x && y ? d / Math.sqrt(x * y) : 0; }
async function vocabVectors(env) {
  if (VEC) return VEC;
  const cache = typeof caches !== "undefined" ? caches.default : null;
  if (cache) { try { const hit = await cache.match(VKEY); if (hit) { VEC = await hit.json(); return VEC; } } catch (e) {} }
  const all = [];
  for (let i = 0; i < TERMS.length; i += 100) all.push(...vecs(await env.AI.run(EMBED, { text: TERMS.slice(i, i + 100) })));
  if (all.length !== TERMS.length) throw new Error("embed size");
  VEC = all;
  if (cache) { try { await cache.put(VKEY, new Response(JSON.stringify(all), { headers: { "content-type": "application/json", "cache-control": "public, max-age=2592000" } })); } catch (e) {} }
  return VEC;
}
async function byEmbedding(env, f) {
  const V = await vocabVectors(env);
  const q = vecs(await env.AI.run(EMBED, { text: [f] }))[0];
  if (!q) return [];
  return V.map((v, i) => [TERMS[i], cos(q, v)]).filter((x) => x[1] >= MIN_SIM).sort((a, b) => b[1] - a[1]).slice(0, 3).map((x) => x[0]);
}
async function byLlm(env, f) {
  const r = await env.AI.run(LLM, {
    max_tokens: 60, temperature: 0,
    messages: [
      { role: "system", content: "You map a shopping search to words from a clothing catalogue. Answer with JSON only, like {\"terms\":[\"puffer jacket\"]}: at most 4 items, each copied exactly from this list: " + TOP.join(", ") + ". If nothing fits, answer {\"terms\":[]}." },
      { role: "user", content: f }
    ]
  });
  const txt = String((r && (r.response || (r.result && r.result.response))) || "");
  const m = txt.match(/\{[\s\S]*\}/);
  let a = [];
  try { const j = JSON.parse(m ? m[0] : txt); a = Array.isArray(j.terms) ? j.terms : []; } catch (e) { return []; }
  const seen = new Set();
  return a.map(fold).filter((t) => t && SET.has(t) && !seen.has(t) && seen.add(t)).slice(0, 4);   /* only vocabulary words ever reach the page */
}

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "POST") return new Response(JSON.stringify({ terms: [], ai: false }), { status: 405, headers: { ...J, allow: "POST" } });
  if (!env || !env.AI || typeof env.AI.run !== "function") return out(501, { terms: [], ai: false });
  const url = new URL(request.url);
  let oh = "";
  try { oh = new URL(request.headers.get("origin") || "").host; } catch (e) {}
  if (!oh || oh !== url.host) return out(403, { terms: [], ai: true });
  const len = Number(request.headers.get("content-length") || 0);
  if (len > 512) return out(413, { terms: [], ai: true });
  const raw = await request.text();
  if (raw.length > 512) return out(413, { terms: [], ai: true });
  let q = "";
  try { q = JSON.parse(raw || "{}").q; } catch (e) {}
  const f = typeof q === "string" ? fold(q) : "";
  if (f.length < 2 || f.length > 80 || /^\d+$/.test(f.replace(/ /g, "")) || /https?:|www\.|\.(com|cn|net)\b/i.test(String(q))) return out(400, { terms: [], ai: true });

  const cache = typeof caches !== "undefined" ? caches.default : null;
  const qkey = "https://ai-search.cache/q/" + encodeURIComponent(f);
  if (cache) { try { const hit = await cache.match(qkey); if (hit) return out(200, await hit.json()); } catch (e) {} }

  let timer;
  const late = new Promise((res) => { timer = setTimeout(() => res({ terms: [], via: "timeout", ai: true }), TIMEOUT); });
  const work = (async () => {
    try {
      let t = await byEmbedding(env, f);
      if (t.length) return { terms: t, via: "embed", ai: true };
      t = await byLlm(env, f);
      return { terms: t, via: t.length ? "llm" : "none", ai: true };
    } catch (e) { return { terms: [], via: "error", ai: true }; }
  })();
  const save = async (body) => {
    if (!cache || body.via === "timeout" || body.via === "error") return;
    try { await cache.put(qkey, new Response(JSON.stringify(body), { headers: { "content-type": "application/json", "cache-control": "public, max-age=86400" } })); } catch (e) {}
  };
  // A fresh isolate embeds the whole vocabulary first (several AI calls), which can outlast TIMEOUT. waitUntil keeps that
  // work alive after the quick "timeout" answer, so the vectors and this answer are cached for the next visitor.
  if (typeof context.waitUntil === "function") context.waitUntil(work.then(save).catch(() => {}));
  const body = await Promise.race([work, late]);
  clearTimeout(timer);
  if (typeof context.waitUntil !== "function") await save(body);
  return out(200, body);
}
