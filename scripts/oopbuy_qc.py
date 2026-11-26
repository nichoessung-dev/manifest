# -*- coding: utf-8 -*-
"""
Oopbuy QC photos (26 Nov 2026, owner sent Oopbuy's "OpenAPI External Interface Documentation"): a second QC source next
to qualit.ly, with no monthly quota in the doc. POST https://pointshaul.com/qin/api/qc/by_spu_v3, body
{"encryptedData": AES-ECB-PKCS5(json), Base64 URL-safe, no padding}; the answer's encryptedData decrypts the same way to
{"code": 200, "data": [{channel, spuNo, skuNo, subject, checkPhotos: [...], ...}]}, at most 10 QC records.

Needs (from Oopbuy, GitHub secrets): OOPBUY_APP_ID, OOPBUY_AES_KEY (16 bytes), OOPBUY_SIGN_SECRET (sign = md5(appId +
timestamp + secret); when unset the AES key is tried). The invite code is ours (AGENT_REFS.oopbuy in index.html).

  python scripts/oopbuy_qc.py <storefront> <item id>     one lookup, prints the photo links
"""
import base64, hashlib, json, os, sys, time, urllib.request

URL = "https://pointshaul.com/qin/api/qc/by_spu_v3"
INVITE = "LHQC0OS8O"


def ready():
    return bool(os.environ.get("OOPBUY_APP_ID") and os.environ.get("OOPBUY_AES_KEY"))


def _cipher():
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    return Cipher(algorithms.AES(os.environ["OOPBUY_AES_KEY"].encode()), modes.ECB())


def _enc(text):
    from cryptography.hazmat.primitives import padding
    p = padding.PKCS7(128).padder(); data = p.update(text.encode()) + p.finalize()
    e = _cipher().encryptor(); raw = e.update(data) + e.finalize()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _dec(text):
    from cryptography.hazmat.primitives import padding
    raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    d = _cipher().decryptor(); data = d.update(raw) + d.finalize()
    u = padding.PKCS7(128).unpadder(); return (u.update(data) + u.finalize()).decode()


def lookup(spu):
    """(status, records). status: 200 found, 404 none, other: failed."""
    app = os.environ["OOPBUY_APP_ID"]; ts = int(time.time() * 1000)
    secret = os.environ.get("OOPBUY_SIGN_SECRET") or os.environ["OOPBUY_AES_KEY"]
    sign = hashlib.md5((app + str(ts) + secret).encode("utf-8")).hexdigest()
    body = json.dumps({"spuNo": str(spu), "inviteCode": INVITE, "appId": app, "timestamp": ts, "sign": sign}, separators=(",", ":"))
    req = urllib.request.Request(URL, data=json.dumps({"encryptedData": _enc(body)}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        return 0, str(e)[:120]
    if r.get("code") != 200 or not r.get("encryptedData"):
        return int(r.get("code") or 0), r.get("message")
    inner = json.loads(_dec(r["encryptedData"]))
    return int(inner.get("code") or 200), inner.get("data") or []


def photos(spu):
    """(status, photo links, newest first)."""
    st, recs = lookup(spu)
    if st != 200 or not isinstance(recs, list):
        return st, []
    out = []
    for rec in recs:
        for u in rec.get("checkPhotos") or []:
            if isinstance(u, str) and u.startswith("http") and u not in out:
                out.append(u)
    return 200, out


if __name__ == "__main__":
    if not ready():
        raise SystemExit("set OOPBUY_APP_ID and OOPBUY_AES_KEY first")
    st, ph = photos(sys.argv[-1])
    print(st, len(ph)); print("\n".join(ph[:12]))
