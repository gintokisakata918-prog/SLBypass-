from pydantic import BaseModel


class ResolveResponse(BaseModel):
    status: str
    url: str
    destination: str | None = None
    hops: list[str] = []
    elapsed_ms: int = 0
    detail: str | None = None
    cached: bool = False
