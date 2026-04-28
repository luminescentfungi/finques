"""
Scraper for habitaclia.com – Catalan real-estate portal (JS-rendered).

Search URL  : https://www.habitaclia.com/alquiler-en-barcelones.htm?st=<type>
Pagination  : URL suffix -i{N*25}.htm before .htm
Strategy    : Playwright – collect listing URLs from search pages,
              then fetch each detail page in a single browser session.
Detail page : h1                                        → title
              span.font-2[itemprop="price"]             → price (e.g. "850 €")
"""

from __future__ import annotations

import re
from typing import List

from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, attr, absolute_url

BASE   = "https://www.habitaclia.com"
SEARCH = f"{BASE}/alquiler-en-barcelones.htm"

_TYPE_CODES = {
    "piso":    "1",
    "casa":    "4",
    "local":   "9",
    "parking": "11",
    "oficina": "13",
    "any":     "1,4,9,11,13",
}


def _clean_title(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s*\n+\s*", " | ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip(" |").strip()


class HabitacliaScraper(PlaywrightBaseScraper):
    name = "habitaclia"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        type_code = _TYPE_CODES.get(params.property_type, "1")
        seen_urls: set = set()
        listing_urls: list = []

        # Phase 1 – collect listing URLs from paginated search pages
        for page in range(1, params.max_pages + 1):
            base_path = SEARCH.replace(".htm", f"-i{(page - 1) * 25}.htm") if page > 1 else SEARCH
            query = f"?st={type_code}"
            if params.max_price:
                query += f"&pmax={params.max_price}"
            if params.min_price:
                query += f"&pmin={params.min_price}"
            if params.min_rooms:
                query += f"&hmin={params.min_rooms}"

            html = self._page_html(
                base_path + query,
                wait_selector="article, [class*='list-item']",
            )
            if not html:
                break

            bs = soup(html)
            # Individual listing links look like:
            # /alquiler-piso-en-<location>-<ref>.htm
            cards = bs.find_all(
                "a",
                href=re.compile(
                    r"/alquiler-piso-en-|/alquiler-casa-en-|/alquiler-local-en-|"
                    r"/alquiler-parking-en-|/alquiler-oficina-en-"
                ),
            )
            if not cards:
                break

            new_on_page = 0
            for card in cards:
                href = attr(card, "href")
                listing_url = absolute_url(href, BASE)
                # Skip sub-category aggregation pages (no ref number at end)
                if listing_url not in seen_urls:
                    seen_urls.add(listing_url)
                    listing_urls.append(listing_url)
                    new_on_page += 1
            if new_on_page == 0:
                break

        # Phase 2 – fetch all detail pages in one browser session
        pages_html = self._fetch_batch(
            listing_urls,
            wait_selector="h1, span.font-2",
        )

        for listing_url, detail_html in pages_html.items():
            if not detail_html:
                continue
            detail = soup(detail_html)

            # Title: <h1>...</h1>
            h1 = detail.find("h1")
            if not h1:
                continue
            title = _clean_title(h1.get_text())

            # Price: <span class="font-2" itemprop="price">850 €</span>
            price_span = detail.find(
                "span",
                class_="font-2",
                attrs={"itemprop": "price"},
            )
            if not price_span:
                continue
            price_m = re.search(
                r"([\d\.\,]+)\s*€",
                price_span.get_text(strip=True).replace("\xa0", " "),
            )
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

            bed_m = re.search(r"(\d+)\s*hab", page_text, re.I)
            bedrooms = parse_int(bed_m.group(1)) if bed_m else None

            bath_m = re.search(r"(\d+)\s*ba[\u00f1n]", page_text, re.I)
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
