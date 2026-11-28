# -*- coding: utf-8 -*-
"""
repsapi.pl QC photos (owner, 28 Nov 2026: "let's just use repsapi.pl"): a QC source next to Oopbuy and qualit.ly in
scripts/qc_bank.py. GET https://repsapi.pl/v1/qc?platform=<weidian|taobao|1688>&id=<item id>, "Authorization: Bearer
<REPSAPI_KEY>"; the answer has "batches" (one per QC run: date, photos[]) and "total_photos". Photo links are public and
never change (https://repsapi.pl/v1/photos/<token>.webp; ?w= sets the size; on Pro they carry ?c=... and come without
the repsapi.pl corner badge, so keep the whole link and add &w=). Free plan: 2,000 requests a day, 30 a minute.
Docs: https://repsapi.pl/docs/qc

Needs REPSAPI_KEY (GitHub secret; the key from repsapi.pl, "Get API key").

  python scripts/repsapi_qc.py <storefront> <item id>     one lookup, prints the photo links
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request

API = "https://repsapi.pl/v1/qc"
UA = {"User-Agent": "Mozilla/5.0 PuroClassicoQCBank/1.0", "Accept": "application/json"}
PAUSE = 2.2          # the free plan's 30 a minute


def ready():
    return bool(os.environ.get("REPSAPI_KEY"))


def sized(u, w=1080):
    """The photo link at width w, keeping any ?c=... (Pro: the badge-free link)."""
    p = urllib.parse.urlsplit(u)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if k != "w"] + [("w", str(w))]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), ""))


def photos(storefront, item_id, limit=12):
    """(status, total QC photos on record, [photo links, newest QC run first]). status 0: no answer."""
    url = API + "?" + urllib.parse.urlencode({"platform": storefront, "id": str(item_id)})
    req = urllib.request.Request(url, headers={**UA, "Authorization": "Bearer " + os.environ["REPSAPI_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=40) as r: d = json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, 0, []
    except Exception:
        return 0, 0, []
    runs = sorted(d.get("batches") or [], key=lambda b: str(b.get("date") or ""), reverse=True)
    out = []
    for b in runs:
        for u in b.get("photos") or []:
            if isinstance(u, str) and u.startswith("https://repsapi.pl/") and len(out) < limit: out.append(sized(u))
    return 200, int(d.get("total_photos") or len(out)), out


if __name__ == "__main__":
    if not ready(): sys.exit("REPSAPI_KEY is not set")
    st, n, ph = photos(sys.argv[1], sys.argv[2])
    print("status", st, "QC photos on record", n)
    for u in ph: print(u)
    time.sleep(0)
