"""
Registry of all rental-request senders, keyed by scraper name.

Usage
-----
from requester import send_request, ALL_REQUESTERS
from models import ContactInfo

contact = ContactInfo.load()
result  = send_request(listing, contact)
"""
from __future__ import annotations

from typing import Dict

from models import Listing, ContactInfo, RequestResult
from .base import BaseRequester

from .wordpress import (
    BorsalloguerRequester,
    FincasevaRequester,
    ImmobarceloRequester,
    SelektaPropertiesRequester,
    RemaxRequester,
    FinquesMarbaRequester,
    GilamargosRequester,
    FinquesCampanyaRequester,
    LocaBarcelonaRequester,
)
from .static_sites import (
    DianaFinquesRequester,
    CasablauRequester,
    HabitaBarcelonaRequester,
    OnixRentaRequester,
    DonPisoRequester,
    TecnocasaRequester,
    FinquesTeixidorRequester,
)
from .playwright_sites import (
    SHBarcelonaRequester,
    GrocasaRequester,
    HousyfyRequester,
    HabitacliaRequester,
    Century21Requester,
    MonapartRequester,
    MySpotBarcelonaRequester,
    FinquesBouRequester,
    RemaxPlaywrightRequester,
)

# ---------------------------------------------------------------------------
# Registry — maps scraper `name` → requester instance
# ---------------------------------------------------------------------------

ALL_REQUESTERS: Dict[str, BaseRequester] = {
    # WordPress CF7
    "borsalloguers":       BorsalloguerRequester(),
    "fincaseva":           FincasevaRequester(),
    "immobarcelo":         ImmobarceloRequester(),
    "selektaproperties":   SelektaPropertiesRequester(),
    "finquesmarba":        FinquesMarbaRequester(),

    # WordPress Houzez
    "gilamargos":          GilamargosRequester(),

    # WordPress RealHomes
    "finquescampanya":     FinquesCampanyaRequester(),
    "locabarcelona":       LocaBarcelonaRequester(),

    # Static / Custom PHP
    "dianafinques":        DianaFinquesRequester(),
    "casablau":            CasablauRequester(),
    "habitabarcelona":     HabitaBarcelonaRequester(),
    "onixrenta":           OnixRentaRequester(),
    "donpiso":             DonPisoRequester(),
    "tecnocasa":           TecnocasaRequester(),

    # External / manual
    "finquesteixidor":     FinquesTeixidorRequester(),

    # Playwright required — stubs
    "shbarcelona":         SHBarcelonaRequester(),
    "grocasa":             GrocasaRequester(),
    "housfy":              HousyfyRequester(),
    "habitaclia":          HabitacliaRequester(),
    "century21":           Century21Requester(),
    "monapart":            MonapartRequester(),
    "myspotbarcelona":     MySpotBarcelonaRequester(),
    "finquesbou":          FinquesBouRequester(),
    "remax":               RemaxPlaywrightRequester(),
}


def send_request(listing: Listing, contact: ContactInfo) -> RequestResult:
    """
    Look up the requester for *listing.source* and submit the enquiry.
    Returns a RequestResult with success=False / status="not_implemented"
    if no requester exists for the source.
    """
    requester = ALL_REQUESTERS.get(listing.source)
    if requester is None:
        return RequestResult(
            source=listing.source,
            listing_url=listing.url,
            listing_title=listing.title,
            success=False,
            status="not_implemented",
            message=f"No requester implemented for '{listing.source}'",
        )
    return requester.send(listing, contact)
