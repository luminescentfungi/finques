"""
Scraper for finquesmarba.com – rental listings (Playwright, two-phase).

Phase 1: collect listing URLs from the grid (li.grid-item span.property_url)
Phase 2: fetch each detail page for title (h1.page-title first text node)
         and price (div.price > span)
Listings with "local" in the title are discarded.

URL: https://www.finquesmarba.com/alquiler/
"""

from __future__ import annotations
import re
from typing import List
from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE   = "https://www.finquesmarba.com"
SEARCH = f"{BASE}/alquiler/"


def _clean_title(text: str) -> str:
    text = text.replace("\n", " | ")
    text = re.sub(r" \| $|^ \| ", "", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip(" |")


class FinquesMarbasScraper(PlaywrightBaseScraper):
    name = "finquesmarba"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        # ── Phase 1: collect listing URLs from all pages ──────────────────
        pending_urls: list[str] = []

        for page in range(1, params.max_pages + 1):
            url = SEARCH if page == 1 else f"{SEARCH}page/{page}/"
            html = self._page_html(url, wait_selector="#property_grid_holder")
            if not html:
                break

            bs = soup(html)
            # Each <li> has a hidden <div id="propertyNNN"> with <span class="property_url">
            spans = bs.select("span.property_url")
            if not spans:
                break

            before = len(pending_urls)
            for sp in spans:
                href = sp.get_text(strip=True)
                if href and href not in pending_urls:
                    pending_urls.append(href)
            if len(pending_urls) == before:
                break  # no new URLs on this page

        if not pending_urls:
            return []

        # ── Phase 2: fetch detail pages ───────────────────────────────────
        pages = self._fetch_batch(pending_urls, wait_selector="h1.page-title, div.price")
        results: List[Listing] = []

        for listing_url, detail_html in pages.items():
            if not detail_html:
                continue

            bs = soup(detail_html)

            # Title: first text node of h1.page-title (before inner tags)
            h1 = bs.select_one("h1.page-title")
            if not h1:
                continue
            title_parts = [c for c in h1.children
                           if hasattr(c, "name") is False and str(c).strip()]
            title = _clean_title(str(title_parts[0])) if title_parts else ""
            if not title:
                title = _clean_title(h1.get_text(" ", strip=True))
            # Discard commercial premises
            if re.search(r"local", title, re.IGNORECASE):
                continue

            # Price: <div class="price"><span>PRICE</span><strong>€</strong></div>
            price_div = bs.select_one("div.price")
            price = None
            if price_div:
                price_span = price_div.find("span")
                if price_span:
                    raw_price = price_span.get_text(strip=True)
                    m = re.search(r"([\d\.\,]+)", raw_price)
                    if m:
                        price = parse_price(m.group(1))

            if not price:
                continue
            if params.min_price and price < params.min_price:
                continue
            if params.max_price and price > params.max_price:
                continue

            # Size / beds / baths from amenities block
            amenities = bs.select_one("div.property-amenities")
            size_m2 = bedrooms = bathrooms = None
            if amenities:
                raw_a = amenities.get_text(" ", strip=True)
                m = re.search(r"([\d\.]+)m", raw_a)
                if m:
                    size_m2 = parse_float(m.group(1))
                m = re.search(r"(\d+)\s*Hab", raw_a, re.IGNORECASE)
                if m:
                    bedrooms = parse_int(m.group(1))
                m = re.search(r"(\d+)\s*Ba", raw_a, re.IGNORECASE)
                if m:
                    bathrooms = parse_int(m.group(1))

            results.append(
                self._safe_listing(
                    url=listing_url, title=title, price=price,
                    size_m2=size_m2, bedrooms=bedrooms, bathrooms=bathrooms,
                    city="Barcelona",
                )
            )

        return results
