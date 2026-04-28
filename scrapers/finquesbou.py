"""
Scraper for finquesbou.es (inmobiliariaenbarcelona.finquesbou.es).

URL pattern  : https://inmobiliariaenbarcelona.finquesbou.es/propiedades/alquiler/defecto
Pagination   : ?page=N
Filters      : None exposed in URL (all post-load filtering).
Parsing      : Custom Laende CMS – clean HTML cards with reference, size, rooms, price.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE   = "https://inmobiliariaenbarcelona.finquesbou.es"
SEARCH = f"{BASE}/propiedades/alquiler/defecto"


class FinquesBouScraper(BaseScraper):
    name = "finquesbou"
    base_url = BASE
    uses_js = False

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []

        for page in range(1, params.max_pages + 1):
            url = SEARCH if page == 1 else f"{SEARCH}?page={page}"
            html = self._get_html(url)
            if not html:
                break

            bs = soup(html)
            cards = bs.find_all("a", href=re.compile(r"/propiedad/"))
            if not cards:
                break

            found_any = False
            for card in cards:
                href = attr(card, "href")
                listing_url = absolute_url(href, BASE)
                raw = text_of(card)

                # Pattern:
                # "Alquiler [Type] [description] PRICE €  Referencia: REF
                #  TOTAL m2  USABLE m2  ROOMS  BATHS"

                price_match = re.search(r"([\d\.,]+)\s*€", raw)
                price = parse_price(price_match.group(1)) if price_match else None

                ref_match = re.search(r"Referencia:\s*(\S+)", raw, re.IGNORECASE)
                ref = ref_match.group(1) if ref_match else None

                # Surface: first "N m2" pattern
                size_match = re.search(r"(\d+)\s*m2", raw, re.IGNORECASE)
                size_m2 = parse_float(size_match.group(1)) if size_match else None

                # Rooms/baths appear as bare ints at end of card text
                tail = raw.split("m2")[-1] if "m2" in raw else ""
                nums = re.findall(r"\b(\d+)\b", tail)
                bedrooms  = int(nums[0]) if len(nums) > 0 and nums[0] != "-" else None
                bathrooms = int(nums[1]) if len(nums) > 1 and nums[1] != "-" else None

                # Property type
                type_match = re.search(
                    r"Alquiler\s+(Piso|Local|Casa|Despacho|Parking|Trastero|Ático)",
                    raw, re.IGNORECASE
                )
                prop_type = type_match.group(1).lower() if type_match else "piso"

                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                title = lines[0] if lines else href

                if params.max_price and price and price > params.max_price:
                    continue
                if params.min_price and price and price < params.min_price:
                    continue
                if params.min_rooms and bedrooms is not None and bedrooms < params.min_rooms:
                    continue
                if params.property_type != "any" and params.property_type not in prop_type:
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
                        extra={"property_type": prop_type},
                    )
                )
                found_any = True

            if not found_any:
                break

        return results
