"""
Data models shared across all scrapers.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
load_dotenv()


@dataclass
class SearchParams:
    """
    Unified search parameters accepted by every scraper.

    Attributes
    ----------
    city        : Free-text city/municipality (default "Barcelona").
    district    : Neighbourhood or district within the city (optional).
    min_price   : Minimum monthly rent in EUR (optional).
    max_price   : Maximum monthly rent in EUR (optional).
    min_rooms   : Minimum number of bedrooms (optional).
    max_rooms   : Maximum number of bedrooms (optional).
    min_size    : Minimum surface in m² (optional).
    max_size    : Maximum surface in m² (optional).
    property_type : One of "piso", "casa", "local", "parking", "oficina", "any".
    max_pages   : Maximum number of result pages to fetch.
    """

    city: str = "Barcelona"
    district: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    property_type: str = "piso"    # "piso" | "casa" | "local" | "parking" | "oficina" | "any"
    max_pages: int = 5


@dataclass
class Listing:
    """
    Normalised property listing returned by every scraper.

    All monetary values are in EUR/month.
    All area values are in m².
    Missing / unknown fields are None.
    """

    source: str                          # scraper name, e.g. "shbarcelona"
    url: str                             # canonical URL of the listing
    title: str                           # short title / headline
    price: Optional[float] = None        # monthly rent (EUR)
    size_m2: Optional[float] = None      # total surface (m²)
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    location: Optional[str] = None       # district / neighbourhood
    city: Optional[str] = None
    description: Optional[str] = None
    ref: Optional[str] = None            # internal agency reference
    extra: dict = field(default_factory=dict)   # catch-all for site-specific fields

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "url": self.url,
            "title": self.title,
            "price_eur_month": self.price,
            "size_m2": self.size_m2,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "location": self.location,
            "city": self.city,
            "description": self.description,
            "ref": self.ref,
            **self.extra,
        }

    def __str__(self) -> str:
        price_str = f"{self.price:.0f} €/mes" if self.price else "–"
        rooms_str = f"{self.bedrooms}h" if self.bedrooms is not None else "?"
        size_str  = f"{self.size_m2:.0f} m²" if self.size_m2 else "?"
        return (
            f"[{self.source}] {self.title} | {price_str} | "
            f"{rooms_str} | {size_str} | {self.location or self.city or '?'}"
        )


# ---------------------------------------------------------------------------
# Contact / request models
# ---------------------------------------------------------------------------

@dataclass
class ContactInfo:
    """User contact details loaded from contact_info.json."""
    name: str
    email: str
    phone_full: str   # e.g. "+34672010807"
    phone_local: str  # e.g. "672010807"

    @classmethod
    def load(cls) -> "ContactInfo":
        missing = [k for k in ("CONTACT_NAME", "CONTACT_EMAIL",
                                "CONTACT_PHONE_FULL", "CONTACT_PHONE_LOCAL")
                   if not os.getenv(k)]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Set them in .env or as GitHub Secrets."
            )
        return cls(
            name=os.getenv("CONTACT_NAME", ""),
            email=os.getenv("CONTACT_EMAIL", ""),
            phone_full=os.getenv("CONTACT_PHONE_FULL", ""),
            phone_local=os.getenv("CONTACT_PHONE_LOCAL", ""),
        )


@dataclass
class RequestResult:
    """Outcome of a single rental enquiry submission attempt."""
    source: str          # scraper/agent name
    listing_url: str
    listing_title: str
    success: bool
    status: str          # "sent" | "captcha" | "playwright_required" | "manual" | "not_implemented" | "error"
    message: str         # human-readable outcome
    raw_response: str = ""

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "listing_url": self.listing_url,
            "listing_title": self.listing_title,
            "success": self.success,
            "status": self.status,
            "message": self.message,
        }
