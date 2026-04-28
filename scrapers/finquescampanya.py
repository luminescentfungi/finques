"""
Scraper for finquescampanya.com – WordPress / Real Homes theme.

URL pattern  : https://finquescampanya.com/es/resultado-de-la-busqueda/
Query params : keyword, location, child-location, grandchild-location,
               type, bedrooms, min-price, max-price, min-area, max-area, status
               status=alquiler for rentals.
Pagination   : ?page_number=N  (Real Homes default)
Parsing      : Standard WP Real Homes theme card selectors.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE   = "https://finquescampanya.com"
SEARCH = f"{BASE}/es/resultado-de-la-busqueda/"

_LOCATION_MAP = {
    "barcelona":  "barcelona-es",
    "eixample":   "eixample-es",
    "sant andreu": "sant-andreu-es",
}

_BEDROOMS_MAP = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5+"}


class FinquesCampanyaScraper(BaseScraper):
    name = "finquescampanya"
    base_url = BASE
    uses_js = False

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        city_slug = _LOCATION_MAP.get(params.city.lower(), "")

        for page in range(1, params.max_pages + 1):
            query = {
                "status":            "alquiler",
                "location":          city_slug,
                "child-location":    "any",
                "grandchild-location": "any",
                "type":              "any" if params.property_type == "any" else params.property_type,
                "bedrooms":          str(params.min_rooms) if params.min_rooms else "any",
                "min-price":         str(params.min_price) if params.min_price else "any",
                "max-price":         str(params.max_price) if params.max_price else "any",
                "min-area":          str(params.min_size) if params.min_size else "",
                "max-area":          str(params.max_size) if params.max_size else "",
                "keyword":           "",
            }
            if page > 1:
                query["page_number"] = str(page)

            html = self._get_html(SEARCH, params=query)
            if not html:
                break

            bs = soup(html)
            # Real Homes theme uses <article class="property-item"> or similar
            cards = bs.select("article.property-item, .rh_list_card, .listing-unit")
            if not cards:
                # Try generic approach
                cards = bs.select("a[href*='/property/']")

            if not cards:
                break

            found_any = False
            for card in cards:
                href = attr(card, "href") if card.name == "a" else attr(card.find("a"), "href")
                if not href:
                    continue
                listing_url = absolute_url(href, BASE)
                raw = text_of(card)

                price_match = re.search(r"([\d\.,]+)\s*€\s*al mes", raw, re.IGNORECASE)
                price = parse_price(price_match.group(1)) if price_match else None

                bed_match  = re.search(r"(\d+)\s*Habitac", raw, re.IGNORECASE)
                bedrooms   = parse_int(bed_match.group(1)) if bed_match else None

                bath_match = re.search(r"(\d+)\s*Ba[ñn]os?", raw, re.IGNORECASE)
                bathrooms  = parse_int(bath_match.group(1)) if bath_match else None

                size_match = re.search(r"([\d\.,]+)\s*m2?", raw, re.IGNORECASE)
                size_m2    = parse_float(size_match.group(1)) if size_match else None

                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                title = lines[0] if lines else href

                results.append(
                    self._safe_listing(
                        url=listing_url,
                        title=title,
                        price=price,
                        size_m2=size_m2,
                        bedrooms=bedrooms,
                        bathrooms=bathrooms,
                        city=params.city,
                    )
                )
                found_any = True

            if not found_any:
                break

        return results
