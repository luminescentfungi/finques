"""
Common HTML parsing helpers used by multiple scrapers.
"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup, Tag


# ---------------------------------------------------------------------------
# Price / numeric extraction
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(r"[\d\.,]+")


def _normalize_price_string(raw: str) -> str:
    """
    Normalise a raw numeric token (digits, dots, commas) to a plain decimal
    string suitable for float().

    Rules
    -----
    1. Both separators present (e.g. "1.200,50" or "1,200.50"):
       The *last* separator is the decimal separator; remove the other.

    2. Only commas present:
       • Exactly one comma followed by exactly 2 digits  → decimal comma
         e.g. "780,50"  → "780.50"
       • Otherwise (3 digits after, or multiple commas)  → thousand separator
         e.g. "1,166"   → "1166"   |  "1,200"   → "1200"

    3. Only dots present:
       • Exactly one dot followed by exactly 2 digits    → decimal dot
         e.g. "780.00"  → "780.00"
       • Otherwise                                       → thousand separator
         e.g. "1.200"   → "1200"   |  "1.166"   → "1166"

    4. No separators: return as-is.
    """
    has_dot = "." in raw
    has_comma = "," in raw

    if has_dot and has_comma:
        # Whichever comes last is the decimal separator
        if raw.rfind(".") > raw.rfind(","):
            # dot is decimal → remove commas
            return raw.replace(",", "")
        else:
            # comma is decimal → remove dots, replace comma with dot
            return raw.replace(".", "").replace(",", ".")

    if has_comma and not has_dot:
        parts = raw.split(",")
        # Single comma + exactly 2 decimal digits → decimal separator
        if len(parts) == 2 and len(parts[1]) == 2:
            return parts[0] + "." + parts[1]
        # Otherwise treat every comma as a thousands separator
        return raw.replace(",", "")

    if has_dot and not has_comma:
        parts = raw.split(".")
        # Single dot + exactly 2 decimal digits → decimal separator
        if len(parts) == 2 and len(parts[1]) == 2:
            return raw  # already valid float string
        # Otherwise treat every dot as a thousands separator
        return raw.replace(".", "")

    return raw


def parse_price(text: str) -> Optional[float]:
    """
    Extract the first numeric value from a price string.

    Correctly handles European thousands separators ("1.200 €", "1,166 €"),
    decimal variants ("780,50 €", "780.00 €"), and mixed formats
    ("1.200,50 €", "1,200.50 €").

    Returns float or None.
    """
    if not text:
        return None
    # Normalise non-breaking spaces and strip
    clean = text.replace("\xa0", " ").strip()
    m = _PRICE_RE.search(clean)
    if not m:
        return None
    normalised = _normalize_price_string(m.group())
    try:
        return float(normalised)
    except ValueError:
        return None


def parse_int(text: str) -> Optional[int]:
    """Extract first integer from a string."""
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def parse_float(text: str) -> Optional[float]:
    """Extract first float (handles dot and comma decimal separators)."""
    m = re.search(r"[\d]+[.,]?[\d]*", text or "")
    if not m:
        return None
    raw = m.group().replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# BeautifulSoup shortcuts
# ---------------------------------------------------------------------------

def soup(html: str, parser: str = "lxml") -> BeautifulSoup:
    """Return a BeautifulSoup object."""
    return BeautifulSoup(html, parser)


def text_of(tag: Optional[Tag], strip: bool = True) -> str:
    """Return the text of a BS4 Tag, or empty string if None."""
    if tag is None:
        return ""
    t = tag.get_text(separator=" ", strip=strip)
    return t.strip() if strip else t


def attr(tag: Optional[Tag], attribute: str, default: str = "") -> str:
    """Return an attribute value from a BS4 Tag, or default if missing."""
    if tag is None:
        return default
    return tag.get(attribute, default) or default


def absolute_url(href: str, base: str) -> str:
    """Make *href* absolute using *base* URL."""
    from urllib.parse import urljoin
    return urljoin(base, href)


def extract_heading(html: str) -> Optional[str]:
    """
    Extract the most prominent heading from a full page HTML.
    Tries h1 → h2 → h3 → <title> in that order.
    Returns None if nothing useful is found.
    """
    if not html:
        return None
    bs = BeautifulSoup(html, "lxml")
    for tag in ("h1", "h2", "h3"):
        el = bs.find(tag)
        if el:
            t = el.get_text(separator=" ", strip=True)
            if t and not t.lower().startswith("http"):
                return t
    title_el = bs.find("title")
    if title_el:
        t = title_el.get_text(strip=True)
        # strip site name suffixes like " | SHBarcelona"
        t = t.split("|")[0].split("-")[0].strip()
        if t:
            return t
    return None
