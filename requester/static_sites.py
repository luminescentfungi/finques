"""
Requesters for non-WordPress sites that use static HTML forms:
  - dianafinques  (Inmoweb SaaS)
  - casablau      (Joomla + OSProperty)
  - habitabarcelona (WordPress + math CAPTCHA)
  - onixrenta     (Custom PHP)
  - donpiso       (Custom PHP)
  - tecnocasa     (Custom PHP)
  - finquesteixidor (ColdFusion → external DocuWare — manual only)
"""
from __future__ import annotations

import re

from .base import (
    BaseRequester, build_message, _session, _base_url, _soup, _polite_sleep,
)
from models import Listing, ContactInfo, RequestResult


# ---------------------------------------------------------------------------
# dianafinques — Inmoweb SaaS
# ---------------------------------------------------------------------------

class DianaFinquesRequester(BaseRequester):
    """
    Inmoweb SaaS platform.
    The per-listing contact form POSTs to the Inmoweb handler with the
    property reference as a hidden field.
    """
    source = "dianafinques"

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        sess = _session()
        try:
            resp = sess.get(listing.url, timeout=20)
            html = resp.text
        except Exception as exc:
            return self._fail(listing, "error", f"GET listing failed: {exc}")

        bs = _soup(html)
        form = bs.select_one("form")
        if not form:
            return self._fail(listing, "error", "No form found on listing page")

        action = form.get("action", "")
        if not action.startswith("http"):
            action = _base_url(listing.url) + ("" if action.startswith("/") else "/") + action.lstrip("/")

        # Collect all hidden fields (includes property ref / inmueble_id)
        hidden = {
            tag["name"]: tag.get("value", "")
            for tag in form.select("input[type=hidden]")
            if tag.get("name")
        }

        msg = build_message(listing)
        payload = {
            **hidden,
            # Common Inmoweb field names — adapt if page differs
            "nombre":       contact.name,
            "email":        contact.email,
            "telefono":     contact.phone_local,
            "comentarios":  msg,
            "privacidad":   "1",
        }

        _polite_sleep()
        try:
            r = sess.post(
                action, data=payload,
                headers={"Referer": listing.url},
                timeout=20,
                allow_redirects=True,
            )
            # Inmoweb typically returns an HTML page with a confirmation message
            if r.status_code == 200 and (
                "gracias" in r.text.lower()
                or "enviado" in r.text.lower()
                or "thank" in r.text.lower()
            ):
                return self._ok(listing, "Inmoweb: form submitted (confirmation in page)", r.url)
            return self._fail(listing, "error", f"HTTP {r.status_code} — check response", r.url)
        except Exception as exc:
            return self._fail(listing, "error", str(exc))


# ---------------------------------------------------------------------------
# casablau — Joomla + OSProperty
# ---------------------------------------------------------------------------

class CasablauRequester(BaseRequester):
    """
    Joomla + OSProperty contact form.
    Requires extracting the Joomla CSRF formToken (32-char hex hidden field).
    """
    source = "casablau"

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        sess = _session()
        try:
            resp = sess.get(listing.url, timeout=20)
            html = resp.text
        except Exception as exc:
            return self._fail(listing, "error", f"GET listing failed: {exc}")

        bs = _soup(html)
        form = bs.select_one("form")
        if not form:
            return self._fail(listing, "error", "No form on listing page")

        # Joomla CSRF token: a hidden input whose *name* is a 32-char hex string
        token_name = None
        for inp in form.select("input[type=hidden]"):
            name = inp.get("name", "")
            if re.match(r"^[0-9a-f]{32}$", name) and inp.get("value") == "1":
                token_name = name
                break

        if not token_name:
            return self._fail(listing, "error", "Joomla formToken not found on page")

        # OSProperty contact task — extract from form action
        action = form.get("action", "")
        if not action.startswith("http"):
            action = _base_url(listing.url) + action

        msg = build_message(listing)
        payload = {
            token_name: "1",
            "name":     contact.name,
            "email":    contact.email,
            "phone":    contact.phone_local,
            "message":  msg,
            # OSProperty typically passes the property ID via the form or URL
        }
        # Collect other hidden fields (property ID etc.)
        for inp in form.select("input[type=hidden]"):
            n = inp.get("name", "")
            if n and n != token_name:
                payload.setdefault(n, inp.get("value", ""))

        _polite_sleep()
        try:
            r = sess.post(
                action, data=payload,
                headers={"Referer": listing.url},
                timeout=20,
                allow_redirects=True,
            )
            if r.status_code in (200, 302):
                return self._ok(listing, f"Joomla form submitted (HTTP {r.status_code})", r.url)
            return self._fail(listing, "error", f"HTTP {r.status_code}", r.url)
        except Exception as exc:
            return self._fail(listing, "error", str(exc))


