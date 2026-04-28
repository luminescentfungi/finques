"""
Scraper for habitabarcelona.com – WordPress / WP Real Estate agency site.

Strategy     : Static HTML (no JS needed).
Search URLs  : /property-status/alquilar-amueblado
               /property-status/alquilar-sin-muebles
Detail page  : h1.page-title         → title
               li.price span         → price  (e.g. <span>3,150</span> €)
               feature <li> elements → size / bedrooms / bathrooms
"""

from __future__ import annotations

import re
from typing import List

from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, absolute_url, attr

BASE = "https://habitabarcelona.com"

SEARCH_URLS = [
    f"{BASE}/property-status/alquilar-amueblado",
    f"{BASE}/property-status/alquilar-sin-muebles",
]


def _clean_title(text: str) -> str:
    """Strip \\n → ' | ', collapse spaces, trim."""
    if not text:
        return text
    text = text.strip()
    text = re.sub(r"\s*\n+\s*", " | ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip(" |").strip()


class HabitaBarcelonaScraper(PlaywrightBaseScraper):
    name = "habitabarcelona"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        seen_urls: set = set()
        listing_urls: list = []

        # Phase 1 – collect unique /property/ links from static search pages
        for search_url in SEARCH_URLS:
            html = self._get_html(search_url)
            if not html:
                continue
            bs = soup(html)
            for a in bs.find_all("a", href=re.compile(r"/property/")):
                url = absolute_url(attr(a, "href"), BASE)
                if url not in seen_urls:
                    seen_urls.add(url)
                    listing_urls.append(url)

        # Phase 2 – fetch each detail page (static) and parse
        for listing_url in listing_urls:
            detail_html = self._get_html(listing_url)
            if not detail_html:
                continue
            detail = soup(detail_html)

            # Title: <h1 class="page-title">…</h1>
            h1 = detail.find("h1", class_="page-title")
            if not h1:
                continue
            title = _clean_title(h1.get_text())

            # Price: <li class="price" …><span>3,150</span> €</li>
            li_price = detail.find("li", class_="price")
            if not li_price:
                continue
            price_span = li_price.find("span")
            price = parse_price(price_span.get_text(strip=True)) if price_span else None
            if not price or price == 0:
                continue

            if params.max_price and price > params.max_price:
                continue
            if params.min_price and price < params.min_price:
                continue

            # Feature <li> elements: "135 m2", "3 Habitaciones", "2 Baños"
            size_m2 = bedrooms = bathrooms = None
            for li in detail.find_all("li"):
                t = li.get_text(strip=True)
                if re.search(r"\d+\s*m[2²]", t, re.I) and size_m2 is None:
                    m = re.search(r"(\d+)\s*m[2²]", t, re.I)
                    size_m2 = float(m.group(1)) if m else None
                elif re.search(r"[Hh]abitacion", t) and bedrooms is None:
                    m = re.match(r"(\d+)", t)
                    bedrooms = int(m.group(1)) if m else None
                elif re.search(r"[Bb]a[ñn]", t) and bathrooms is None:
                    m = re.match(r"(\d+)", t)
                    bathrooms = int(m.group(1)) if m else None

            if params.min_rooms and bedrooms is not None and bedrooms < params.min_rooms:
                continue
            if params.min_size and size_m2 is not None and size_m2 < params.min_size:
                continue

            results.append(
                self._safe_listing(
                    url=listing_url,
                    title=title,
                    price=price,
                    size_m2=size_m2,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    city="Barcelona",
                )
            )

        return results
