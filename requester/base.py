"""
Base classes and shared helpers for rental enquiry submission.
"""
from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod

import requests as http
from bs4 import BeautifulSoup

from models import Listing, ContactInfo, RequestResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def build_message(listing: Listing) -> str:
    """
    Build the enquiry message.

    Rules:
    - Default (1 bedroom, or 2+ rooms but price ≤ 1000 €):
        singular / solo renter copy.
    - 2+ bedrooms AND price > 1000 €:
        couple copy.
    """
    is_couple = (
        listing.bedrooms is not None
        and listing.bedrooms >= 2
        and listing.price is not None
        and listing.price > 1000
    )

    if is_couple:
        mid = (
            "Somos 2 buscando piso para estancia de larga duración. "
            "Yo desarrollador de software con contrato indefinido, sueldo bruto anual 38000."
        )
    else:
        mid = (
            "Busco piso para estancia de larga duración. "
            "Desarrollador de software con contrato indefinido, sueldo bruto anual 38000."
        )

    return (
        "Hola, ¿que tal?\n"
        "¿Sigue disponible el piso? ¿Sería posible hacer una visita en estos días? "
        f"{mid} No dudes en preguntarme cualquier cosa. Saludos!"
    )


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _session() -> http.Session:
    s = http.Session()
    s.headers.update({"User-Agent": _UA})
    return s


def _base_url(url: str) -> str:
    """Return https://domain.tld from any URL."""
    parts = url.split("/", 3)
    return "/".join(parts[:3])


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _polite_sleep() -> None:
    """Random 2–5 s delay between submissions."""
    time.sleep(random.uniform(2, 5))


# ---------------------------------------------------------------------------
# Base requester
# ---------------------------------------------------------------------------

class BaseRequester(ABC):
    source: str = "base"
    requires_playwright: bool = False

    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        """Submit an enquiry for *listing* using *contact* details."""
        ...

    # -- convenience factories ------------------------------------------------

    def _ok(self, listing: Listing, msg: str = "Sent", raw: str = "") -> RequestResult:
        return RequestResult(
            source=self.source,
            listing_url=listing.url,
            listing_title=listing.title,
            success=True,
            status="sent",
            message=msg,
            raw_response=raw,
        )

    def _fail(
        self, listing: Listing, status: str, msg: str, raw: str = ""
    ) -> RequestResult:
        return RequestResult(
            source=self.source,
            listing_url=listing.url,
            listing_title=listing.title,
            success=False,
            status=status,
            message=msg,
            raw_response=raw,
        )

    def _playwright_stub(self, listing: Listing) -> RequestResult:
        return self._fail(
            listing,
            "playwright_required",
            f"{self.source}: form requires a headless browser — not yet automated. "
            f"Visit manually: {listing.url}",
        )

    def _not_implemented(self, listing: Listing, note: str = "") -> RequestResult:
        return self._fail(
            listing,
            "not_implemented",
            f"{self.source}: no automated submission available. {note}".strip(),
        )
