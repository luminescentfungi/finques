"""
Scraper for myspotbarcelona.com – Rent listings (JS-rendered).

URL pattern  : https://www.myspotbarcelona.com/properties?location=Barcelona&operation=Rent
Filters      : location, operation, min_price, max_price, bedrooms
Pagination   : &page=N
Strategy     : Playwright.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE   = "https://www.myspotbarcelona.com"
SEARCH = f"{BASE}/properties"


class MySpotBarcelonaScraper(PlaywrightBaseScraper):
    name = "myspotbarcelona"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []

        for page in range(1, params.max_pages + 1):
            url = f"{SEARCH}?location={params.city}&operation=Rent&page={page}"
            if params.max_price:
                url += f"&max_price={params.max_price}"
            if params.min_price:
                url += f"&min_price={params.min_price}"
            if params.min_rooms:
                url += f"&bedrooms={params.min_rooms}"

            html = self._page_html(url, wait_selector="[class*='property'], [class*='card']")
            if not html:
                break

            bs = soup(html)
            cards = bs.find_all("a", href=re.compile(r"/properties/|/property/"))
            if not cards:
                break

            found_any = False
            for card in cards:
                href = attr(card, "href")
                listing_url = absolute_url(href, BASE)
                raw = text_of(card)

                price_match = re.search(r"([\d\.,]+)\s*€", raw)
                price = parse_price(price_match.group(1)) if price_match else None

                size_match = re.search(r"(\d+)\s*m²?", raw, re.IGNORECASE)
                size_m2 = parse_float(size_match.group(1)) if size_match else None

                bed_match = re.search(r"(\d+)\s*[Hh]ab|(\d+)\s*[Bb]ed", raw)
                bedrooms = parse_int((bed_match.group(1) or bed_match.group(2))) if bed_match else None

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
                        city=params.city,
                    )
                )
                found_any = True

            if not found_any:
                break

        return results
