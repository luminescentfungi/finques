"""
Scraper for dianafinques.com – Inmoweb-powered CMS.

URL pattern  : https://www.dianafinques.com/results/
Query params : id_tipo_operacion=2 (rental), type=24 (piso), dt={district_code}
               For all properties: omit type / dt
Pagination   : page=N (1-indexed) via query param
Filters      : price range, size, bedrooms, bathrooms, property_type
               all passed as GET params.
Parsing      : Static HTML, listing cards with price, title, ref.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE   = "https://www.dianafinques.com"
SEARCH = f"{BASE}/results/"

# Inmoweb type codes observed for rentals
_TYPE_MAP = {
    "piso":    "24",
    "casa":    "25",
    "local":   "30",
    "parking": "32",
    "oficina": "28",
    "any":     "",
}


class DianaFinquesScraper(BaseScraper):
    name = "dianafinques"
    base_url = BASE
    uses_js = False

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        type_code = _TYPE_MAP.get(params.property_type, "")
        seen_urls: set = set()
        pending_urls: list = []

        for page in range(1, params.max_pages + 1):
            query: dict = {
                "id_tipo_operacion": "2",   # alquiler
            }
            if type_code:
                query["type"] = type_code
            if params.min_price:
                query["precio_desde"] = params.min_price
            if params.max_price:
                query["precio_hasta"] = params.max_price
            if params.min_rooms:
                query["habitaciones"] = params.min_rooms
            if params.min_size:
                query["sup_desde"] = params.min_size
            if params.max_size:
                query["sup_hasta"] = params.max_size
            if page > 1:
                query["page"] = page

            html = self._get_html(SEARCH, params=query)
            if not html:
                break

            bs = soup(html)
            # Listing cards are <a href="/piso-en-barcelona-...html">
            cards = bs.find_all("a", href=re.compile(r"/(piso|local|casa|parking|oficina)-en-"))
            if not cards:
                break

            found_any = False
            for card in cards:
                href = attr(card, "href")
                listing_url = absolute_url(href, BASE)
                if listing_url in seen_urls:
                    continue
                seen_urls.add(listing_url)
                pending_urls.append(listing_url)
                found_any = True

            if not found_any:
                break

        # Fetch each detail page for accurate title + price
        for listing_url in pending_urls:
            detail_html = self._get_html(listing_url)
            if not detail_html:
                continue

            detail = soup(detail_html)

            # Price: <p class="precio">Precio: 1.043€/mes</p>
            precio_tag = detail.find("p", class_="precio")
            if not precio_tag:
                continue
            price_m = re.search(r"([\d\.\,]+)\s*€", precio_tag.get_text(strip=True))
            price = parse_price(price_m.group(1)) if price_m else None
            if not price or price == 0:
                continue

            # Price range filter
            if params.max_price and price > params.max_price:
                continue
            if params.min_price and price < params.min_price:
                continue

            # Title: <h1>Piso en Barcelona, alquiler</h1>
            h1 = detail.find("h1")
            title = h1.get_text(strip=True) if h1 else listing_url

            # Attempt to parse size/bedrooms/bathrooms from detail page
            detail_text = detail.get_text(" ", strip=True)

            size_match = re.search(r"(\d+)\s*m[²2]", detail_text, re.IGNORECASE)
            size_m2    = parse_float(size_match.group(1)) if size_match else None

            bed_match  = re.search(r"(\d+)\s*[Hh]ab", detail_text)
            bedrooms   = parse_int(bed_match.group(1)) if bed_match else None

            bath_match = re.search(r"(\d+)\s*[Bb]a[ñn]", detail_text)
            bathrooms  = parse_int(bath_match.group(1)) if bath_match else None

            if params.min_rooms and bedrooms is not None and bedrooms < params.min_rooms:
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
