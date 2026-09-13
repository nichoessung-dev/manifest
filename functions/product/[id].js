// Real crawlable product URLs: /product/<id>
// Serves the SPA but injects product-specific <title>, meta, canonical, OG and Product JSON-LD
// so each product is an indexable page with unique metadata. The client opens the product on load.
const SITE = "https://puroclassico.com";

function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;"); }

export async function onRequestGet(context){
  const { request, params } = context;
  const id = decodeURIComponent(params.id || "");
  const origin = new URL(request.url).origin;
  let html;
  try { html = await (await fetch(origin + "/index.html")).text(); }
  catch(e){ return Response.redirect(SITE + "/#p/" + encodeURIComponent(id), 302); }

  let data = {};
  try { data = await (await fetch(origin + "/products.json")).json(); } catch(e){}
  const p = data[id];

  if (p) {
    const url = SITE + "/product/" + encodeURIComponent(id);
    const title = esc(p.title + (p.brand ? " — " + p.brand : "") + " | Puro Classico");
    const desc = esc((p.title || "Find") + (p.brand ? " by " + p.brand : "") + " — quality-checked, sourced from " + (p.seller || "China") + ". Real QC photos and one-tap agent buy links via Puro Classico.");
    const img = esc(p.img || (SITE + "/og.png"));

    html = html.replace(/<title>[\s\S]*?<\/title>/, "<title>" + title + "</title>");
    html = html.replace(/<meta name="description" content="[^"]*">/, '<meta name="description" content="' + desc + '">');
    html = html.replace('<link rel="canonical" href="https://puroclassico.com/">', '<link rel="canonical" href="' + url + '">');
    html = html.replace('<meta property="og:type" content="website">', '<meta property="og:type" content="product">');
    html = html.replace(/<meta property="og:title" content="[^"]*">/, '<meta property="og:title" content="' + title + '">');
    html = html.replace(/<meta property="og:description" content="[^"]*">/, '<meta property="og:description" content="' + desc + '">');
    html = html.replace('<meta property="og:url" content="https://puroclassico.com/">', '<meta property="og:url" content="' + url + '">');
    html = html.replace('<meta property="og:image" content="https://puroclassico.com/og.png">', '<meta property="og:image" content="' + img + '">');
    html = html.replace(/<meta name="twitter:image" content="[^"]*">/, '<meta name="twitter:image" content="' + img + '">');

    const usd = parseFloat(p.usd || 0) || 0;
    const ld = {
      "@context":"https://schema.org","@type":"Product",
      "name": p.title, "image": p.img ? [p.img] : undefined,
      "brand": p.brand ? {"@type":"Brand","name":p.brand} : undefined,
      "category": p.cat || undefined,
      "offers": {"@type":"Offer","price": usd.toFixed(2), "priceCurrency":"USD","availability":"https://schema.org/InStock","url": url}
    };
    html = html.replace("</head>", '<script type="application/ld+json">' + JSON.stringify(ld) + "</script></head>");
  }
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300, s-maxage=3600" } });
}
