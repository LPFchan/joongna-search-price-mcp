from __future__ import annotations

from urllib.parse import quote

import httpx


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
)


class JoongnaFetchError(RuntimeError):
    pass


class JoongnaClient:
    def __init__(
        self,
        *,
        base_url: str = "https://web.joongna.com",
        timeout_seconds: float = 20.0,
        user_agent: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": f"{self._base_url}/search-price",
            "User-Agent": user_agent or DEFAULT_USER_AGENT,
        }
        self._http = httpx.AsyncClient(
            follow_redirects=True,
            headers=self._headers,
            http2=True,
            timeout=timeout_seconds,
        )

    def build_search_url(self, search_word: str) -> str:
        quoted = quote(search_word.strip(), safe="")
        return f"{self._base_url}/search-price/{quoted}"

    def build_search_keyword_url(self, keyword: str) -> str:
        quoted = quote(keyword.strip(), safe="")
        return f"{self._base_url}/search/{quoted}?excludeSoldOutProductYn=false"

    async def fetch_search_keyword_page(self, keyword: str) -> tuple[str, str]:
        if not keyword.strip():
            raise JoongnaFetchError("keyword must not be blank")

        url = self.build_search_keyword_url(keyword)
        response = await self._http.get(url)

        if response.status_code != 200:
            raise JoongnaFetchError(f"Joongna returned HTTP {response.status_code} for {url}")

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            raise JoongnaFetchError(
                f"Joongna returned unexpected content type {content_type!r} for {url}"
            )

        body = response.text
        lowered = body.lower()
        if "captcha" in lowered or ("cloudflare" in lowered and "__next_f.push" not in body):
            raise JoongnaFetchError("Joongna returned a suspected anti-bot page")

        return url, body

    async def fetch_search_page(self, search_word: str) -> tuple[str, str]:
        if not search_word.strip():
            raise JoongnaFetchError("search_word must not be blank")

        url = self.build_search_url(search_word)
        response = await self._http.get(url)

        if response.status_code != 200:
            raise JoongnaFetchError(f"Joongna returned HTTP {response.status_code} for {url}")

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            raise JoongnaFetchError(
                f"Joongna returned unexpected content type {content_type!r} for {url}"
            )

        body = response.text
        lowered = body.lower()
        if "captcha" in lowered or ("cloudflare" in lowered and "__next_f.push" not in body):
            raise JoongnaFetchError("Joongna returned a suspected anti-bot page")

        return url, body

    async def aclose(self) -> None:
        await self._http.aclose()