# ---------------------------------------------------------------------------
# habitabarcelona — WordPress + math CAPTCHA
# ---------------------------------------------------------------------------

class HabitaBarcelonaRequester(BaseRequester):
    """
    Custom WordPress contact form with a plaintext arithmetic CAPTCHA.
    The CAPTCHA question (e.g. "1 + 1 = ?") is in the HTML — we solve it.
    """
    source = "habitabarcelona"

    # Regex to find "N op M = ?" pattern in visible text
    _CAPTCHA_RE = re.compile(r"(\d+)\s*([+\-×x\*])\s*(\d+)\s*=\s*\?", re.I)

    @staticmethod
    def _solve(expr: str) -> str:
        m = HabitaBarcelonaRequester._CAPTCHA_RE.search(expr)
        if not m:
            return ""
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        if op == "+":
            return str(a + b)
        if op in ("-",):
            return str(a - b)
        if op in ("×", "x", "*"):
            return str(a * b)
        return ""

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        # habitabarcelona contact form is on /pages/contact-us/ not per-listing;
        # we submit the general contact form with a note about the listing.
        contact_url = "https://habitabarcelona.com/pages/contact-us/"
        sess = _session()
        try:
            resp = sess.get(contact_url, timeout=20)
            html = resp.text
        except Exception as exc:
            return self._fail(listing, "error", f"GET contact page failed: {exc}")

        bs = _soup(html)
        form = bs.select_one("form")
        if not form:
            return self._fail(listing, "error", "Contact form not found")

        # Solve math CAPTCHA
        captcha_answer = ""
        captcha_field = None
        for label in bs.select("label, span, p"):
            text = label.get_text()
            ans = self._solve(text)
            if ans:
                captcha_answer = ans
                # Find the associated input
                for_attr = label.get("for")
                if for_attr:
                    captcha_field = bs.find("input", {"id": for_attr})
                break

        if not captcha_answer:
            return self._fail(listing, "error", "Math CAPTCHA question not found or unsolvable")

        action = form.get("action", contact_url)
        if not action.startswith("http"):
            action = _base_url(contact_url) + action

        hidden = {
            t["name"]: t.get("value", "")
            for t in form.select("input[type=hidden]")
            if t.get("name")
        }

        msg = (
            f"[Re: {listing.title} — {listing.url}]\n\n"
            + build_message(listing)
        )

        payload = {
            **hidden,
            "nombre":          contact.name,
            "Nombre y Apellido": contact.name,
            "telefono":        contact.phone_local,
            "Teléfono":        contact.phone_local,
            "e-mail":          contact.email,
            "E-mail":          contact.email,
            "asunto":          f"Consulta sobre: {listing.title}",
            "Asunto":          f"Consulta sobre: {listing.title}",
            "mensaje":         msg,
            "Mensaje":         msg,
        }
        # Inject captcha answer
        if captcha_field and captcha_field.get("name"):
            payload[captcha_field["name"]] = captcha_answer
        else:
            # Fallback: guess common captcha field names
            for name in ("captcha", "codigo", "security_code", "codigo_seguridad"):
                payload[name] = captcha_answer

        _polite_sleep()
        try:
            r = sess.post(
                action, data=payload,
                headers={"Referer": contact_url},
                timeout=20,
            )
            if r.status_code == 200:
                return self._ok(listing, "habitabarcelona: form submitted", "")
            return self._fail(listing, "error", f"HTTP {r.status_code}")
        except Exception as exc:
            return self._fail(listing, "error", str(exc))


# ---------------------------------------------------------------------------
# onixrenta — Custom PHP
# ---------------------------------------------------------------------------

class OnixRentaRequester(BaseRequester):
    """
    Custom PHP contact form. Standard HTML POST.
    No CAPTCHA detected; no CSRF token (no WordPress).
    """
    source = "onixrenta"

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        sess = _session()
        try:
            resp = sess.get(listing.url, timeout=20)
            html = resp.text
        except Exception as exc:
            return self._fail(listing, "error", f"GET listing failed: {exc}")

        bs = _soup(html)
        form = bs.select_one("form")
        if not form:
            return self._fail(listing, "error", "No form on listing page")

        action = form.get("action", "")
        if not action.startswith("http"):
            action = _base_url(listing.url) + ("/" if not action.startswith("/") else "") + action.lstrip("/")

        hidden = {
            t["name"]: t.get("value", "")
            for t in form.select("input[type=hidden]")
            if t.get("name")
        }

        msg = build_message(listing)
        payload = {
            **hidden,
            "nombre":    contact.name,
            "name":      contact.name,
            "email":     contact.email,
            "telefono":  contact.phone_local,
            "phone":     contact.phone_local,
            "mensaje":   msg,
            "message":   msg,
            "privacidad": "1",
            "privacy":    "1",
        }

        _polite_sleep()
        try:
            r = sess.post(
                action, data=payload,
                headers={"Referer": listing.url},
                timeout=20,
                allow_redirects=True,
            )
            if r.status_code == 200:
                return self._ok(listing, "onixrenta: form submitted", "")
            return self._fail(listing, "error", f"HTTP {r.status_code}")
        except Exception as exc:
            return self._fail(listing, "error", str(exc))


