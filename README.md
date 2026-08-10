# Joongna Search Price MCP

MCP server that fetches and parses Joongna's search-price page, exposing a `joongna_search_price` tool that returns average/highest/lowest price, BID and EXECUTION price history, and product listings with thumbnails and links. Configure via environment variables: `JOONGNA_AUTH_TOKEN` (comma-separated bearer tokens for `/mcp` auth), `JOONGNA_BASE_URL`, `JOONGNA_CACHE_TTL_SECONDS`, `JOONGNA_TIMEOUT_SECONDS`, `JOONGNA_USER_AGENT`, `JOONGNA_PUBLIC_BASE_URL`, `JOONGNA_ALLOWED_HOSTS`, and `JOONGNA_ALLOWED_ORIGINS`. Run with `docker compose up --build` or `python -m joongna_search_price_mcp.server`.

The HTTP endpoint uses the official MCP Python SDK v2 and supports the
`2026-07-28` stateless protocol via `server/discover`, with a stateless legacy
fallback for clients that still use `initialize`.
