"""
Requesters for WordPress-based sites:
  - CF7 (Contact Form 7)  → borsalloguers, fincaseva, immobarcelo, locabarcelona,
                             selektaproperties, remax, finquesmarba (fallback)
  - Houzez theme AJAX     → gilamargos
  - RealHomes theme AJAX  → finquescampanya, locabarcelona
"""
from __future__ import annotations

import re

from .base import (
    BaseRequester, build_message, _session, _base_url, _soup, _polite_sleep,
)
from models import Listing, ContactInfo, RequestResult


# ---------------------------------------------------------------------------
# Generic CF7 requester
# ---------------------------------------------------------------------------

class CF7Requester(BaseRequester):
    """
    Works for any WordPress + Contact Form 7 site.
    Subclasses must set `source` and may override `field_map` / `phone_attr`.

    phone_attr: "phone_full" (+34672010807) or "phone_local" (672010807)
    """
    source = "cf7_generic"
    field_map: dict = {
        "name":    "your-name",
        "email":   "your-email",
        "phone":   "your-phone",
        "message": "your-message",
    }
    phone_attr: str = "phone_local"  # most ES sites accept 9-digit local format

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        sess = _session()
        try:
            resp = sess.get(listing.url, timeout=20)
            html = resp.text
        except Exception as exc:
            return self._fail(listing, "error", f"GET listing failed: {exc}")

        bs = _soup(html)
        form = bs.select_one("form.wpcf7-form")
        if not form:
            return self._fail(listing, "error", "CF7 form not found on listing page")

        # Image CAPTCHA detection
        if form.select_one("img[src*='wpcf7_captcha'], input[name*='captcha']"):
            return self._fail(
                listing, "captcha",
                f"{self.source}: image CAPTCHA present — manual submission required. "
                f"URL: {listing.url}",
            )

        form_id = (
            form.get("data-id")
            or re.search(r"wpcf7-f(\d+)", form.get("id", ""), re.I)
            and re.search(r"wpcf7-f(\d+)", form.get("id", ""), re.I).group(1)
            or "0"
        )

        hidden = {
            tag["name"]: tag.get("value", "")
            for tag in form.select("input[type=hidden]")
            if tag.get("name")
        }

        phone_val = getattr(contact, self.phone_attr)
        msg = build_message(listing)

        payload = {
            **hidden,
            self.field_map["name"]:    contact.name,
            self.field_map["email"]:   contact.email,
            self.field_map["phone"]:   phone_val,
            self.field_map["message"]: msg,
        }

        endpoint = (
            f"{_base_url(listing.url)}/wp-json/contact-form-7/v1/"
            f"contact-forms/{form_id}/feedback"
        )

        _polite_sleep()
        try:
            r = sess.post(
                endpoint, data=payload,
                headers={"Referer": listing.url, "Accept": "application/json"},
                timeout=20,
            )
            data = r.json()
            if data.get("status") == "mail_sent":
                return self._ok(listing, "CF7: mail sent successfully", r.text)
            return self._fail(listing, "error", data.get("message", r.text)[:200], r.text)
        except Exception as exc:
            return self._fail(listing, "error", str(exc))


# ---------------------------------------------------------------------------
# CF7 subclasses — site-specific field names
# ---------------------------------------------------------------------------

class BorsalloguerRequester(CF7Requester):
    """CF7 + image CAPTCHA — always returns captcha status."""
    source = "borsalloguers"
    # The parent CF7Requester already detects the captcha and returns early.
    # No special override needed; it will always hit the captcha branch.


class FincasevaRequester(CF7Requester):
    source = "fincaseva"


class ImmobarceloRequester(CF7Requester):
    source = "immobarcelo"
    field_map = {
        "name":    "your-name",
        "email":   "your-email",
        "phone":   "your-phone",
        "message": "your-message",
    }


class SelektaPropertiesRequester(CF7Requester):
    source = "selektaproperties"
    field_map = {
        "name":    "your-name",
        "email":   "your-email",
        "phone":   "your-phone",
        "message": "your-message",
    }


class RemaxRequester(CF7Requester):
    """remax.es uses WordPress; try CF7 static approach first."""
    source = "remax"


# ---------------------------------------------------------------------------
# Houzez theme AJAX requester
# ---------------------------------------------------------------------------

