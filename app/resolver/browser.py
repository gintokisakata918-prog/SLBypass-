"""Real Chromium fallback. vplink ka VPN gate + countdown isi se clear hota hai."""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from ..config import settings
from ..utils import host_of
from .extract import choose_destination, extract_candidates, is_shortener_host

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

SELECTORS = [
    "#continue", "#btn-main", "#getlink", "#get-link", "#btn-continue",
    "a#continue", "button#continue", "a.btn.btn-primary", "button.btn-primary",
    "a.btn-success", "button.btn-success", ".get-link", ".btn-continue",
]
TEXTS = ["continue", "click here", "get link", "getlink", "proceed",
         "download now", "verify", "next", "click to continue"]


async def _click_any(page) -> bool:
    for sel in SELECTORS:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                await loc.click(timeout=4000, force=True)
                return True
        except Exception:
            continue
    for txt in TEXTS:
        try:
            loc = page.get_by_text(txt, exact=False).first
            if await loc.count() and await loc.is_visible():
                await loc.click(timeout=4000, force=True)
                return True
        except Exception:
            continue
    return False


def _same_page(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.netloc, pa.path.rstrip("/")) == (pb.netloc, pb.path.rstrip("/"))


async def browser_resolve(url: str, timeout_ms: int | None = None) -> str | None:
    from playwright.async_api import async_playwright

    timeout_ms = timeout_ms or settings.browser_timeout_ms
    origin_host = host_of(url)

    async with async_playwright() as pw:
        launch_args = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage",
                     "--disable-blink-features=AutomationControlled"],
        }
        if settings.proxy_url:
            launch_args["proxy"] = {"server": settings.proxy_url}
        browser = await pw.chromium.launch(**launch_args)
        ctx = await browser.new_context(
            user_agent=UA, locale="en-US", timezone_id="Asia/Kolkata",
            viewport={"width": 1366, "height": 768},
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = await ctx.new_page()
        popups: list = []
        ctx.on("page", lambda p: popups.append(p))

        dest: str | None = None
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
            for _ in range(12):
                if asyncio.get_running_loop().time() > deadline:
                    break
                await page.wait_for_timeout(1500)

                cur = page.url
                if cur != url and not _same_page(cur, url) and not is_shortener_host(host_of(cur)):
                    dest = cur
                    break

                for p in popups:
                    try:
                        pu = p.url
                        if pu.startswith("http") and not is_shortener_host(host_of(pu)):
                            dest = pu
                            break
                    except Exception:
                        pass
                if dest:
                    break

                anchors = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                best = choose_destination(list(anchors or []), origin_host, url)
                if best:
                    dest = best
                    break

                html = await page.content()
                best = choose_destination(extract_candidates(html, page.url), origin_host, url)
                if best:
                    dest = best
                    break

                await _click_any(page)
        finally:
            await ctx.close()
            await browser.close()
        return dest
