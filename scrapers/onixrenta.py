"""
Scraper for onixrenta.com – Onix Renta Barcelona.

URL pattern  : https://www.onixrenta.com/viviendas/
               https://www.onixrenta.com/locales-comerciales/
               https://www.onixrenta.com/parkings/
Filter params: Exposed as HTML form inputs (Precio, Tipo, Superficie, Habitaciones,
               Zona); submitted as GET query params.
Pagination   : None – all listings on one page per type.
Parsing      : Static HTML, clean card structure.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE = "https://www.onixrenta.com"

_TYPE_MAP = {
    "piso":    "/viviendas/",
    "casa":    "/viviendas/",
    "local":   "/locales-comerciales/",
    "parking": "/parkings/",
    "oficina": "/viviendas/",
    "any":     "/viviendas/",
}


class OnixRentaScraper(BaseScraper):
    name = "onixrenta"
    base_url = BASE
    uses_js = False

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        path = _TYPE_MAP.get(params.property_type, "/viviendas/")

        query: dict = {}
        if params.max_price:
            query["precio_hasta"] = params.max_price
        if params.min_price:
            query["precio_desde"] = params.min_price
        if params.min_rooms:
            query["habitaciones"] = params.min_rooms
        if params.district:
            query["zona"] = params.district.lower().replace(" ", "-")

        html = self._get_html(f"{BASE}{path}", params=query)
        if not html:
            return results

        bs = soup(html)

        # Collect unique listing URLs
        seen_urls: set = set()
        listing_urls = []
        for card in bs.find_all("a", class_="ficha__link",
                                href=re.compile(r"/viviendas/\d+|/locales|/parkings/\d+")):
            href = attr(card, "href")
            listing_url = absolute_url(href, BASE)
            if listing_url not in seen_urls:
                seen_urls.add(listing_url)
                listing_urls.append(listing_url)

        # Fetch each detail page for accurate title + price
        for listing_url in listing_urls:
            detail_html = self._get_html(listing_url)
            if not detail_html:
                continue

            detail = soup(detail_html)

            # Price: <div class="content">1440€/mes</div>
            price_tag = None
            for div in detail.find_all("div", class_="content"):
                txt = div.get_text(strip=True)
                if "€/mes" in txt.lower() or "€" in txt:
                    price_tag = div
                    break
            if not price_tag:
                continue
            price_m = re.search(r"([\d\.\,]+)\s*€", price_tag.get_text(strip=True))
            price = parse_price(price_m.group(1)) if price_m else None
            if not price or price == 0:
                continue

            # Price range filter
            if params.max_price and price > params.max_price:
                continue
            if params.min_price and price < params.min_price:
                continue

            # Title: <h2 class="text-primary mt-5"><strong>…</strong></h2>
            h2 = detail.find("h2", class_="text-primary")
            title = h2.get_text(strip=True) if h2 else listing_url

            # Details block: "Superficie69m2Habitaciones:2Baños:1"
            block = detail.find("div", class_="block")
            block_text = block.get_text(strip=True) if block else ""

            size_m = re.search(r"Superficie\s*(\d+)\s*m2", block_text, re.IGNORECASE)
            size_m2 = parse_float(size_m.group(1)) if size_m else None

            bed_m = re.search(r"Habitaciones:\s*(\d+)", block_text, re.IGNORECASE)
            bedrooms = parse_int(bed_m.group(1)) if bed_m else None

            bath_m = re.search(r"Baños:\s*(\d+)", block_text, re.IGNORECASE)
            bathrooms = parse_int(bath_m.group(1)) if bath_m else None

            ref_m = re.search(r"Referencia:\s*(\d+)", block_text, re.IGNORECASE)
            ref = ref_m.group(1) if ref_m else None

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
                    ref=ref,
                )
            )

        return results
