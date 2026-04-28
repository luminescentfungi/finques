"""
Scraper for locabarcelona.com – long-stay rentals (JS-rendered, RealHomes WP theme).

Search URL  : /es/busqueda-inmuebles/?status=alquiler-larga-estancia
Pagination  : &paged=N
Strategy    : Playwright – collect /es/inmueble/<slug>/ links from search pages,
              then fetch each detail page in a single browser session.
Detail page : h1.rh_page__title  → title
              p.price             → price (e.g. "850 €")
"""

from __future__ import annotations

import re
from typing import List

from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, attr, absolute_url

BASE   = "https://www.locabarcelona.com"
SEARCH = f"{BASE}/es/busqueda-inmuebles/"


def _clean_title(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s*\n+\s*", " | ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip(" |").strip()


class LocaBarcelonaScraper(PlaywrightBaseScraper):
    name = "locabarcelona"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        seen_urls: set = set()
        listing_urls: list = []

        # Phase 1 – collect listing URLs from paginated search pages
        for page in range(1, params.max_pages + 1):
            url = f"{SEARCH}?status=alquiler-larga-estancia"
            if params.max_price:
                url += f"&precio_max={params.max_price}"
            if params.min_price:
                url += f"&precio_min={params.min_price}"
            if params.min_rooms:
                url += f"&habitaciones={params.min_rooms}"
            if page > 1:
                url += f"&paged={page}"

            html = self._page_html(
                url, wait_selector="[class*='rh_prop_card'], [class*='property']"
            )
            if not html:
                break

            bs = soup(html)
            # RealHomes theme uses /es/inmueble/<slug>/ URLs
            cards = bs.find_all(
                "a",
                href=re.compile(r"/es/inmueble/|/inmueble/|/property/"),
            )
            if not cards:
                break

            new_on_page = 0
            for card in cards:
                href = attr(card, "href")
                listing_url = absolute_url(href, BASE)
                if listing_url not in seen_urls:
                    seen_urls.add(listing_url)
                    listing_urls.append(listing_url)
                    new_on_page += 1
            if new_on_page == 0:
                break

        # Phase 2 – fetch all detail pages in one browser session
        pages_html = self._fetch_batch(
            listing_urls,
            wait_selector="h1.rh_page__title, p.price",
        )

        for listing_url, detail_html in pages_html.items():
            if not detail_html:
                continue
            detail = soup(detail_html)

            # Title: <h1 class="rh_page__title">...</h1>
            h1 = detail.find("h1", class_="rh_page__title")
            if not h1:
                continue
            title = _clean_title(h1.get_text())

            # Price: <p class="price">850 €</p>
            p_price = detail.find("p", class_="price")
            if not p_price:
                continue
            price_m = re.search(r"([\d\.\,]+)\s*€", p_price.get_text(strip=True).replace("\xa0", " "))
            price = parse_price(price_m.group(1)) if price_m else None
            if not price or price == 0:
                continue

            if params.max_price and price > params.max_price:
                continue
            if params.min_price and price < params.min_price:
                continue

            page_text = detail.get_text(" ", strip=True)
            size_m = re.search(r"(\d+)\s*m[\u00b22]", page_text, re.I)
            size_m2 = parse_float(size_m.group(1)) if size_m else None

            bed_m = re.search(r"(\d+)\s*[Hh]ab", page_text)
            bedrooms = parse_int(bed_m.group(1)) if bed_m else None

            bath_m = re.search(r"(\d+)\s*[Bb]a[\u00f1n]", page_text)
            bathrooms = parse_int(bath_m.group(1)) if bath_m else None

            if params.min_rooms and bedrooms is not None and bedrooms < params.min_rooms:
                continue
            if params.min_size and size_m2 is not None and size_m2 < params.min_size:
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
