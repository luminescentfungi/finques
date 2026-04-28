"""
Scraper for selektaproperties.com – Barcelona rentals (Elementor loop, JS-rendered).

Search URL  : https://selektaproperties.com/inmuebles-en-alquiler/?poblacion=29
Pagination  : &paged=N (Elementor loop / WP)
Strategy    : Playwright – wait for Elementor loop items to render.
Card selector: div[data-elementor-type="loop-item"]
  Title + URL : .elementor-widget-theme-post-title a
  Price       : .elementor-widget-heading .elementor-heading-title (contains "€")
  Bedrooms    : .elementor-heading-title text matching r"(\d+)\s*hab"
  Size        : .elementor-heading-title text matching r"(\d+)\s*m2"
  Neighbourhood: first <span> inside the location row
"""

from __future__ import annotations
import re
from typing import List
from scrapers.playwright_base import PlaywrightBaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, parse_float, text_of, attr, absolute_url

BASE       = "https://selektaproperties.com"
SEARCH_URL = f"{BASE}/inmuebles-en-alquiler/"
CARD_SEL   = "div[data-elementor-type='loop-item']"


class SelektaPropertiesScraper(PlaywrightBaseScraper):
    name = "selektaproperties"
    base_url = BASE

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        seen_urls: set = set()

        for page in range(1, params.max_pages + 1):
            url = SEARCH_URL + "?poblacion=29"
            if params.max_price:
                url += f"&precio_max={params.max_price}"
            if params.min_price:
                url += f"&precio_min={params.min_price}"
            if page > 1:
                url += f"&paged={page}"

            html = self._page_html(url, wait_selector=CARD_SEL)
            if not html:
                break

            bs = soup(html)
            cards = bs.select(CARD_SEL)
            if not cards:
                break

            found_any = False
            for card in cards:
                # --- URL + title ---
                title_tag = card.select_one(".elementor-widget-theme-post-title a")
                if not title_tag:
                    continue
                href = attr(title_tag, "href")
                listing_url = absolute_url(href, BASE)
                if listing_url in seen_urls:
                    continue
                seen_urls.add(listing_url)
                found_any = True

                title = title_tag.get_text(strip=True)

                # --- Price: heading that contains "€" ---
                price = None
                for htag in card.select(".elementor-heading-title"):
                    txt = htag.get_text(strip=True)
                    if "€" in txt:
                        price = parse_price(txt)
                        break

                # --- Bedrooms: heading matching "N hab" ---
                bedrooms = None
                size_m2 = None
                for htag in card.select(".elementor-heading-title"):
                    txt = htag.get_text(strip=True)
                    m = re.search(r"(\d+)\s*hab", txt, re.IGNORECASE)
                    if m:
                        bedrooms = parse_int(m.group(1))
                    m2 = re.search(r"(\d+)\s*m2", txt, re.IGNORECASE)
                    if m2:
                        size_m2 = parse_float(m2.group(1))

                # --- Neighbourhood: first <span> in location row ---
                neighbourhood = None
                span = card.select_one(".elementor-heading-title span")
                if span:
                    neighbourhood = span.get_text(strip=True)

                results.append(
                    self._safe_listing(
                        url=listing_url,
                        title=title,
                        price=price,
                        size_m2=size_m2,
                        bedrooms=bedrooms,
                        location=neighbourhood,
                        city="Barcelona",
                    )
                )

            if not found_any:
                break

        return results
