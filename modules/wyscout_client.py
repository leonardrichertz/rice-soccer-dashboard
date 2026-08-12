"""Thin HTTP client for the Wyscout API v3 (https://apirest.wyscout.com/v3).

Authentication is plain HTTP Basic Auth -- despite being called "client ID /
client secret", Wyscout has no OAuth2 token exchange. The client ID is the
Basic Auth username, the client secret is the password.

Throttled to stay under the documented limit of 12 requests/second per API
key, and retries with backoff on 429 (Too Many Requests).
"""
import os
import time
from functools import lru_cache

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://apirest.wyscout.com/v3"
MAX_REQUESTS_PER_SECOND = 12
_MIN_INTERVAL = 1.0 / MAX_REQUESTS_PER_SECOND

_last_request_at = 0.0


@lru_cache(maxsize=1)
def _get_credentials():
    return (os.environ["WYSCOUT_CLIENT_ID"], os.environ["WYSCOUT_CLIENT_SECRET"])


def _throttle():
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


def get(path, params=None, max_retries=5):
    """GET a Wyscout API path (e.g. "/competitions/{id}/seasons") and return
    the parsed JSON body. Retries with exponential backoff on 429."""
    client_id, client_secret = _get_credentials()
    url = f"{BASE_URL}{path}"

    for attempt in range(max_retries):
        _throttle()
        resp = requests.get(url, params=params, auth=(client_id, client_secret), timeout=30)

        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue

        resp.raise_for_status()
        return resp.json()

    raise RuntimeError(f"Wyscout API rate limit exceeded after {max_retries} retries: {url}")


def get_all_pages(path, list_key, params=None, page_size=100):
    """GET a paginated Wyscout list endpoint (e.g. /seasons/{id}/players),
    collecting every page's `list_key` array into one list. Some of these
    endpoints silently cap at ~20 results per page by default (250 players
    returned as just the first 20) -- always paginate explicitly rather than
    trusting a single call to return everything."""
    params = dict(params or {})
    params["limit"] = page_size
    page = 1
    all_items = []

    while True:
        params["page"] = page
        data = get(path, params=params)
        items = data.get(list_key, [])
        all_items.extend(items)

        meta = data.get("meta") or {}
        page_count = meta.get("page_count", 1)
        if page >= page_count or not items:
            break
        page += 1

    return all_items
