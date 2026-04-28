"""
Scraper for fincaseva.com (JS-rendered – structure unknown at crawl time).

The site failed to return parseable static HTML.
This scraper uses Playwright to load the page and attempts a generic
card-link extraction pattern.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE = "https://www.fincaseva.com"


class FincasEvaScraper(PlaywrightBaseScraper):
    name = "fincaseva"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        html = self._page_html(BASE + "/", wait_selector="[class*='property'], [class*='listing'], article")
        if not html:
            return results

        bs = soup(html)
        for card in bs.find_all("a", href=re.compile(r"/(alquiler|inmueble|piso|propiedad)/")):
            href = attr(card, "href")
            listing_url = absolute_url(href, BASE)
            raw = text_of(card)

            price_match = re.search(r"([\d\.,]+)\s*€", raw)
            price = parse_price(price_match.group(1)) if price_match else None

            size_match = re.search(r"(\d+)\s*m²?", raw, re.IGNORECASE)
            size_m2 = parse_float(size_match.group(1)) if size_match else None

            bed_match = re.search(r"(\d+)\s*[Hh]ab", raw)
            bedrooms = parse_int(bed_match.group(1)) if bed_match else None

            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            title = lines[0] if lines else href

            if params.max_price and price and price > params.max_price:
                continue

            results.append(
                self._safe_listing(
                    url=listing_url,
                    title=title,
                    price=price,
                    size_m2=size_m2,
                    bedrooms=bedrooms,
                    city="Barcelona",
                )
            )

        return results
