"""
Scraper for century21.es – Barcelona rentals (JS SPA).

URL pattern  : http://century21.es/alquilar?address_names=Barcelona&addresses=0701&page=1&ad_type=rent
Pagination   : &page=N
Filters      : address_names, addresses (location code), ad_type=rent
Strategy     : Playwright – Angular SPA.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE = "https://century21.es"


class Century21Scraper(PlaywrightBaseScraper):
    name = "century21"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []

        for page in range(1, params.max_pages + 1):
            url = (
                f"{BASE}/alquilar"
                f"?address_names={params.city}"
                f"&addresses=0701"
                f"&page={page}"
                f"&ad_type=rent"
            )
            if params.max_price:
                url += f"&max_price={params.max_price}"
            if params.min_price:
                url += f"&min_price={params.min_price}"
            if params.min_rooms:
                url += f"&min_rooms={params.min_rooms}"

            html = self._page_html(url, wait_selector="[class*='listing'], [class*='property']")
            if not html:
                break

            bs = soup(html)
            cards = bs.find_all("a", href=re.compile(r"/propiedad/|/inmueble/|/listing/"))
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

                bed_match = re.search(r"(\d+)\s*[Hh]ab", raw)
                bedrooms = parse_int(bed_match.group(1)) if bed_match else None

                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                title = lines[0] if lines else href

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
