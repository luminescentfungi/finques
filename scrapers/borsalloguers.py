"""
Scraper for borsalloguers.com – Col·legi d'Administradors de Finques BCN-Lleida.

URL pattern  : https://borsalloguers.com/inmuebles//poblacion:{city}/tipo_inmueble:{type}/
Pagination   : /page/{N}/
Filters      : URL path segments: poblacion, tipo_inmueble
Parsing      : WordPress + custom plugin – clean static HTML cards.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE = "https://borsalloguers.com"

_TYPE_MAP = {
    "piso":    "piso",
    "casa":    "no-especificado",
    "local":   "local-comercial",
    "parking": "plaza-garaje-coche",
    "oficina": "despacho",
    "any":     None,
}


class BorsalloguersScraper(BaseScraper):
    name = "borsalloguers"
    base_url = BASE
    uses_js = False

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        seen_urls: set = set()
        city_slug = params.city.lower().replace(" ", "-")
        type_slug = _TYPE_MAP.get(params.property_type)

        for page in range(1, params.max_pages + 1):
            url = self._build_url(city_slug, type_slug, page)
            html = self._get_html(url)
            if not html:
                break

            bs = soup(html)
            # All listing data (price, title, location) lives in div.ficha_resumen.
            # The child <a> tags are empty or "Ver detalles" – never read from them.
            containers = bs.select("div.ficha_resumen")
            if not containers:
                break

            found_any = False
            for container in containers:
                # URL: first /alquiler/ link inside the card
                a_tag = container.select_one("a[href*='/alquiler/']")
                if not a_tag:
                    continue
                href = attr(a_tag, "href")
                if not href or href.endswith("/alquiler/"):
                    continue
                listing_url = absolute_url(href, BASE)

                if listing_url in seen_urls:
                    continue

                raw = text_of(container)

                # Skip sale listings that occasionally appear in rental results
                if re.search(r"\ben\s+venta\b", raw, re.IGNORECASE):
                    continue

                # --- Price: European format "1.200 €" ---
                price_match = re.search(r"([\d][\d\.]*)\s*€", raw)
                price = parse_price(price_match.group(1)) if price_match else None

                bed_match  = re.search(r"(\d+)\s*habitaciones?", raw, re.IGNORECASE)
                bedrooms   = parse_int(bed_match.group(1)) if bed_match else None

                bath_match = re.search(r"(\d+)\s*ba[ñn]os?", raw, re.IGNORECASE)
                bathrooms  = parse_int(bath_match.group(1)) if bath_match else None

                size_match = re.search(r"([\d\.,]+)\s*m[2²]", raw, re.IGNORECASE)
                size_m2    = parse_float(size_match.group(1)) if size_match else None

                # Location: "Neighbourhood - Barcelona (Barcelona)"
                loc_match = re.search(
                    r"([^0-9\n€]{4,50?})\s*[-–]\s*Barcelona",
                    raw, re.IGNORECASE
                )
                location = loc_match.group(1).strip() if loc_match else None
                if location:
                    # strip leading price/type noise
                    location = re.sub(r"^[\w\s]*(alquiler|piso|casa|local)\s+[\d\.,\s€]+", "", location, flags=re.IGNORECASE).strip()

                # Title: prefer h2/h3 inside card, else parse from text
                title_tag = container.select_one("h2, h3, h4")
                if title_tag:
                    title = text_of(title_tag)
                else:
                    title_match = re.search(
                        r"en alquiler en (.+?)(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ -|\s*$)",
                        raw, re.IGNORECASE
                    )
                    title = title_match.group(1).strip() if title_match else self._fetch_heading(listing_url)

                if params.max_price and price is not None and price > params.max_price:
                    continue
                if params.min_price and price is not None and price < params.min_price:
                    continue
                if params.min_rooms and bedrooms is not None and bedrooms < params.min_rooms:
                    continue

                seen_urls.add(listing_url)
                results.append(
                    self._safe_listing(
                        url=listing_url,
                        title=title,
                        price=price,
                        size_m2=size_m2,
                        bedrooms=bedrooms,
                        bathrooms=bathrooms,
                        location=location,
                        city=params.city,
                    )
                )
                found_any = True

            if not found_any:
                break

        return results

    def _build_url(self, city_slug: str, type_slug: str | None, page: int) -> str:
        parts = [f"poblacion:{city_slug}"]
        if type_slug:
            parts.append(f"tipo_inmueble:{type_slug}")
        path = "/".join(parts) + "/"
        if page > 1:
            return f"{BASE}/inmuebles/{path}page/{page}/"
        return f"{BASE}/inmuebles//{path}"
