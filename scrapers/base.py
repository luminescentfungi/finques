"""
Abstract base class for all scrapers.
Every scraper MUST subclass BaseScraper and implement `search()`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from models import SearchParams, Listing
from utils import RateLimitedSession

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Base class for all Barcelona rental scrapers.

    Subclasses must implement:
        search(params: SearchParams) -> List[Listing]

    They may override:
        name       – short identifier used in Listing.source
        uses_js    – True when a headless browser is required
        _build_url – helper to construct the first search URL from SearchParams
    """

    name: str = "base"
    uses_js: bool = False       # set True for Playwright-based scrapers
    base_url: str = ""

    def __init__(self) -> None:
        self._http = RateLimitedSession()
        self._log = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    @abstractmethod
    def search(self, params: SearchParams) -> List[Listing]:
        """
        Execute a search with *params* and return a (possibly empty) list
        of normalised Listing objects.

        Implementations should:
        1. Build the initial search URL.
        2. Fetch and parse pages, respecting params.max_pages.
        3. Return results; never raise – log errors and return partial list.
        """
        ...

    # ------------------------------------------------------------------ #
    # Helpers available to subclasses
    # ------------------------------------------------------------------ #

    def _get_html(self, url: str, **kwargs) -> str:
        """Fetch *url* and return response text.  Returns '' on error."""
        import requests as _req
        try:
            resp = self._http.get(url, **kwargs)
            return resp.text
        except _req.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status == 404:
                self._log.debug("GET %s → 404 (end of pagination)", url)
            else:
                self._log.error("GET %s failed: %s", url, exc)
            return ""
        except Exception as exc:
            self._log.warning("GET %s failed: %s", url, exc)
            return ""

    def _fetch_heading(self, url: str) -> str:
        """
        Fetch *url* and return its h1/h2/h3/<title> text.
        Falls back to the URL slug if nothing useful is found.
        """
        from utils.parser import extract_heading
        from urllib.parse import urlparse
        import os
        html = self._get_html(url)
        heading = extract_heading(html)
        if heading:
            return heading
        # last resort: humanise the URL slug
        slug = os.path.basename(urlparse(url).path.rstrip("/"))
        return slug.replace("-", " ").replace("_", " ").title() if slug else url

    def _safe_listing(self, **kwargs) -> Listing:
        """Create a Listing, injecting this scraper's name as source."""
        kwargs.setdefault("source", self.name)
        return Listing(**kwargs)
