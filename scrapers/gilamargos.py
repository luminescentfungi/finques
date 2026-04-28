"""
Scraper for gilamargos.com – WP Houzez theme agency (JS-rendered).

URL pattern  : https://gilamargos.com/es?status=alquiler&...
               Form params: Estado (venta/alquiler), Barrio, Tipo, M2, Precio
Strategy     : Playwright – submit the search form programmatically.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE = "https://gilamargos.com"


class GilAmargósScraper(PlaywrightBaseScraper):
    name = "gilamargos"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []

        # Build a direct WP REST-like search URL (Houzez theme uses /en/properties)
        url = f"{BASE}/es/propiedades/?status=alquiler"
        if params.max_price:
            url += f"&max-price={params.max_price}"
        if params.min_price:
            url += f"&min-price={params.min_price}"
        if params.min_rooms:
            url += f"&bedrooms={params.min_rooms}"
        if params.district:
            url += f"&area={params.district.lower().replace(' ', '-')}"

        html = self._page_html(url, wait_selector="[class*='listing'], [class*='property']")
        if not html:
            return results

        bs = soup(html)
        for card in bs.find_all("a", href=re.compile(r"/es/property/")):
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
                    city="Barcelona",
                )
            )

        return results
