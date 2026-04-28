"""
Scraper for finquesteixidor.com – ColdFusion-based agency.

URL pattern  : https://www.finquesteixidor.com/es/alquiler-barcelona.cfm
               (single page, all listings loaded at once)
Filters      : Type filter via JS dropdown; not accessible via URL params directly.
               We apply local post-fetch filtering.
Parsing      : Static HTML, listings are <a> with href matching /alquiler-pisos-barcelona.cfm/ID/{n}/
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE    = "https://www.finquesteixidor.com"
SEARCH  = f"{BASE}/es/alquiler-barcelona.cfm"


class FinquesTeixidorScraper(BaseScraper):
    name = "finquesteixidor"
    base_url = BASE
    uses_js = False

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        html = self._get_html(SEARCH)
        if not html:
            return results

        bs = soup(html)

        # Collect unique listing URLs from search page
        seen_urls: set = set()
        listing_urls = []
        for card in bs.find_all("a", href=re.compile(r"/alquiler-pisos-barcelona\.cfm/ID/\d+")):
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

            # Price: <span class="label price">950.0 €</span>
            # Note: value is an English float (e.g. '950.0'), NOT European thousands.
            price_tag = detail.find("span", class_="price")
            if not price_tag:
                continue
            price_raw_m = re.search(r"([\d]+(?:\.[\d]+)?)", price_tag.get_text(strip=True))
            price = float(price_raw_m.group(1)) if price_raw_m else None
            if not price or price == 0:
                continue

            # Price range filter
            if params.max_price and price > params.max_price:
                continue
            if params.min_price and price < params.min_price:
                continue

            # Title: <h2> inside div.col-sm-8
            col = detail.find("div", class_="col-sm-8")
            title_tag = col.find("h2") if col else None
            title = title_tag.get_text(strip=True) if title_tag else listing_url

            # Amenities: "Superfície: 40.0 m2  1 Habitaciones  1 Baños  Ascensor"
            amen = detail.find(class_="amenities")
            amen_text = amen.get_text(" ", strip=True) if amen else ""

            size_m = re.search(r"Superfície:\s*([\d\.,]+)\s*m2", amen_text, re.IGNORECASE)
            size_m2 = parse_float(size_m.group(1)) if size_m else None

            bed_m = re.search(r"(\d+)\s*Habitacion", amen_text, re.IGNORECASE)
            bedrooms = int(bed_m.group(1)) if bed_m else None

            bath_m = re.search(r"(\d+)\s*Baño", amen_text, re.IGNORECASE)
            bathrooms = int(bath_m.group(1)) if bath_m else None

            # Property type from amenities
            type_m = re.search(r"Tipo:\s*(\w+)", amen_text, re.IGNORECASE)
            prop_type = type_m.group(1).lower() if type_m else "piso"

            if params.min_rooms and bedrooms is not None and bedrooms < params.min_rooms:
                continue
            if params.property_type != "any" and params.property_type not in prop_type:
                continue

            # Location: zone part of title (e.g. "EIXAMPLE ESQUERRE - ZONA X")
            loc_m = re.match(r"([A-ZÁÉÍÓÚÑ][\w\s\-]+?)\s*[-–]", title)
            location = loc_m.group(1).strip() if loc_m else None

            results.append(
                self._safe_listing(
                    url=listing_url,
                    title=title,
                    price=price,
                    size_m2=size_m2,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    location=location,
                    city="Barcelona",
                    extra={"property_type": prop_type},
                )
            )

        return results
