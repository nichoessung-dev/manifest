# -*- coding: utf-8 -*-
"""List Postiz posts around now with their state and any error (for checking drafts).  python scripts/postiz_status.py [hours_back]"""
import json, os, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_short as P
h = float(sys.argv[1]) if len(sys.argv) > 1 else 3
now = datetime.now(timezone.utc); f = "%Y-%m-%dT%H:%M:%S.000Z"
ps = P.call("GET", "/posts?startDate=%s&endDate=%s" % ((now - timedelta(hours=h)).strftime(f), (now + timedelta(hours=2)).strftime(f))).get("posts", [])
for p in sorted(ps, key=lambda p: p.get("publishDate") or ""):
    it = p.get("integration") or {}
    print(p.get("publishDate"), it.get("name"), p.get("state"), (p.get("releaseURL") or ""), json.dumps({k: p.get(k) for k in ("error", "errorMessage", "intervalInDays") if p.get(k)})[:300])
print(len(ps), "posts")
