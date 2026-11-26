# -*- coding: utf-8 -*-
"""
Tracked email links (Email v2, 26 Nov 2026), the Python half of functions/e/[[path]].js.

  sid = new_send_id()                                  # a UUIDv7: the send time is inside the id
  url = track(sid, "welcome", "coupon", "https://www.puroclassico.com/go/mycnbox?k=invite&p=email-welcome")
  pix = pixel(sid, "welcome")                          # the open pixel URL (only for streams that use it)

The link is https://www.puroclassico.com/e/<sid22>/<campaign>/<link>?u=<destination>&h=<signature>, where the signature
is the first 16 base64url characters of HMAC-SHA256 with the key "e1:" + UNSUB_SECRET over "sid|campaign|link|dest".
Campaign and link are slugs: lowercase letters, digits and hyphens, at most 32 characters.
"""
import base64, hashlib, hmac, os, re, secrets, time, urllib.parse, uuid

SITE = os.environ.get("SITE_URL", "https://www.puroclassico.com").rstrip("/")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def _secret():
    s = os.environ.get("UNSUB_SECRET", "")
    if not s: raise RuntimeError("UNSUB_SECRET is not set: tracked links cannot be signed")
    return s


def b64u(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def new_send_id():
    """A UUIDv7 (RFC 9562): 48 bits of Unix time in ms, version 7, then random bits."""
    ms = int(time.time() * 1000)
    r = bytearray(secrets.token_bytes(10))
    b = ms.to_bytes(6, "big") + bytes([0x70 | (r[0] & 0x0F), r[1], 0x80 | (r[2] & 0x3F)]) + bytes(r[3:10])
    return uuid.UUID(bytes=bytes(b))


def sid22(send_id):
    return b64u(send_id.bytes)


def sign(sid, campaign, link, dest):
    msg = "%s|%s|%s|%s" % (sid, campaign, link, dest)
    return b64u(hmac.new(("e1:" + _secret()).encode(), msg.encode(), hashlib.sha256).digest())[:16]


def track(send_id, campaign, link, dest):
    """The tracked version of dest. campaign and link must be slugs; dest an https URL on our site or an agent."""
    if not (SLUG.match(campaign) and SLUG.match(link)): raise ValueError("bad slug: %r %r" % (campaign, link))
    sid = sid22(send_id) if isinstance(send_id, uuid.UUID) else send_id
    return "%s/e/%s/%s/%s?u=%s&h=%s" % (SITE, sid, campaign, link, urllib.parse.quote(dest, safe=""), sign(sid, campaign, link, dest))


def pixel(send_id, campaign):
    sid = sid22(send_id) if isinstance(send_id, uuid.UUID) else send_id
    return "%s/e/o/%s/%s.gif" % (SITE, sid, campaign)


if __name__ == "__main__":
    os.environ.setdefault("UNSUB_SECRET", "test-secret")
    s = new_send_id()
    print(s, sid22(s))
    print(track(s, "welcome", "coupon", "https://www.puroclassico.com/go/mycnbox?k=invite&p=email-welcome"))
