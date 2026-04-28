"""
Playwright-required requesters — stubs that return playwright_required status.

Each class documents:
  - The expected form/API endpoint
  - How to implement the Playwright flow when ready
  - Any site-specific notes

To implement a site: replace the `send()` stub with real Playwright code
using PlaywrightBaseScraper patterns already in the project.
"""
from __future__ import annotations

from .base import BaseRequester
from models import Listing, ContactInfo, RequestResult


class _PlaywrightRequester(BaseRequester):
    """Base stub for all Playwright-required requesters."""
    requires_playwright: bool = True
    _notes: str = ""

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        return self._fail(
            listing,
            "playwright_required",
            f"{self.source}: requires headless browser interaction. "
            + (f"{self._notes} " if self._notes else "")
            + f"Visit manually: {listing.url}",
        )


# ---------------------------------------------------------------------------
# shbarcelona — React SPA / Next.js
# ---------------------------------------------------------------------------

class SHBarcelonaRequester(_PlaywrightRequester):
    """
    shbarcelona.com — React SPA.

    To implement:
    1. page.goto(listing.url, wait_until="networkidle")
    2. Look for contact form fields: Nombre, Apellido, Teléfono, Email,
       Disponibilidad, Mensaje.
    3. Intercept fetch to /api/... on submit to capture endpoint.
    4. Fields: phone_full (international format accepted).
    5. Also check for "RESERVE AHORA" button — separate booking flow.
    """
    source = "shbarcelona"
    _notes = "React SPA — intercept /api/contact fetch call."


# ---------------------------------------------------------------------------
# grocasa — Custom SPA
# ---------------------------------------------------------------------------

class GrocasaRequester(_PlaywrightRequester):
    """
    grocasa.com — Custom SPA.

    To implement:
    1. page.goto(listing.url, wait_until="networkidle")
    2. Click "Contactar" button.
    3. Fill: Teléfono, Correo, Mensaje.
    4. Intercept XHR to identify endpoint.
    5. WhatsApp fallback: api.whatsapp.com/send?phone=34938256868
    """
    source = "grocasa"
    _notes = "Custom SPA — intercept XHR on form submit."


# ---------------------------------------------------------------------------
# housfy — React / Next.js multi-step wizard
# ---------------------------------------------------------------------------

class HousyfyRequester(_PlaywrightRequester):
    """
    housfy.com — Next.js multi-step lead wizard.

    To implement:
    1. page.goto(listing.url, wait_until="networkidle")
    2. Click "Infórmate gratis" button to start wizard.
    3. Step through wizard steps (type of enquiry, name, email, phone).
    4. Intercept POST to housfy API (possibly https://api.housfy.com/...).
    5. Note: may have reCAPTCHA on final step.
    """
    source = "housfy"
    _notes = "Next.js multi-step wizard. Possible reCAPTCHA on final step."


# ---------------------------------------------------------------------------
# habitaclia — Custom portal (Fotocasa group)
# ---------------------------------------------------------------------------

class HabitacliaRequester(_PlaywrightRequester):
    """
    habitaclia.com — Large aggregator portal.

    To implement:
    1. page.goto(listing.url, wait_until="networkidle")
    2. Click "Contactar" or envelope icon.
    3. Fill in the per-listing messaging form.
    4. Intercept REST API call — likely requires session cookie / login.
    5. NOTE: may require user account registration first.
    """
    source = "habitaclia"
    _notes = "Portal messaging — may require user login/registration."


# ---------------------------------------------------------------------------
# century21 — React SPA (Umbraco backend)
# ---------------------------------------------------------------------------

class Century21Requester(_PlaywrightRequester):
    """
    century21.es — React SPA backed by Umbraco CMS.

    To implement:
    1. page.goto(listing.url, wait_until="networkidle")
    2. Wait for contact form panel to render.
    3. Fill: name, email, phone (full international), message.
    4. Intercept POST to /api/v1/contact or Umbraco REST endpoint.
    5. Check for Bearer token or session requirement.
    """
    source = "century21"
    _notes = "React SPA (Umbraco). Intercept /api/ REST call on submit."


# ---------------------------------------------------------------------------
# monapart — Vue/React (Felix platform)
# ---------------------------------------------------------------------------

class MonapartRequester(_PlaywrightRequester):
    """
    monapart.com — Vue/React SPA ("Felix" platform).

    To implement:
    1. page.goto(listing.url, wait_until="networkidle")
    2. Find "Contacta con nosotros" form.
    3. Fill: name, email, phone, message.
    4. Intercept POST /api/contact (JSON body with listingId).
    5. Platform may require login; check if anonymous enquiry is supported.
    """
    source = "monapart"
    _notes = "Vue/React SPA. May require user login."


# ---------------------------------------------------------------------------
# myspotbarcelona — Unknown SPA (cookie wall)
# ---------------------------------------------------------------------------

class MySpotBarcelonaRequester(_PlaywrightRequester):
    """
    myspotbarcelona.com — Cookie consent wall blocks all static access.

    To implement:
    1. page.goto(listing.url, wait_until="networkidle")
    2. Handle cookie consent dialog.
    3. Find enquiry form (short/medium-term rental — may include date picker).
    4. Fill all fields and intercept API call.
    """
    source = "myspotbarcelona"
    _notes = "Cookie wall + unknown SPA — full Playwright required."


# ---------------------------------------------------------------------------
# finquesbou — Laende platform
# ---------------------------------------------------------------------------

class FinquesBouRequester(_PlaywrightRequester):
    """
    inmobiliariaenbarcelona.finquesbou.es — Laende SaaS platform.

    To implement:
    1. page.goto(listing.url, wait_until="networkidle")
    2. Scroll to contact section.
    3. Fill form and intercept AJAX/REST call.
    4. Alternative: WhatsApp 678 962 310 or finquesbou@finquesbou.es
    """
    source = "finquesbou"
    _notes = "Laende SaaS — unknown endpoints. Alt: WhatsApp 678962310."


# ---------------------------------------------------------------------------
# remax — WordPress but JS-rendered listing pages
# ---------------------------------------------------------------------------

class RemaxPlaywrightRequester(_PlaywrightRequester):
    """
    remax.es — WordPress backend but Angular/React-rendered listing detail pages.

    To implement:
    1. page.goto(listing.url, wait_until="networkidle")
    2. Once rendered, extract CF7 form hidden fields from DOM.
    3. Can replay as static CF7 POST once form_id and nonce are known.
    4. Alternatively fill form via Playwright and submit.
    """
    source = "remax"
    _notes = "WP backend but JS-rendered. Extract CF7 form via Playwright then POST."
