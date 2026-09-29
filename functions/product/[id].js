// /product/<id> — a fully server-rendered product page (H1, price, QC photos, agent links, related finds),
// so every find is a real, fast, indexable page. Finds without QC photos are noindex,follow.
// Unknown/removed ids get a real 404.
import { renderProduct } from "../_lib/pages.js";
import { notFound } from "../_lib/site.js";

export async function onRequestGet(context) {
  const { request, params } = context;
  const url = new URL(request.url);
  const id = decodeURIComponent(params.id || "");
  const res = await renderProduct(id, url.origin);
  return res || notFound(url.pathname);
}
