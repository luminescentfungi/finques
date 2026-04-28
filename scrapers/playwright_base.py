"""
Base class for Playwright (headless browser) scrapers.

Subclass this instead of BaseScraper when the target site requires JavaScript
execution for rendering listings.

Usage
-----
class MyScraper(PlaywrightBaseScraper):
    name = "mysite"
    uses_js = True

    def search(self, params):
        with self._browser_page() as page:
            page.goto(self._build_url(params))
            page.wait_for_load_state("networkidle")
            html = page.content()
        return self._parse(html, params)
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from scrapers.base import BaseScraper
from config import PLAYWRIGHT_HEADLESS, PLAYWRIGHT_TIMEOUT

logger = logging.getLogger(__name__)


class PlaywrightBaseScraper(BaseScraper):
    """
    Extends BaseScraper with a helper context manager that opens a
    Playwright browser page and closes it cleanly on exit.

    Playwright must be installed:  playwright install chromium
    """

    uses_js = True

    @contextmanager
    def _browser_page(self) -> Generator:
        """Yield a Playwright Page inside a temporary browser context."""
        from playwright.sync_api import sync_playwright  # lazy import

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="es-ES",
            )
            page = ctx.new_page()
            page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
            try:
                yield page
            except Exception as exc:
                self._log.error("Playwright error: %s", exc)
            finally:
                ctx.close()
                browser.close()

    def _page_html(self, url: str, wait_selector: str | None = None) -> str:
        """
        Navigate to *url*, optionally wait for *wait_selector*, return HTML.
        If the selector never appears we still return whatever HTML was rendered.
        Returns '' only on hard navigation failure.
        """
        try:
            with self._browser_page() as page:
                page.goto(url, wait_until="domcontentloaded")
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=PLAYWRIGHT_TIMEOUT)
                    except Exception:
                        # Selector didn't appear – still grab whatever is rendered
                        try:
                            page.wait_for_load_state("networkidle", timeout=5_000)
                        except Exception:
                            pass
                else:
                    try:
                        page.wait_for_load_state("networkidle", timeout=PLAYWRIGHT_TIMEOUT)
                    except Exception:
                        pass
                return page.content()
        except Exception as exc:
            self._log.error("_page_html(%s) failed: %s", url, exc)
            return ""

    def _fetch_batch(self, urls: list, wait_selector: str | None = None) -> dict:
        """
        Fetch multiple URLs in a **single** browser session (reuses the same tab).
        Returns a dict mapping url → html string.  Missing/failed URLs map to ''.
        """
        results: dict = {u: "" for u in urls}
        if not urls:
            return results
        try:
            with self._browser_page() as page:
                for url in urls:
                    try:
                        page.goto(url, wait_until="domcontentloaded")
                        if wait_selector:
                            try:
                                page.wait_for_selector(wait_selector, timeout=PLAYWRIGHT_TIMEOUT)
                            except Exception:
                                try:
                                    page.wait_for_load_state("networkidle", timeout=5_000)
                                except Exception:
                                    pass
                        else:
                            try:
                                page.wait_for_load_state("networkidle", timeout=10_000)
                            except Exception:
                                pass
                        results[url] = page.content()
                    except Exception as exc:
                        self._log.error("_fetch_batch(%s) failed: %s", url, exc)
        except Exception as exc:
            self._log.error("_fetch_batch browser session failed: %s", exc)
        return results
