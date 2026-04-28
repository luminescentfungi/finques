"""
Scraper for shbarcelona.com – long-term rentals.

URL pattern  : https://shbarcelona.com/es/rent/yearly
Pagination   : No standard pagination – all listings displayed on one page.
Filters      : None exposed via URL; all filtering is client-side JS.
Parsing      : Static HTML, each listing is an <a> card.
"""

from __future__ import annotations

import re
from typing import List

from scrapers.base import BaseScraper
from models import SearchParams, Listing
from utils import soup, parse_price, parse_int, text_of, attr, absolute_url

BASE = "https://shbarcelona.com"
SEARCH_URL = f"{BASE}/es/rent/yearly"


class SHBarcelonaScraper(BaseScraper):
    name = "shbarcelona"
    base_url = BASE
    uses_js = False

    def search(self, params: SearchParams) -> List[Listing]:
        results: List[Listing] = []
        html = self._get_html(SEARCH_URL)
        if not html:
            return results

        bs = soup(html)
        # Each listing is an <a> tag containing:
        #   - The title text (street name)
        #   - District / city info
        #   - REF number
        #   - Size, bedrooms, bathrooms
        #   - Price
        seen_urls: set = set()

        for card in bs.select("a[href*='/es/l/']"):
            href = attr(card, "href")
            url = absolute_url(href, BASE)

            # --- Skip duplicates ---
            if url in seen_urls:
                continue

            raw_text = text_of(card)

            # --- Price ---
            # Look for patterns like "884 € / MES" or "884€/mes" anywhere in the card
            price_match = re.search(
                r"([\d][\d\.\,]*)\s*€\s*/\s*mes",
                raw_text,
                re.IGNORECASE,
            )
            price = parse_price(price_match.group(1)) if price_match else None

            # Skip this card entirely if it carries no useful info
            # (image-only links, badge links, etc. have very short or empty text)
            meaningful_text = raw_text.replace(href, "").strip()
            if len(meaningful_text) < 10 and price is None:
                continue

            # --- Bedrooms ---
            bed_match = re.search(r"(\d+)\s*Habitaciones?", raw_text, re.IGNORECASE)
            bedrooms = int(bed_match.group(1)) if bed_match else None

            # --- Bathrooms ---
            bath_match = re.search(r"(\d+)\s*Baños?", raw_text, re.IGNORECASE)
            bathrooms = int(bath_match.group(1)) if bath_match else None

            # --- Size ---
            size_match = re.search(r"(\d+)\s*m[²2]", raw_text, re.IGNORECASE)
            size_m2 = float(size_match.group(1)) if size_match else None

            # --- REF ---
            ref_match = re.search(r"REF\s+(\S+)", raw_text, re.IGNORECASE)
            ref = ref_match.group(1) if ref_match else None

            # --- Location: "District | City" ---
            loc_match = re.search(
                r"([\w\-\s]+)\s*\|\s*(Barcelona|Hospitalet.*?)\s*\|",
                raw_text,
                re.IGNORECASE,
            )
            location = loc_match.group(1).strip() if loc_match else None

            # --- Title: first meaningful line, or fetch h1 from listing page ---
            title_lines = [
                l.strip() for l in raw_text.splitlines()
                if l.strip() and not l.strip().startswith("http")
            ]
            if title_lines:
                title = title_lines[0]
            else:
                title = self._fetch_heading(url)

            # --- Apply price filters ---
            if params.max_price and price is not None and price > params.max_price:
                continue
            if params.min_price and price is not None and price < params.min_price:
                continue
            if params.min_rooms and bedrooms is not None and bedrooms < params.min_rooms:
                continue

            seen_urls.add(url)
            results.append(
                self._safe_listing(
                    url=url,
                    title=title,
                    price=price,
                    size_m2=size_m2,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    location=location,
                    city="Barcelona",
                    ref=ref,
                )
            )

        return results
