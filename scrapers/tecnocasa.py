"""
Scraper for tecnocasa.es – Barcelona rentals.

URL pattern  : https://www.tecnocasa.es/alquiler/inmuebles/cataluna/barcelona/barcelona.html
Pagination   : None (all ~15 items on one page for Barcelona).
Filters      : URL-based district navigation:
               /alquiler/inmuebles/cataluna/barcelona/barcelona/distritos-{slug}.html
Parsing      : Static HTML, listing links follow
               /alquiler/{type}/barcelona/barcelona/{id}.html
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE = "https://www.tecnocasa.es"
SEARCH_URL = f"{BASE}/alquiler/inmuebles/cataluna/barcelona/barcelona.html"


class TecnocasaScraper(PlaywrightBaseScraper):
    name = "tecnocasa"
    base_url = BASE
    uses_js = True

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        url = self._build_url(params)
        html = self._page_html(url, wait_selector="div.estates-list")
        if not html:
            return results

        bs = soup(html)

        estates_list = bs.find("div", class_="estates-list")
        if not estates_list:
            return results

        estate_cards = estates_list.find_all("div", class_="estate-card")
        if not estate_cards:
            return results

        for card in estate_cards:
            link_tag = card.find("a", href=True)
            if not link_tag:
                continue
            href = attr(link_tag, "href")
            listing_url = absolute_url(href, BASE)

            # Price
            price_tag = card.find(class_="estate-card-current-price")
            price_raw = text_of(price_tag) if price_tag else ""
            price_match = re.search(r"([\d\.\s,]+)\s*€", price_raw)
            price = parse_price(price_match.group(1)) if price_match else None

            # Title: combine h3 title + h4 subtitle with " | "
            title_tag = card.find(class_="estate-card-title")
            subtitle_tag = card.find(class_="estate-card-subtitle")
            title_text = text_of(title_tag).strip() if title_tag else ""
            subtitle_text = text_of(subtitle_tag).strip() if subtitle_tag else ""
            title = f"{title_text} | {subtitle_text}" if subtitle_text else title_text

            # Location from subtitle (e.g. "Barcelona, Eixample")
            location = None
            if subtitle_text:
                parts = subtitle_text.split(",", 1)
                location = parts[1].strip() if len(parts) > 1 else subtitle_text

            # Bedrooms
            rooms_tag = card.find(class_="estate-card-rooms")
            bed_match = re.search(r"(\d+)\s*dorm", text_of(rooms_tag), re.IGNORECASE) if rooms_tag else None
            bedrooms = parse_int(bed_match.group(1)) if bed_match else None

            # Size
            surface_tag = card.find(class_="estate-card-surface")
            size_match = re.search(r"(\d+)\s*m", text_of(surface_tag), re.IGNORECASE) if surface_tag else None
            size_m2 = parse_float(size_match.group(1)) if size_match else None

            # Bathrooms
            bath_tag = card.find(class_="estate-card-bathrooms")
            bath_match = re.search(r"(\d+)\s*ba[ñn]o", text_of(bath_tag), re.IGNORECASE) if bath_tag else None
            bathrooms = parse_int(bath_match.group(1)) if bath_match else None

            # Property type from URL
            type_match = re.search(r"/alquiler/([^/]+)/", href)
            prop_type = type_match.group(1).replace("-", " ") if type_match else "inmueble"

            # Local filters
            if params.max_price and price and price > params.max_price:
                continue
            if params.min_price and price and price < params.min_price:
                continue
            if params.min_rooms and bedrooms is not None and bedrooms < params.min_rooms:
                continue
            if params.property_type != "any" and params.property_type not in prop_type.lower():
                continue

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
                )
            )

        return results

    def _build_url(self, params: SearchParams) -> str:
        if params.district:
            slug = params.district.lower().replace(" ", "-").replace("à", "a").replace("è", "e")
            return f"{BASE}/alquiler/inmuebles/cataluna/barcelona/barcelona/distritos-{slug}.html"
        return SEARCH_URL