class HouzezRequester(BaseRequester):
    """
    WordPress + Houzez theme.
    POST to /wp-admin/admin-ajax.php with action=houzez_submit_contact_form.

    Used by: gilamargos
    """
    source = "houzez_generic"
    phone_attr: str = "phone_local"

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        sess = _session()
        try:
            resp = sess.get(listing.url, timeout=20)
            html = resp.text
        except Exception as exc:
            return self._fail(listing, "error", f"GET listing failed: {exc}")

        # Extract nonce — Houzez inlines it in various JS objects
        nonce_match = re.search(
            r'houzez_nonce["\s:=]+["\']([^"\']+)["\']', html
        ) or re.search(
            r'"nonce"\s*:\s*"([^"]+)"', html
        )
        if not nonce_match:
            return self._fail(listing, "error", "houzez_nonce not found on page")
        nonce = nonce_match.group(1)

        # Extract property post ID
        prop_match = re.search(
            r'["\']?prop(?:erty)?[_-]?id["\']?\s*[=:]\s*["\']?(\d+)', html, re.I
        ) or re.search(r'"post_id"\s*:\s*"?(\d+)', html)
        prop_id = prop_match.group(1) if prop_match else ""

        # Extract agent ID (optional)
        agent_match = re.search(r'listing_agent_id["\s:=]+["\']?(\d+)', html)
        agent_id = agent_match.group(1) if agent_match else ""

        phone_val = getattr(contact, self.phone_attr)
        msg = build_message(listing)

        endpoint = f"{_base_url(listing.url)}/wp-admin/admin-ajax.php"
        payload = {
            "action":           "houzez_submit_contact_form",
            "houzez_nonce":     nonce,
            "prop_id":          prop_id,
            "listing_agent_id": agent_id,
            "fullname":         contact.name,
            "femail":           contact.email,
            "phone":            phone_val,
            "message":          build_message(listing),
        }

        _polite_sleep()
        try:
            r = sess.post(
                endpoint, data=payload,
                headers={"Referer": listing.url, "X-Requested-With": "XMLHttpRequest"},
                timeout=20,
            )
            data = r.json()
            if data.get("type") == "success" or data.get("success"):
                return self._ok(listing, "Houzez: message sent", r.text)
            return self._fail(listing, "error", str(data)[:200], r.text)
        except Exception as exc:
            return self._fail(listing, "error", str(exc))


class GilamargosRequester(HouzezRequester):
    source = "gilamargos"


# ---------------------------------------------------------------------------
# RealHomes / InspireTheme AJAX requester
# ---------------------------------------------------------------------------

class RealHomesRequester(BaseRequester):
    """
    WordPress + RealHomes theme.
    POST to /wp-admin/admin-ajax.php with action=send_email.

    Used by: finquescampanya, locabarcelona
    """
    source = "realhomes_generic"
    phone_attr: str = "phone_local"
    # RealHomes uses different nonce variable names across versions
    _nonce_patterns = [
        r'inspiry_ajax_nonce["\s:=]+["\']([^"\']+)',
        r'realhomes_nonce["\s:=]+["\']([^"\']+)',
        r'"nonce"\s*:\s*"([^"]+)"',
        r"var\s+nonce\s*=\s*['\"]([^'\"]+)",
    ]

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        sess = _session()
        try:
            resp = sess.get(listing.url, timeout=20)
            html = resp.text
        except Exception as exc:
            return self._fail(listing, "error", f"GET listing failed: {exc}")

        nonce = None
        for pat in self._nonce_patterns:
            m = re.search(pat, html)
            if m:
                nonce = m.group(1)
                break
        if not nonce:
            return self._fail(listing, "error", "WP nonce not found on page")

        # Property post ID — look in hidden input or JS
        pid_match = re.search(
            r'(?:property_id|post_id)["\s:=]+["\']?(\d+)', html, re.I
        )
        prop_id = pid_match.group(1) if pid_match else ""

        phone_val = getattr(contact, self.phone_attr)
        endpoint = f"{_base_url(listing.url)}/wp-admin/admin-ajax.php"
        payload = {
            "action":        "send_email",
            "nonce":         nonce,
            "property_id":   prop_id,
            "sender_name":   contact.name,
            "sender_email":  contact.email,
            "sender_phone":  phone_val,
            "message":       build_message(listing),
            "privacy_policy": "1",
        }

        _polite_sleep()
        try:
            r = sess.post(
                endpoint, data=payload,
                headers={"Referer": listing.url, "X-Requested-With": "XMLHttpRequest"},
                timeout=20,
            )
            # RealHomes may return plain text or JSON
            try:
                data = r.json()
                ok = data.get("success") or data.get("status") == "success"
            except Exception:
                ok = r.status_code == 200 and len(r.text) < 500
            if ok:
                return self._ok(listing, "RealHomes: message sent", r.text)
            return self._fail(listing, "error", r.text[:200], r.text)
        except Exception as exc:
            return self._fail(listing, "error", str(exc))


class FinquesCampanyaRequester(RealHomesRequester):
    source = "finquescampanya"


class LocaBarcelonaRequester(RealHomesRequester):
    source = "locabarcelona"
    # locabarcelona adds an enquiry_type radio
    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        result = super().send(listing, contact)
        return result  # enquiry_type defaults are server-side; parent payload is sufficient


# ---------------------------------------------------------------------------
# finquesmarba — WordPress + ConvertPlug (unknown exact endpoint)
# Falls back to CF7 attempt, else manual.
# ---------------------------------------------------------------------------

class FinquesMarbaRequester(CF7Requester):
    """
    finquesmarba uses WordPress + ConvertPlug popup.
    Try CF7 endpoint; if no CF7 form found, flag as manual.
    """
    source = "finquesmarba"

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        result = super().send(listing, contact)
        if result.status == "error" and "not found" in result.message:
            return self._fail(
                listing, "manual",
                "finquesmarba: no CF7 form on listing page. "
                f"Contact via WhatsApp or info@finquesmarba.com — {listing.url}",
            )
        return result
