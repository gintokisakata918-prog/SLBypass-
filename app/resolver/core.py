from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin

import httpx

from ..config import settings
from ..utils import BadURL, host_of, normalize_url
from .extract import choose_destination, extract_candidates, is_shortener_host

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class Result:
    status: str            # ok | protected | invalid | timeout | error
    url: str
    destination: str | None = None
    hops: list[str] | None = None
    elapsed_ms: int = 0
    detail: str | None = None

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "url": self.url,
            "destination": self.destination,
            "hops": self.hops or [],
            "elapsed_ms": self.elapsed_ms,
            "detail": self.detail,
        }


def _client() -> httpx.AsyncClient:
    kwargs = dict(
        timeout=settings.http_timeout_s,
        follow_redirects=True,
        headers=HEADERS,
        http2=True,
    )
    if settings.proxy_url:
        kwargs["proxy"] = settings.proxy_url
    return httpx.AsyncClient(**kwargs)


async def _api_attempt(client: httpx.AsyncClient, short_url: str, slug: str) -> str | None:
    """gplinks-family style XHR endpoint. Kabhi kabhi poora timer skip ho jata hai."""
    origin = f"{urlparse(short_url).scheme}://{urlparse(short_url).netloc}"
    for path in ("/links/go", "/api/links/go", "/go"):
        try:
            r = await client.post(
                urljoin(origin, path),
                data={"_id": slug, "slug": slug},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": short_url,
                    "Origin": origin,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                },
            )
        except httpx.HTTPError:
            continue
        if r.status_code >= 400 or not r.text.strip().startswith("{"):
            continue
        try:
            data = r.json()
        except ValueError:
            continue
        for key in ("url", "link", "destination", "redirect", "final"):
            v = data.get(key)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for v in data.values():
            if isinstance(v, str) and v.startswith("http"):
                return v
    return None


async def _http_hop(client: httpx.AsyncClient, url: str) -> str | None:
    r = await client.get(url, headers={"Referer": "https://www.google.com/"})
    final = str(r.url)
    best = choose_destination(extract_candidates(r.text, final), host_of(url), url)
    if best:
        return best
    if final != url and not is_shortener_host(host_of(final)):
        return final
    return None


async def resolve(raw_url: str, *, allow_browser: bool | None = None) -> Result:
    started = time.monotonic()
    try:
        url = normalize_url(raw_url)
    except BadURL as exc:
        return Result("invalid", raw_url, detail=str(exc))

    if allow_browser is None:
        allow_browser = settings.enable_browser

    hops: list[str] = [url]
    slug = urlparse(url).path.strip("/").split("/")[0]
    deadline = started + settings.total_budget_s
    current = url

    async with _client() as client:
        for _ in range(settings.max_hops):
            if time.monotonic() > deadline:
                return Result("timeout", url, hops=hops,
                              elapsed_ms=int((time.monotonic() - started) * 1000),
                              detail="budget exhausted")

            for attempt in (_api_attempt(client, current, slug), _http_hop(client, current)):
                try:
                    nxt = await attempt
                except httpx.HTTPError as exc:
                    nxt = None
                    last_error = repr(exc)
                if nxt:
                    break

            if nxt and nxt != current:
                if not is_shortener_host(host_of(nxt)):
                    return Result("ok", url, destination=nxt, hops=hops,
                                  elapsed_ms=int((time.monotonic() - started) * 1000))
                current = nxt
                slug = urlparse(current).path.strip("/").split("/")[0]
                hops.append(current)
                continue
            break

    if allow_browser:
        try:
            from .browser import browser_resolve
            dest = await browser_resolve(url)
        except Exception as exc:  # noqa: BLE001
            return Result("error", url, hops=hops,
                          elapsed_ms=int((time.monotonic() - started) * 1000),
                          detail=f"browser failed: {exc!r}")
        if dest:
            return Result("ok", url, destination=dest, hops=hops,
                          elapsed_ms=int((time.monotonic() - started) * 1000))
        return Result("protected", url, hops=hops,
                      elapsed_ms=int((time.monotonic() - started) * 1000),
                      detail="timer/VPN gate not cleared")

    return Result("protected", url, hops=hops,
                  elapsed_ms=int((time.monotonic() - started) * 1000),
                  detail="http layer found nothing, browser disabled")
