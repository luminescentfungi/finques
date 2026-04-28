"""
Scraper for housfy.com – rental listings, filterable by city.

URL pattern  : https://housfy.com/alquiler-{type}/{city}
               or https://housfy.com/alquiler-pisos/barcelona/barcelona
Pagination   : ?page=N (1-indexed)
Filters      : Embedded in URL path and query params.
Parsing      : Static HTML cards.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, absolute_url

BASE = "https://housfy.com"

_TYPE_MAP = {
    "piso":    "alquiler-pisos",
    "casa":    "alquiler-casas",
    "local":   "alquiler-locales",
    "parking": "alquiler-garajes",
    "oficina": "alquiler-oficinas",
    "any":     "alquiler-inmuebles",
}


class HoushfyScraper(BaseScraper):
    name = "housfy"
    base_url = BASE
    uses_js = False

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        city_slug = params.city.lower().replace(" ", "-")
        type_path = _TYPE_MAP.get(params.property_type, "alquiler-pisos")

        for page in range(1, params.max_pages + 1):
            url = f"{BASE}/{type_path}/{city_slug}"
            query: dict = {"page": page}
            if params.min_price:
                query["price_from"] = params.min_price
            if params.max_price:
                query["price_to"] = params.max_price
            if params.min_rooms:
                query["rooms_from"] = params.min_rooms

            html = self._get_html(url, params=query)
            if not html:
                break

            bs = soup(html)

            # Only real listing pages follow: /alquiler-*/p/<city>/<slug>
            listing_re = re.compile(r"/alquiler-[^/]+/p/[^/]+/[^/]+-\d+/?$")
            seen_urls: set = set()
            found_any = False

            for a_tag in bs.find_all("a", href=True):
                href = a_tag["href"]
                if not listing_re.search(href):
                    continue
                listing_url = absolute_url(href, BASE)
                if listing_url in seen_urls:
                    continue
                seen_urls.add(listing_url)

                # ---- parse title ----
                h1 = a_tag.find("h1", class_=re.compile(r"address__title"))
                title = h1.get_text(strip=True) if h1 else None

                # ---- parse price ----
                price_span = a_tag.find("span", class_=re.compile(r"prices__price"))
                price_text = price_span.get_text(separator=" ", strip=True).replace("\xa0", " ") if price_span else ""
                price_m = re.search(r"([\d\.,]+)\s*€", price_text)
                price = parse_price(price_m.group(1)) if price_m else None

                # ---- parse rooms / size / bathrooms from card text ----
                raw = a_tag.get_text(separator=" ", strip=True)

                if not title:
                    lines = [l.strip() for l in raw.splitlines() if l.strip()]
                    title = lines[0] if lines else listing_url

                bed_match  = re.search(r"(\d+)\s*Habs?", raw, re.IGNORECASE)
                bedrooms   = parse_int(bed_match.group(1)) if bed_match else None

                bath_match = re.search(r"(\d+)\s*Ba[ñn]os?", raw, re.IGNORECASE)
                bathrooms  = parse_int(bath_match.group(1)) if bath_match else None

                size_match = re.search(r"(\d+)\s*m²", raw, re.IGNORECASE)
                size_m2    = parse_float(size_match.group(1)) if size_match else None

                loc_match  = re.search(r",\s*([\w\s\-]+),\s*(" + re.escape(params.city) + ")", raw, re.IGNORECASE)
                location   = loc_match.group(1).strip() if loc_match else None

                # Local price filter (housfy does not always honour query params)
                if params.max_price and price and price > params.max_price:
                    continue
                if params.min_price and price and price < params.min_price:
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
                        city=params.city,
                    )
                )
                found_any = True

            if not found_any:
                break

        return results
