from __future__ import annotations

import contextlib
import os
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.responses import JSONResponse
import uvicorn

from joongna_search_price_mcp.client import DEFAULT_USER_AGENT, JoongnaClient
from joongna_search_price_mcp.service import JoongnaPriceService
from joongna_search_price_mcp.models import JoongnaSearchPriceResult


_service: JoongnaPriceService | None = None


@contextlib.asynccontextmanager
async def mcp_lifespan(_: FastMCP):
    global _service

    client = JoongnaClient(
        base_url=os.environ.get("JOONGNA_BASE_URL", "https://web.joongna.com"),
        timeout_seconds=float(os.environ.get("JOONGNA_TIMEOUT_SECONDS", "20")),
        user_agent=os.environ.get("JOONGNA_USER_AGENT", DEFAULT_USER_AGENT),
    )
    _service = JoongnaPriceService(
        client,
        cache_ttl_seconds=int(os.environ.get("JOONGNA_CACHE_TTL_SECONDS", "300")),
    )

    try:
        yield
    finally:
        if _service is not None:
            await _service.aclose()
        _service = None


mcp = FastMCP(
    "joongna-search-price",
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    lifespan=mcp_lifespan,
)


@mcp.tool()
async def joongna_search_price(
    query: Annotated[
        str,
        Field(description="Natural-language question or device name to search on Joongna"),
    ],
    search_word: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional explicit Joongna search term override, ideally in Korean",
        ),
    ] = None,
    max_listings: Annotated[
        int,
        Field(default=10, ge=1, le=20, description="Maximum listings to return per dataset"),
    ] = 10,
    force_refresh: Annotated[
        bool,
        Field(default=False, description="Bypass the in-memory cache for this request"),
    ] = False,
) -> JoongnaSearchPriceResult:
    """Query Joongna's used-market search-price page and return structured price data."""
    service = _require_service()
    return await service.search(
        query=query,
        search_word=search_word,
        max_listings=max_listings,
        force_refresh=force_refresh,
    )


def _require_service() -> JoongnaPriceService:
    if _service is None:
        raise RuntimeError("Joongna price service is not ready")
    return _service


async def index(_: object) -> JSONResponse:
    return JSONResponse(
        {
            "name": "joongna-search-price-mcp",
            "mcp_path": "/mcp",
            "healthz": "/healthz",
            "tool": "joongna_search_price",
        }
    )


async def healthz(_: object) -> JSONResponse:
    return JSONResponse({"ok": True})


@mcp.custom_route("/", methods=["GET"], include_in_schema=False)
async def root_route(request):
    del request
    return await index(None)


@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def health_route(request):
    del request
    return await healthz(None)


app = mcp.streamable_http_app()


def main() -> None:
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
