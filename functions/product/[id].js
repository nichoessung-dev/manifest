// Real crawlable product URLs: /product/<id>
// Serves the SPA but injects product-specific <title>, meta, canonical, OG/Twitter and Product JSON-LD
// so each product is an indexable page with unique metadata. The client opens the product on load.
// Unknown/removed ids get a 404 + noindex instead of a duplicate of the homepage.
const SITE = "https://puroclassico.com";

function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;"); }

export async function onRequestGet(context){
  const { request, params } = context;
  const id = decodeURIComponent(params.id || "");
  const origin = new URL(request.url).origin;
  let html;
  try { html = await (await fetch(origin + "/index.html")).text(); }
  catch(e){ return Response.redirect(SITE + "/", 302); }

  let data = {};
  try { data = await (await fetch(origin + "/products.json")).json(); } catch(e){}
  const p = data[id];

  if (!p) {
    html = html.replace(/<meta name="robots" content="[^"]*">/, '<meta name="robots" content="noindex,follow">');
    return new Response(html, { status: 404, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300" } });
  }

  const url = SITE + "/product/" + encodeURIComponent(id);
  const usd = parseFloat(p.usd || 0) || 0;
  const rawTitle = (p.title || "Find") + " Rep — QC Photos & Buy on Any Agent · Puro Classico";
  const rawDesc = (p.title || "This find") + " rep" + (usd ? " for $" + Math.round(usd) : "") +
    " with real QC photos. Quality-checked, sourced from " + (p.seller || "China") +
    ". Open the listing on MyCNBox, KakoBuy, Oopbuy or any shopping agent.";
  const title = esc(rawTitle), desc = esc(rawDesc);
  const img = esc(p.img || (SITE + "/og.png"));

  html = html.replace(/<title>[\s\S]*?<\/title>/, "<title>" + title + "</title>");
  html = html.replace(/<meta name="description" content="[^"]*">/, '<meta name="description" content="' + desc + '">');
  html = html.replace('<link rel="canonical" href="https://puroclassico.com/">', '<link rel="canonical" href="' + url + '">');
  html = html.replace('<meta property="og:type" content="website">', '<meta property="og:type" content="product">');
  html = html.replace(/<meta property="og:title" content="[^"]*">/, '<meta property="og:title" content="' + title + '">');
  html = html.replace(/<meta property="og:description" content="[^"]*">/, '<meta property="og:description" content="' + desc + '">');
  html = html.replace('<meta property="og:url" content="https://puroclassico.com/">', '<meta property="og:url" content="' + url + '">');
  html = html.replace('<meta property="og:image" content="https://puroclassico.com/og.png">', '<meta property="og:image" content="' + img + '">');
  html = html.replace(/<meta name="twitter:title" content="[^"]*">/, '<meta name="twitter:title" content="' + title + '">');
  html = html.replace(/<meta name="twitter:description" content="[^"]*">/, '<meta name="twitter:description" content="' + desc + '">');
  html = html.replace(/<meta name="twitter:image" content="[^"]*">/, '<meta name="twitter:image" content="' + img + '">');

  const ld = {
    "@context":"https://schema.org","@type":"Product",
    "name": p.title, "sku": id, "url": url,
    "description": rawDesc,
    "image": p.img ? [p.img] : undefined,
    "brand": p.brand ? {"@type":"Brand","name":p.brand} : undefined,
    "category": p.cat || undefined,
    "offers": {"@type":"Offer","price": usd.toFixed(2), "priceCurrency":"USD","availability":"https://schema.org/InStock","url": url}
  };
  const crumbs = {
    "@context":"https://schema.org","@type":"BreadcrumbList",
    "itemListElement":[
      {"@type":"ListItem","position":1,"name":"Puro Classico","item":SITE + "/"},
      {"@type":"ListItem","position":2,"name":p.cat || "Finds","item":SITE + "/"},
      {"@type":"ListItem","position":3,"name":p.title || id,"item":url}
    ]
  };
  // "</" is escaped so product text can never close the script tag early.
  const safe = o => JSON.stringify(o).replace(/<\//g, "<\\/");
  const ldTag = '<script type="application/ld+json">' + safe(ld) + '</script>\n<script type="application/ld+json">' + safe(crumbs) + "</script>\n";
  // The document has no </head>; inject before the first <style> (always present in the head).
  if (html.indexOf("<style>") !== -1) html = html.replace("<style>", ldTag + "<style>");
  else html = ldTag + html;

  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300, s-maxage=3600" } });
}
