# Joongna Search Price MCP

MCP server that fetches Joongna's `search-price` page over plain HTTP, parses the server-rendered summary and hydrated pricing data, and returns structured results for LLMs.

Current scope:

- direct HTTP fetches to `https://web.joongna.com/search-price/{searchWord}`
- summary parsing for average, highest, and lowest price
- hydrated `BID` and `EXECUTION` price history parsing
- listing extraction with thumbnail and product link
- streamable HTTP MCP endpoint at `/mcp`
- health endpoint at `/healthz`

Not implemented yet:

- browser fallback with `camofox-browser`
- authentication for the public MCP endpoint
- persistent cache shared across replicas

## Tool

`joongna_search_price`

Inputs:

- `query`: user query or product/device name
- `search_word`: optional explicit Joongna search term override
- `max_listings`: cap returned listings per dataset, default `10`
- `force_refresh`: bypass the in-memory cache

Example queries that should normalize well:

- `how much does used iPhone 13 mini go these days?`
- `iPhone 13 mini 128GB`
- `아이폰 13 미니`

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
python -m joongna_search_price_mcp.server
```

Endpoints:

- `http://127.0.0.1:8000/healthz`
- `http://127.0.0.1:8000/mcp`

## Docker

Build and run:

```bash
docker build -t joongna-search-price-mcp .
docker run --rm -p 8000:8000 joongna-search-price-mcp
```

Or with Compose:

```bash
docker compose up --build
```

## Configuration

Environment variables:

- `HOST` - default `0.0.0.0`
- `PORT` - default `8000`
- `JOONGNA_BASE_URL` - default `https://web.joongna.com`
- `JOONGNA_TIMEOUT_SECONDS` - default `20`
- `JOONGNA_CACHE_TTL_SECONDS` - default `300`
- `JOONGNA_USER_AGENT` - optional browser-like user agent override
- `JOONGNA_PUBLIC_BASE_URL` - public HTTPS URL for this MCP server, for example `https://joongna.lost.plus`
- `JOONGNA_ALLOWED_HOSTS` - optional comma-separated extra allowed Host headers for MCP transport security
- `JOONGNA_ALLOWED_ORIGINS` - optional comma-separated extra allowed Origin values for MCP transport security

`JOONGNA_PUBLIC_BASE_URL` is the easiest way to make FastMCP accept your public hostname when the app sits behind `cloudflared`, nginx, or another reverse proxy.

## Cloudflared

Recommended deployment pattern:

- run this app container on the OCI host
- run `cloudflared` separately, not inside this app container
- point the tunnel hostname at the local app port

Example tunnel config:

```yaml
tunnel: <tunnel-id>
credentials-file: /etc/cloudflared/<tunnel-id>.json

ingress:
  - hostname: joongna.lost.plus
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Set the app environment so MCP Host header validation accepts the tunneled hostname:

```bash
export JOONGNA_PUBLIC_BASE_URL="https://joongna.lost.plus"
```

If you prefer explicit overrides instead of `JOONGNA_PUBLIC_BASE_URL`:

```bash
export JOONGNA_ALLOWED_HOSTS="joongna.lost.plus"
export JOONGNA_ALLOWED_ORIGINS="https://joongna.lost.plus"
```

## Deployment Notes

- Expose `/mcp` through your reverse proxy.
- Keep a small cache TTL to reduce repeated fetches and bot scrutiny.
- If Joongna starts returning degraded HTML or blocking requests, add a browser fallback container and keep it behind a feature flag instead of switching the whole stack to browser-first.
