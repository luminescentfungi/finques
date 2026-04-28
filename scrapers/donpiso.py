"""
Scraper for donpiso.com – Barcelona rental listings (JS-rendered).

URL pattern  : https://www.donpiso.com/alquiler-casas-y-pisos/{city}-{province}/listado
Pagination   : /pagina-{N}/ inserted before ?
Filters      : price range, bedrooms – appended as query params.
Strategy     : Playwright – heavy React SPA.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE = "https://www.donpiso.com"


class DonPisoScraper(PlaywrightBaseScraper):
    name = "donpiso"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        city = params.city.lower().replace(" ", "-")

        for page in range(1, params.max_pages + 1):
            suffix = "" if page == 1 else f"pagina-{page}/"
            url = f"{BASE}/alquiler-casas-y-pisos/{city}-{city}/{suffix}listado"
            query: dict = {}
            if params.max_price:
                query["precioMax"] = params.max_price
            if params.min_price:
                query["precioMin"] = params.min_price
            if params.min_rooms:
                query["habitacionesMin"] = params.min_rooms

            html = self._page_html(url, wait_selector="[class*='PropertyCard'], [class*='listing-card']")
            if not html:
                break

            bs = soup(html)
            cards = bs.find_all("a", href=re.compile(r"/alquiler/|/inmueble/"))
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
