/* Counts "Buy" clicks per agent (and the visitor's country, which the server adds). No cookies set, nothing personal sent:
   only which agent, which item, and which page. The link itself is never changed, so affiliate codes work as before. */
(function () {
  var AG = { "mycnbox.com": "mycnbox", "kakobuy.com": "kakobuy", "oopbuy.com": "oopbuy", "lovegobuy.com": "lovegobuy", "sugargoo.com": "sugargoo" };
  function agentOf(host) {
    host = (host || "").toLowerCase().replace(/^www\./, "");
    for (var d in AG) if (host === d || host.slice(-d.length - 1) === "." + d) return AG[d];
    return "";
  }
  function itemOf(href) {
    var u = href; try { u = decodeURIComponent(href); } catch (e) {}
    var m = u.match(/[?&]itemI[dD]=(\d{5,20})/) || u.match(/[?&]id=(\d{5,20})/) || u.match(/\/product\/[a-z0-9]+\/(\d{5,20})/i) || u.match(/(\d{8,20})/);
    return m ? m[1] : "";
  }
  function send(a) {
    var agent = agentOf(a.hostname); if (!agent) return;
    var href = a.href || "", u = href; try { u = decodeURIComponent(href); } catch (e) {}
    var pl = /1688\.com|mallType=1688|platform=1688/i.test(u) ? "1688" : /taobao|tmall|mallType=taobao|platform=taobao/i.test(u) ? "taobao" : /weidian/i.test(u) ? "weidian" : "";
    var body = JSON.stringify({ a: agent, i: itemOf(href), pl: pl, pg: location.pathname.slice(0, 120) });
    try {
      if (navigator.sendBeacon && navigator.sendBeacon("/api/click", new Blob([body], { type: "application/json" }))) return;
    } catch (e) {}
    try { fetch("/api/click", { method: "POST", body: body, headers: { "content-type": "application/json" }, keepalive: true }); } catch (e) {}
  }
  function onClick(ev) {
    if (ev.type === "auxclick" && ev.button !== 1) return;           // middle click opens a tab too
    var a = ev.target && ev.target.closest ? ev.target.closest("a[href]") : null;
    if (a) send(a);
  }
  document.addEventListener("click", onClick, true);
  document.addEventListener("auxclick", onClick, true);
})();
