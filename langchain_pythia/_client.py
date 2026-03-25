"""Internal HTTP client for fetching Pythia Oracle data."""

from datetime import datetime, timezone

import httpx

DATA_URL = "https://pythia.c3x-solutions.com/feed-status.json"
CACHE_TTL_SECONDS = 60

_cache: dict = {}


async def fetch_data() -> dict:
    """Fetch feed-status.json with 60s cache."""
    now = datetime.now(timezone.utc)
    cached = _cache.get("data")
    if cached and (now - cached["at"]).total_seconds() < CACHE_TTL_SECONDS:
        return cached["data"]

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(DATA_URL)
        resp.raise_for_status()
        data = resp.json()

    _cache["data"] = {"data": data, "at": now}
    return data


def fetch_data_sync() -> dict:
    """Synchronous version of fetch_data."""
    now = datetime.now(timezone.utc)
    cached = _cache.get("data")
    if cached and (now - cached["at"]).total_seconds() < CACHE_TTL_SECONDS:
        return cached["data"]

    with httpx.Client(timeout=15) as client:
        resp = client.get(DATA_URL)
        resp.raise_for_status()
        data = resp.json()

    _cache["data"] = {"data": data, "at": now}
    return data