# ---------------------------------------------------------------------------
# donpiso — Custom PHP platform
# ---------------------------------------------------------------------------

class DonPisoRequester(BaseRequester):
    """
    donpiso.com — Custom PHP. Per-listing contact form.
    The site also prominently offers WhatsApp; we attempt a static POST first.
    """
    source = "donpiso"

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        sess = _session()
        try:
            resp = sess.get(listing.url, timeout=20)
            html = resp.text
        except Exception as exc:
            return self._fail(listing, "error", f"GET listing failed: {exc}")

        bs = _soup(html)
        form = bs.select_one("form")
        if not form:
            # Check for WhatsApp link as fallback
            wa = bs.select_one("a[href*='wa.me'], a[href*='whatsapp']")
            note = f" WhatsApp: {wa['href']}" if wa else ""
            return self._fail(
                listing, "manual",
                f"donpiso: no static form found — JS-rendered.{note} Manual: {listing.url}",
            )

        action = form.get("action", listing.url)
        if not action.startswith("http"):
            action = _base_url(listing.url) + action

        hidden = {
            t["name"]: t.get("value", "")
            for t in form.select("input[type=hidden]")
            if t.get("name")
        }
        msg = build_message(listing)
        payload = {
            **hidden,
            "nombre":   contact.name,
            "email":    contact.email,
            "telefono": contact.phone_local,
            "mensaje":  msg,
        }

        _polite_sleep()
        try:
            r = sess.post(action, data=payload, headers={"Referer": listing.url}, timeout=20)
            if r.status_code == 200:
                return self._ok(listing, "donpiso: form submitted", "")
            return self._fail(listing, "error", f"HTTP {r.status_code}")
        except Exception as exc:
            return self._fail(listing, "error", str(exc))


# ---------------------------------------------------------------------------
# tecnocasa — Custom PHP (Franchising Ibérico Tecnocasa)
# ---------------------------------------------------------------------------

class TecnocasaRequester(BaseRequester):
    """
    tecnocasa.es — Custom PHP per-listing contact form.
    Attempts static POST; the site may require JS for some pages.
    """
    source = "tecnocasa"

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        sess = _session()
        try:
            resp = sess.get(listing.url, timeout=20)
            html = resp.text
        except Exception as exc:
            return self._fail(listing, "error", f"GET listing failed: {exc}")

        bs = _soup(html)
        form = bs.select_one("form")
        if not form:
            return self._fail(
                listing, "manual",
                f"tecnocasa: no static form on listing page — may be JS-rendered. "
                f"Manual: {listing.url}",
            )

        action = form.get("action", listing.url)
        if not action.startswith("http"):
            action = _base_url(listing.url) + action

        hidden = {
            t["name"]: t.get("value", "")
            for t in form.select("input[type=hidden]")
            if t.get("name")
        }
        msg = build_message(listing)
        payload = {
            **hidden,
            "nombre":    contact.name,
            "email":     contact.email,
            "telefono":  contact.phone_local,
            "mensaje":   msg,
            "privacidad": "1",
        }

        _polite_sleep()
        try:
            r = sess.post(action, data=payload, headers={"Referer": listing.url}, timeout=20)
            if r.status_code == 200:
                return self._ok(listing, "tecnocasa: form submitted", "")
            return self._fail(listing, "error", f"HTTP {r.status_code}")
        except Exception as exc:
            return self._fail(listing, "error", str(exc))


# ---------------------------------------------------------------------------
# finquesteixidor — ColdFusion → external DocuWare cloud form
# ---------------------------------------------------------------------------

class FinquesTeixidorRequester(BaseRequester):
    """
    finquesteixidor.com uses ColdFusion and redirects contact to an external
    DocuWare cloud form. Fully manual — we log the DocuWare URL.
    """
    source = "finquesteixidor"
    _DOCUWARE_URL = (
        "https://finquesteixidor.docuware.cloud/docuware/formsweb/"
        "lista-difusion-interesados"
    )

    def send(self, listing: Listing, contact: ContactInfo) -> RequestResult:
        return self._fail(
            listing, "manual",
            f"finquesteixidor: contact form is hosted on external DocuWare. "
            f"Submit manually at: {self._DOCUWARE_URL} "
            f"(reference listing: {listing.url})",
        )
