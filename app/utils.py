import re
from urllib.parse import urlparse, urlunparse


class BadURL(ValueError):
    pass


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip().strip("<>\"'")
    if not raw:
        raise BadURL("empty url")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    p = urlparse(raw)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise BadURL(f"unsupported url: {raw}")
    if "." not in p.hostname:
        raise BadURL(f"bad host: {p.hostname}")
    return urlunparse(p._replace(fragment=""))


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower().lstrip(".")
