"""HTML se destination nikalne ke helpers. Koi network call nahi."""
from __future__ import annotations

import base64
import binascii
import re
from html import unescape
from urllib.parse import urljoin, urlparse

SHORTENER_HOSTS: set[str] = {
    "vplink.in", "www.vplink.in", "gplinks.co", "gplinks.in", "gplinks.com",
    "arolinks.com", "www.arolinks.com", "liteshort.in", "earn4link.in",
    "techmint.in", "www.techmint.in", "linkshortify.in", "shrinkforearn.in",
    "rocklinks.in", "jrlinks.in", "indianshortner.com", "4hi.in", "tnshort.net",
    "go.tnshort.net", "dekhe.click", "clk.wiki", "clk.kim", "clk.sh",
    "softurl.in", "droplink.co", "lksfy.in", "shrinkme.io", "shrinkme.ink",
    "shrinkearn.com", "srnky.com", "tpi.li", "cpmshort.com", "nowshort.com",
    "alpha-links.in", "shortingly.me", "urlsopen.com", "earnlink.io",
    "openurl.co", "mdiskshortner.link",
}

TRACKER_HOSTS: set[str] = {
    "google-analytics.com", "googletagmanager.com", "doubleclick.net",
    "cloudflareinsights.com", "connect.facebook.net", "google.com",
    "googleapis.com", "gstatic.com", "fonts.googleapis.com", "jsdelivr.net",
    "cdnjs.cloudflare.com", "unpkg.com", "bootstrapcdn.com", "jquery.com",
    "cloudflare.com", "challenges.cloudflare.com", "w3.org", "schema.org",
    "sitelock.in", "histats.com", "addthis.com", "sharethis.com",
}

_STATIC_EXT = (
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".map", ".mp4", ".webm", ".m3u8",
)

_PATTERNS = [
    re.compile(r"""window\.location(?:\.href)?\s*=\s*['"]([^'"]{4,2048})['"]""", re.I),
    re.compile(r"""location\.(?:replace|assign)\(\s*['"]([^'"]{4,2048})['"]""", re.I),
    re.compile(r"""<meta[^>]+http-equiv\s*=\s*['"]?refresh['"]?[^>]+content\s*=\s*['"][^'"]*?url\s*=\s*([^'"]+)['"]""", re.I),
    re.compile(r"""data-(?:url|href|link|redirect|destination)=['"]([^'"]{4,2048})['"]""", re.I),
    re.compile(r"""['"](?:url|link|destination|redirect|target|final|go|href)['"]\s*:\s*['"](https?://[^'"]{4,2048})['"]""", re.I),
    re.compile(r"""<iframe[^>]+src=['"](https?://[^'"]{4,2048})['"]""", re.I),
    re.compile(r"""href=['"](https?://[^'"]{4,2048})['"]""", re.I),
]

_ATOB = re.compile(r"""atob\(\s*['"]([A-Za-z0-9+/=]{16,})['"]\s*\)""")
_B64 = re.compile(r"""\b([A-Za-z0-9+/]{28,}={0,2})\b""")


def _host_matches(host: str, table: set[str]) -> bool:
    return host in table or any(host.endswith("." + h) for h in table)


def is_shortener_host(host: str) -> bool:
    return _host_matches((host or "").lower(), SHORTENER_HOSTS)


def _try_b64(token: str) -> str:
    try:
        pad = token + "=" * (-len(token) % 4)
        out = base64.b64decode(pad, validate=False).decode("utf-8", "ignore").strip()
    except (binascii.Error, ValueError):
        return ""
    return out if out.startswith(("http://", "https://")) else ""


def extract_candidates(html: str, base_url: str) -> list[str]:
    if not html:
        return []
    text = unescape(html).replace("\\u0026", "&").replace("\\/", "/")
    out: list[str] = []
    seen: set[str] = set()

    def push(raw: str) -> None:
        if not raw:
            return
        u = urljoin(base_url, raw.strip().replace("\\", ""))
        if u.startswith(("http://", "https://")) and u not in seen:
            seen.add(u)
            out.append(u)

    for pat in _PATTERNS:
        for m in pat.finditer(text):
            push(m.group(1))
    for m in _ATOB.finditer(text):
        push(_try_b64(m.group(1)))
    for m in _B64.finditer(text):
        push(_try_b64(m.group(1)))
    return out


def choose_destination(candidates: list[str], origin_host: str, short_url: str) -> str | None:
    origin_host = (origin_host or "").lower()
    for u in candidates:
        h = (urlparse(u).hostname or "").lower().lstrip(".")
        if not h or h == origin_host:
            continue
        if is_shortener_host(h) or _host_matches(h, TRACKER_HOSTS):
            continue
        if u.rstrip("/") == short_url.rstrip("/"):
            continue
        if urlparse(u).path.lower().endswith(_STATIC_EXT):
            continue
        return u
    return None
