"""
Scraper for monapart.com – JS-rendered rental portal.

Search URL  : https://www.monapart.com/viviendas-barcelona-alquiler
Pagination  : ?page=N
Strategy    : Playwright – collect listing URLs from search pages,
              then fetch each detail page in a single browser session.
Detail page : h1[class*="estate-item__title"]  → title
              div[class*="estate-item__price"] → price (e.g. "1.200 €")
"""

from __future__ import annotations

import re
from typing import List

from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, attr, absolute_url

BASE   = "https://www.monapart.com"
SEARCH = f"{BASE}/viviendas-barcelona-alquiler"


def _clean_title(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s*\n+\s*", " | ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip(" |").strip()


class MonapartScraper(PlaywrightBaseScraper):
    name = "monapart"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        seen_urls: set = set()
        listing_urls: list = []

        # Phase 1 – collect listing URLs from paginated search pages
        for page in range(1, params.max_pages + 1):
            url = SEARCH if page == 1 else f"{SEARCH}?page={page}"
            html = self._page_html(url, wait_selector="[class*='estate-item']")
            if not html:
                break

            bs = soup(html)
            cards = bs.find_all("a", href=re.compile(
                r"/vivienda-|/piso-|/casa-|/apartamento-|/estudio-"
            ))
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
            wait_selector="[class*='estate-item__price']",
        )

        for listing_url, detail_html in pages_html.items():
            if not detail_html:
                continue
            detail = soup(detail_html)

            # Title: <h1 class="estate-item__title h2" data-v-...>...</h1>
            h1 = detail.find("h1", class_=re.compile(r"estate-item__title"))
            if not h1:
                continue
            title = _clean_title(h1.get_text())

            # Price: <div class="estate-item__price" data-v-...>1.200&nbsp;€</div>
            price_div = detail.find(class_=re.compile(r"estate-item__price"))
            if not price_div:
                continue
            price_text = price_div.get_text(strip=True).replace("\xa0", " ")
            price_m = re.search(r"([\d\.\,]+)\s*€", price_text)
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
