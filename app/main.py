import time

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .config import settings
from .models import ResolveResponse
from .resolver.core import resolve

app = FastAPI(title="vplink-bypass", version="1.0.0")
_cache: dict[str, tuple[float, ResolveResponse]] = {}


async def auth(x_api_key: str | None = Header(default=None)) -> None:
    if settings.api_token and x_api_key != settings.api_token:
        raise HTTPException(401, "bad api key")


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "browser": settings.enable_browser, "proxy": bool(settings.proxy_url)}


@app.get("/resolve", response_model=ResolveResponse, dependencies=[Depends(auth)])
async def resolve_endpoint(
    url: str = Query(..., min_length=6),
    force: bool = Query(False),
    allow_browser: bool = Query(True),
) -> ResolveResponse:
    key = url.strip()
    now = time.time()
    hit = _cache.get(key)
    if hit and not force and now - hit[0] < settings.cache_ttl_s:
        out = hit[1].model_copy(update={"cached": True})
        return out

    result = await resolve(key, allow_browser=allow_browser)
    resp = ResolveResponse(**result.as_dict())
    if resp.status == "ok":
        _cache[key] = (now, resp)
    return resp
