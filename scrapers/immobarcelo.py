"""
Scraper for immobarcelo.es – long-term rentals in Barcelona.

URL pattern : https://immobarcelo.es/buscar-inmueble/?alquiler=alquiler&Tipo=Pisos&Poblacion=Barcelona&preciomax=<max>
Pagination  : &npag=<n>  (1-based)
Parsing     : Static HTML – listing cards are div.citeminmueble.citemv2
              with data-precio / data-metros attributes.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, text_of, absolute_url

BASE = "https://immobarcelo.es"

# Property-type mapping (site uses capitalised Spanish names)
TYPE_MAP = {
    "piso":     "Pisos",
    "casa":     "Casas",
    "local":    "Locales",
    "parking":  "Garajes",
    "oficina":  "Oficinas",
    "any":      "",
}


class ImmoBarceloScraper(BaseScraper):
    name = "immobarcelo"
    base_url = BASE
    uses_js = False

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        seen_urls: set = set()

        tipo = TYPE_MAP.get(params.property_type, "Pisos")
        city = params.city or "Barcelona"

        for page in range(1, (params.max_pages or 5) + 1):
            url = (
                f"{BASE}/buscar-inmueble/"
                f"?alquiler=alquiler"
                f"&Tipo={tipo}"
                f"&Poblacion={city}"
                f"&preciomax={params.max_price or ''}"
                + (f"&preciomin={params.min_price}" if params.min_price else "")
                + (f"&habitacionesmin={params.min_rooms}" if params.min_rooms else "")
                + (f"&metrosmin={params.min_size}" if params.min_size else "")
                + (f"&npag={page}" if page > 1 else "")
            )

            html = self._get_html(url)
            if not html:
                break

            bs = soup(html)
            cards = bs.find_all("div", class_="citeminmueble")
            if not cards:
                break

            new_this_page = 0
            for card in cards:
                # URL
                a_tag = card.find("a", href=True)
                if not a_tag:
                    continue
                listing_url = absolute_url(a_tag["href"], BASE)
                if listing_url in seen_urls:
                    continue
                seen_urls.add(listing_url)

                # Price  (data-precio attribute is the cleanest source)
                raw_price = card.get("data-precio")
                price = parse_price(raw_price) if raw_price else None

                # Apply max-price filter (site may not honour it perfectly)
                if params.max_price and price and price > params.max_price:
                    continue

                # Size  (data-metros attribute)
                raw_m2 = card.get("data-metros")
                size_m2 = float(raw_m2) if raw_m2 and raw_m2.isdigit() else None

                # Apply min-size filter
                if params.min_size and size_m2 and size_m2 < params.min_size:
                    continue

                # Title
                title_tag = card.find(class_="sitemtitle")
                title = title_tag.get_text(strip=True) if title_tag else None

                # Bedrooms
                bed_tag = card.find(class_="shabsv2")
                bedrooms = None
                if bed_tag:
                    bed_text = bed_tag.get_text(strip=True)
                    m = re.match(r"(\d+)", bed_text)
                    bedrooms = int(m.group(1)) if m else None

                # Apply min-rooms filter
                if params.min_rooms and bedrooms is not None and bedrooms < params.min_rooms:
                    continue

                # Bathrooms
                bath_tag = card.find(class_="sbanosv2")
                bathrooms = None
                if bath_tag:
                    bath_text = bath_tag.get_text(strip=True)
                    m = re.match(r"(\d+)", bath_text)
                    bathrooms = int(m.group(1)) if m else None

                # Location – try to extract from title ("Piso en Barcelona, Poblenou")
                location = None
                if title:
                    loc_m = re.search(r",\s*(.+)$", title)
                    location = loc_m.group(1).strip() if loc_m else None

                results.append(
                    Listing(
                        source=self.name,
                        url=listing_url,
                        title=title,
                        price=price,
                        size_m2=size_m2,
                        bedrooms=bedrooms,
                        bathrooms=bathrooms,
                        location=location,
                        city=city,
                    )
                )
                new_this_page += 1

            # If no new cards were found on this page we've reached the end
            if new_this_page == 0:
                break

        return results
