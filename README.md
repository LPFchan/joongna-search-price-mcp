# Joongna Search Price MCP

MCP server that fetches and parses Joongna's search and search-price pages. Both `joongna_search_price` and `joongna_search_keyword` return seller descriptions and full product-image links by default. The price tool also returns average/highest/lowest price and BID and EXECUTION price history. Configure via environment variables: `JOONGNA_AUTH_TOKEN` (optional comma-separated bearer tokens for `/mcp` auth), `JOONGNA_BASE_URL`, `JOONGNA_PRODUCT_API_BASE_URL`, `JOONGNA_CACHE_TTL_SECONDS`, `JOONGNA_TIMEOUT_SECONDS`, `JOONGNA_USER_AGENT`, `JOONGNA_PUBLIC_BASE_URL`, `JOONGNA_ALLOWED_HOSTS`, and `JOONGNA_ALLOWED_ORIGINS`. Run with `docker compose up --build` or `python -m joongna_search_price_mcp.server`.

The production Compose service leaves `JOONGNA_AUTH_TOKEN` unset because the public ChatGPT connector cannot use the server's fixed bearer-token authentication. The tools only read public Joongna listings. The service uses `restart: unless-stopped` so it returns after host and Docker restarts.

The HTTP endpoint uses the official MCP Python SDK v2 and supports the
`2026-07-28` stateless protocol via `server/discover`, with a stateless legacy
fallback for clients that still use `initialize`.
