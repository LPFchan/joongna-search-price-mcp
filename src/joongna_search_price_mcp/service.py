from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
import time

import asyncio

from joongna_search_price_mcp.client import JoongnaClient
from joongna_search_price_mcp.models import JoongnaSearchKeywordResult, JoongnaSearchPriceResult
from joongna_search_price_mcp.normalize import normalize_search_word
from joongna_search_price_mcp.parser import parse_search_keyword_page, parse_search_price_page


@dataclass(slots=True)
class _CacheEntry:
    expires_at: float
    result: JoongnaSearchPriceResult


@dataclass(slots=True)
class _KeywordCacheEntry:
    expires_at: float
    result: JoongnaSearchKeywordResult


_MAX_KEYWORD_RETRIES = 3
_KEYWORD_RETRY_DELAY = 2.0


class JoongnaPriceService:
    def __init__(self, client: JoongnaClient, *, cache_ttl_seconds: int = 300) -> None:
        self._client = client
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, _CacheEntry] = {}
        self._keyword_cache: dict[str, _KeywordCacheEntry] = {}
        self._lock = asyncio.Lock()

    async def search(
        self,
        *,
        query: str,
        search_word: str | None = None,
        max_listings: int = 10,
        force_refresh: bool = False,
    ) -> JoongnaSearchPriceResult:
        if max_listings < 1:
            raise ValueError("max_listings must be at least 1")

        effective_search_word = search_word.strip() if search_word else normalize_search_word(query)
        now = time.monotonic()

        async with self._lock:
            entry = self._cache.get(effective_search_word)
            if not force_refresh and entry and entry.expires_at > now:
                return self._limit_result(entry.result, max_listings=max_listings, from_cache=True)
            if entry and entry.expires_at <= now:
                self._cache.pop(effective_search_word, None)

        source_url, html = await self._client.fetch_search_page(effective_search_word)
        fetched_at = datetime.now(timezone.utc).isoformat()
        result = parse_search_price_page(
            html,
            query=query,
            search_word=effective_search_word,
            source_url=source_url,
            fetched_at=fetched_at,
        )

        async with self._lock:
            self._cache[effective_search_word] = _CacheEntry(
                expires_at=time.monotonic() + self._cache_ttl_seconds,
                result=result.model_copy(deep=True),
            )

        return self._limit_result(result, max_listings=max_listings, from_cache=False)

    async def search_keyword(
        self,
        *,
        query: str,
        search_word: str | None = None,
        max_listings: int = 20,
        force_refresh: bool = False,
    ) -> JoongnaSearchKeywordResult:
        if max_listings < 1:
            raise ValueError("max_listings must be at least 1")

        effective_search_word = search_word.strip() if search_word else normalize_search_word(query)
        now = time.monotonic()

        async with self._lock:
            entry = self._keyword_cache.get(effective_search_word)
            if not force_refresh and entry and entry.expires_at > now:
                return self._limit_keyword_result(entry.result, max_listings=max_listings, from_cache=True)
            if entry and entry.expires_at <= now:
                self._keyword_cache.pop(effective_search_word, None)

        for attempt in range(_MAX_KEYWORD_RETRIES):
            source_url, html = await self._client.fetch_search_keyword_page(effective_search_word)
            fetched_at = datetime.now(timezone.utc).isoformat()
            result = parse_search_keyword_page(
                html,
                query=query,
                search_word=effective_search_word,
                source_url=source_url,
                fetched_at=fetched_at,
            )

            if result.listings:
                break

            if attempt < _MAX_KEYWORD_RETRIES - 1:
                await asyncio.sleep(_KEYWORD_RETRY_DELAY)

        async with self._lock:
            self._keyword_cache[effective_search_word] = _KeywordCacheEntry(
                expires_at=time.monotonic() + self._cache_ttl_seconds,
                result=result.model_copy(deep=True),
            )

        return self._limit_keyword_result(result, max_listings=max_listings, from_cache=False)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _limit_keyword_result(
        self,
        result: JoongnaSearchKeywordResult,
        *,
        max_listings: int,
        from_cache: bool,
    ) -> JoongnaSearchKeywordResult:
        limited = result.model_copy(deep=True, update={"from_cache": from_cache})
        limited.listings = limited.listings[:max_listings]
        limited.total_count = len(limited.listings)
        return limited

    def _limit_result(
        self,
        result: JoongnaSearchPriceResult,
        *,
        max_listings: int,
        from_cache: bool,
    ) -> JoongnaSearchPriceResult:
        limited = result.model_copy(deep=True, update={"from_cache": from_cache})
        limited.available_listings = limited.available_listings[:max_listings]

        if limited.registered_price_history is not None:
            limited.registered_price_history.listings = limited.registered_price_history.listings[
                :max_listings
            ]

        if limited.sold_price_history is not None:
            limited.sold_price_history.listings = limited.sold_price_history.listings[:max_listings]

        return limited
