from __future__ import annotations

import contextlib
import json
import os
from typing import Annotated
from urllib.parse import parse_qs, urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.responses import JSONResponse
import uvicorn

from joongna_search_price_mcp.client import DEFAULT_USER_AGENT, JoongnaClient
from joongna_search_price_mcp.service import JoongnaPriceService
from joongna_search_price_mcp.models import JoongnaSearchPriceResult


_service: JoongnaPriceService | None = None


def _split_csv_env(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _build_transport_security() -> TransportSecuritySettings:
    allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    allowed_origins = [
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
        "https://127.0.0.1:*",
        "https://localhost:*",
        "https://[::1]:*",
    ]

    public_base_url = os.environ.get("JOONGNA_PUBLIC_BASE_URL")
    if public_base_url:
        parsed = urlparse(public_base_url)
        if parsed.scheme and parsed.netloc:
            allowed_origins.append(f"{parsed.scheme}://{parsed.netloc}")
            if parsed.hostname:
                allowed_hosts.append(parsed.netloc)
                if parsed.port is None:
                    allowed_hosts.append(parsed.hostname)

    allowed_hosts.extend(_split_csv_env(os.environ.get("JOONGNA_ALLOWED_HOSTS")))
    allowed_origins.extend(_split_csv_env(os.environ.get("JOONGNA_ALLOWED_ORIGINS")))

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_dedupe(allowed_hosts),
        allowed_origins=_dedupe(allowed_origins),
    )


class _AuthMiddleware:
    def __init__(self, app, tokens: list[str] | None):
        self.app = app
        self.tokens = set(tokens) if tokens else None

    async def __call__(self, scope, receive, send):
        if self.tokens is None:
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/healthz":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()

        if auth_header.startswith("Bearer ") and auth_header[7:] in self.tokens:
            await self.app(scope, receive, send)
            return

        token_values = parse_qs(scope.get("query_string", b"").decode()).get("token", [])
        if self.tokens & set(token_values):
            await self.app(scope, receive, send)
            return

        body = json.dumps({"error": "Unauthorized"}).encode()
        await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": body})


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
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", "8000")),
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    lifespan=mcp_lifespan,
    transport_security=_build_transport_security(),
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


_raw_tokens = os.environ.get("JOONGNA_AUTH_TOKEN")
_auth_tokens: list[str] | None = None
if _raw_tokens:
    _auth_tokens = [t.strip() for t in _raw_tokens.split(",") if t.strip()]

app = _AuthMiddleware(
    mcp.streamable_http_app(),
    _auth_tokens,
)


def main() -> None:
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
