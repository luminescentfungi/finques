"""
Shared HTTP utilities: session factory, retry logic, rate limiting.
"""

from __future__ import annotations

import time
import logging
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from config import DEFAULT_HEADERS, REQUEST_TIMEOUT, REQUEST_DELAY, MAX_RETRIES

logger = logging.getLogger(__name__)


def make_session(extra_headers: Optional[dict] = None) -> requests.Session:
    """Return a requests.Session pre-loaded with default headers."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if extra_headers:
        session.headers.update(extra_headers)
    return session


class RateLimitedSession:
    """
    Thin wrapper around requests.Session that inserts a delay between
    consecutive requests to the same host.
    """

    def __init__(self, delay: float = REQUEST_DELAY, extra_headers: Optional[dict] = None):
        self._session = make_session(extra_headers)
        self._delay = delay
        self._last_request: float = 0.0

    def _wait(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)

    def get(self, url: str, **kwargs) -> requests.Response:
        self._wait()
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        try:
            resp = self._session.get(url, **kwargs)
        except requests.exceptions.SSLError:
            # Retry without SSL verification for sites with bad cert chains
            logger.warning("SSL error for %s – retrying without verification", url)
            kwargs["verify"] = False
            resp = self._session.get(url, **kwargs)
        except requests.exceptions.Timeout:
            logger.warning("Timeout for %s (%.0fs)", url, kwargs.get("timeout", REQUEST_TIMEOUT))
            raise
        except requests.exceptions.ConnectionError as exc:
            logger.warning("Connection error for %s: %s", url, exc)
            raise
        self._last_request = time.time()
        resp.raise_for_status()
        return resp

    def post(self, url: str, **kwargs) -> requests.Response:
        self._wait()
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        try:
            resp = self._session.post(url, **kwargs)
        except requests.exceptions.SSLError:
            logger.warning("SSL error for %s – retrying without verification", url)
            kwargs["verify"] = False
            resp = self._session.post(url, **kwargs)
        self._last_request = time.time()
        resp.raise_for_status()
        return resp
