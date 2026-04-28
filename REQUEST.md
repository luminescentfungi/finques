# REQUEST MODE — Automated Rental Request Submission

This document describes how to implement a **request mode** for each scraper agent:
the ability to detect a contact/enquiry form on a listing detail page and automatically
submit a rental request on behalf of the user.

---

## Overview

### Architecture

A new abstract method `request()` should be added to `BaseScraper`:

```python
@abstractmethod
def request(self, listing: Listing, contact: ContactInfo) -> RequestResult:
    """
    Detect and submit a rental enquiry form for *listing*.
    Returns a RequestResult with success flag and message.
    """
    ...
```

A new `ContactInfo` model should be created:

```python
@dataclass
class ContactInfo:
    name: str
    email: str
    phone: str
    message: str = "Estoy interesado/a en el inmueble. ¿Podría contactarme para más información?"
```

And a `RequestResult` model:

```python
@dataclass
class RequestResult:
    success: bool
    agent: str          # scraper name
    listing_url: str
    message: str        # human-readable outcome or error
    raw_response: str = ""
```

### Modes of form interaction

| Mode | Description | Tools needed |
|------|-------------|--------------|
| **Static POST** | Standard HTML `<form>` POSTed directly | `requests` |
| **WordPress CF7 AJAX** | CF7 plugin – `admin-ajax.php` or REST endpoint | `requests` |
| **WordPress Houzez AJAX** | Houzez theme – `admin-ajax.php` + nonce | `requests` (nonce pre-fetch) |
| **WordPress RealHomes AJAX** | RealHomes theme – `admin-ajax.php` + nonce | `requests` (nonce pre-fetch) |
| **Playwright interaction** | JS SPA – must click/type in browser | Playwright |
| **External / manual** | Redirects to third-party or only phone/WhatsApp | N/A – log only |
| **CAPTCHA-blocked** | Image captcha requires solver service | Optional: 2captcha / anti-captcha |

---

## Per-Agent Implementation Guide

---

### 1. `borsalloguers` — borsalloguers.com

**Form type:** WordPress Contact Form 7 (CF7)  
**Submission method:** AJAX POST to `/wp-json/contact-form-7/v1/contact-forms/<ID>/feedback`  
**Needs Playwright:** No  
**CAPTCHA:** ⚠️ Image CAPTCHA present — blocks fully automated submission

**Steps:**
1. Fetch the listing detail page HTML.
2. Find the `<form class="wpcf7-form">` block and extract:
   - `data-id` attribute → CF7 form ID
   - Hidden field `_wpcf7`, `_wpcf7_version`, `_wpcf7_locale`, `_wpcf7_unit_tag`
3. POST to `https://borsalloguers.com/wp-json/contact-form-7/v1/contact-forms/<ID>/feedback` with fields:
   ```
   your-name, your-email, your-phone, your-message
   _wpcf7, _wpcf7_version, _wpcf7_locale, _wpcf7_unit_tag
   ```
4. **CAPTCHA blocker:** The form includes an image CAPTCHA (`captchac` field).  
   **Workaround options:**
   - Integrate a CAPTCHA solving service (e.g. [2captcha](https://2captcha.com) or [Anti-Captcha](https://anti-captcha.com)).
   - Fall back to logging the listing URL and contact info for manual follow-up.

**Recommended approach:** Log as `MANUAL_REQUIRED` unless a captcha solver is configured.

---

### 2. `casablau` — casablau.net

**Form type:** Joomla + OSProperty component  
**Submission method:** Standard HTML POST  
**Needs Playwright:** No  
**CAPTCHA:** None detected

**Steps:**
1. Fetch the listing detail page.
2. Find `<form>` with `action` pointing to `/index.php?option=com_osproperty&task=...`.
3. Extract the hidden CSRF token field (32-char hex, field name varies — look for `<input type="hidden" name="[a-f0-9]{32}" value="1">`).
4. POST to the form `action` URL with fields:
   ```
   name, email, phone, message, <csrf_token>=1
   ```
5. Parse response for confirmation text.

**Note:** The CSRF token changes per page load — always fetch the listing page fresh before submitting.

---

### 3. `century21` — century21.es

**Form type:** Angular SPA — contact form rendered client-side  
**Submission method:** REST API call (JSON) — likely `POST /api/v1/contact` or similar  
**Needs Playwright:** ✅ Yes

**Steps:**
1. Use Playwright to navigate to the listing detail URL.
2. Wait for the contact form to appear (selector: `[class*="contact-form"]` or `button[class*="contact"]`).
3. Fill in fields: name, email, phone, message.
4. Intercept the network request triggered on submit to identify the real API endpoint and payload shape.
5. Optionally, bypass Playwright and replay the captured API call with `requests` + the same headers (Bearer token, `X-Requested-With`, etc.).

**Recommended approach:**  
- First run: use Playwright to intercept the API call and log endpoint + payload.  
- Subsequent runs: send the API call directly via `requests` if no auth token is required per-session.

---

### 4. `dianafinques` — www.dianafinques.com

**Form type:** Inmoweb SaaS platform  
**Submission method:** POST to Inmoweb backend (likely `https://app.inmoweb.es/...` or internal route)  
**Needs Playwright:** No  
**CAPTCHA:** None detected

**Steps:**
1. Fetch the listing detail page.
2. Locate `<form>` — fields typically include: `nombre`, `email`, `telefono`, `comentarios`, plus hidden `ref` (property reference code).
3. Extract the hidden `ref` field value and the form `action` URL.
4. POST with:
   ```
   nombre, email, telefono, comentarios, ref=<property_ref>
   ```
5. The form action URL may point to the same domain or to `app.inmoweb.es` — follow redirects.

**Note:** If the backend URL is `app.inmoweb.es`, set the `Referer` header to the original listing URL.

---

### 5. `donpiso` — www.donpiso.com

**Form type:** Custom PHP/React hybrid — contact form inside a JS-rendered panel  
**Submission method:** AJAX/Fetch to internal API endpoint  
**Needs Playwright:** ✅ Yes (listing pages are JS-rendered)

**Steps:**
1. Use Playwright to navigate to the listing detail page.
2. Click the "Contactar" or "Solicitar visita" button to open the contact panel.
3. Fill in: name, email, phone, message.
4. Intercept the API call on submit (endpoint pattern: `/api/contact` or `/api/leads`).
5. Check for WhatsApp CTA — the site prominently offers WhatsApp as the primary channel. Log the WhatsApp link as an alternative.

**Alternative (WhatsApp):** Extract the WhatsApp link from the listing page (`https://wa.me/34...?text=...`) and present it to the user.

---

### 6. `fincaseva` — www.fincaseva.com

**Form type:** WordPress Contact Form 7 (CF7)  
**Submission method:** AJAX POST to `/wp-json/contact-form-7/v1/contact-forms/<ID>/feedback`  
**Needs Playwright:** No  
**CAPTCHA:** None detected

**Steps:**
1. Fetch the listing detail page.
2. Extract CF7 hidden fields: `_wpcf7`, `_wpcf7_version`, `_wpcf7_locale`, `_wpcf7_unit_tag`.
3. POST to the CF7 REST endpoint with fields:
   ```
   your-name, your-email, your-phone, your-message
   _wpcf7, _wpcf7_version, _wpcf7_locale, _wpcf7_unit_tag
   ```
4. Confirm success by checking JSON response field `"status": "mail_sent"`.

---

### 7. `finquesbou` — inmobiliariaenbarcelona.finquesbou.es

**Form type:** Unknown — JS-heavy, likely custom or WP plugin  
**Submission method:** TBD — requires Playwright inspection  
**Needs Playwright:** ✅ Yes (site is JS-rendered)

**Steps:**
1. Use Playwright to navigate to the listing detail page.
2. Look for a contact section — scroll down to find the form or "Contactar" button.
3. Fill in form fields and intercept the network request.
4. Log the API endpoint and payload for a static implementation.

**Note:** The site subdomain (`inmobiliariaenbarcelona.finquesbou.es`) suggests a white-label platform. If WP is detected in the page source, try the CF7 approach first.

---

### 8. `finquescampanya` — finquescampanya.com

**Form type:** WordPress RealHomes theme  
**Submission method:** AJAX POST to `/wp-admin/admin-ajax.php` with `action=make_an_offer_email`  
**Needs Playwright:** No  
**CAPTCHA:** None — privacy checkbox only (can be set to `1`)

**Steps:**
1. Fetch the listing detail page.
2. Extract the nonce: look for `inspiry_ajax_nonce` in a `<script>` block or inline JS object (e.g. `var iasOptions = {..., "nonce":"<value>", ...}`).
3. Extract the listing post ID from the page (typically in `<input name="property_id" value="...">` or a JS variable).
4. POST to `https://finquescampanya.com/wp-admin/admin-ajax.php`:
   ```
   action=make_an_offer_email
   property_id=<id>
   nonce=<inspiry_ajax_nonce>
   name=<name>
   email=<email>
   phone=<phone>
   message=<message>
   privacy_policy=1
   ```
5. Confirm success: JSON response `{"status":"success"}` or similar.

---

### 9. `finquesmarba` — www.finquesmarba.com

**Form type:** WordPress Houzez theme  
**Submission method:** AJAX POST to `/wp-admin/admin-ajax.php` with `action=houzez_send_message_to_agent`  
**Needs Playwright:** No  
**CAPTCHA:** None — privacy checkbox only

**Steps:**
1. Fetch the listing detail page.
2. Extract `houzez_nonce` from inline JS (look for `var houzezData = {...}` or `houzez_nonce` variable).
3. Extract `prop_id` (Houzez listing post ID) from the page.
4. POST to `https://www.finquesmarba.com/wp-admin/admin-ajax.php`:
   ```
   action=houzez_send_message_to_agent
   houzez_nonce=<nonce>
   prop_id=<id>
   sender_name=<name>
   sender_email=<email>
   sender_phone=<phone>
   message=<message>
   privacy_policy=on
   ```
5. Confirm: JSON `{"type":"success"}`.

---

### 10. `finquesteixidor` — www.finquesteixidor.com

**Form type:** ColdFusion site — contact redirects to external **DocuWare Cloud** form  
**Submission method:** External — `https://<tenant>.docuware.cloud/Forms/...`  
**Needs Playwright:** ✅ Yes (DocuWare form is a JS SPA)

**Steps:**
1. Fetch the listing detail page.
2. Find the "PIDENOS HORA" or contact link — it points to a DocuWare Cloud URL.
3. Use Playwright to navigate to the DocuWare form URL.
4. Fill in the DocuWare form fields (name, email, phone, property ref, message).
5. Submit and capture confirmation.

**Alternative:** Extract the agent's direct email and phone from the listing page and offer them to the user for manual contact. The ColdFusion site also displays WhatsApp links.

**Recommended approach:** Log as `EXTERNAL_FORM` with the DocuWare URL and agent contact details.

---

### 11. `gilamargos` — gilamargos.com

**Form type:** WordPress Houzez theme  
**Submission method:** AJAX POST to `/wp-admin/admin-ajax.php`  
**Needs Playwright:** No  
**CAPTCHA:** None

**Steps:**
1. Fetch listing detail page.
2. Extract `houzez_nonce` from inline JS.
3. Extract `prop_id` from the page.
4. POST to `https://gilamargos.com/wp-admin/admin-ajax.php`:
   ```
   action=houzez_send_message_to_agent
   houzez_nonce=<nonce>
   prop_id=<id>
   sender_name=<name>
   sender_email=<email>
   sender_phone=<phone>
   message=<message>
   privacy_policy=on
   ```
5. Confirm: JSON `{"type":"success"}`.

---

### 12. `grocasa` — www.grocasa.com

**Form type:** JS-rendered SPA (Vue/React)  
**Submission method:** Internal REST API  
**Needs Playwright:** ✅ Yes

**Steps:**
1. Use Playwright to navigate to the listing detail page.
2. Find and click the "Contactar" button.
3. Fill in name, email, phone, message.
4. Intercept the network XHR/Fetch request to identify the API endpoint.
5. Replay the API call with `requests` if possible.

---

### 13. `habitabarcelona` — habitabarcelona.com

**Form type:** WordPress Real Estate 7 / WPGetAPI plugin  
**Submission method:** AJAX POST  
**Needs Playwright:** No  
**CAPTCHA:** ✅ Simple math CAPTCHA — readable from HTML (e.g. `1 + 1 = ?`)

**Steps:**
1. Fetch the listing detail page.
2. Extract the math CAPTCHA question from the HTML (look for `<label>` or `<span>` near the captcha input).
3. Compute the answer programmatically (the question is plain text arithmetic).
4. Extract any hidden fields: `post_id`, `nonce`, `action`.
5. POST to the AJAX endpoint:
   ```
   action=<action_name>
   post_id=<id>
   nonce=<nonce>
   name=<name>
   email=<email>
   phone=<phone>
   message=<message>
   captcha=<computed_answer>
   ```

**Note:** Because the math captcha is in plain HTML, this site is **fully automatable** without external services.

---

### 14. `habitaclia` — www.habitaclia.com

**Form type:** JS SPA — Playwright required  
**Submission method:** Internal REST API (JSON)  
**Needs Playwright:** ✅ Yes

**Steps:**
1. Use Playwright to navigate to the listing detail page.
2. Wait for the contact form button (look for "Contactar" or envelope icon).
3. Click to open the form modal.
4. Fill in: name, email, phone, message.
5. Intercept the POST request to extract API endpoint and required headers/auth.
6. For logged-in flows, a session cookie may be required — consider a prior login step.

**Note:** habitaclia.com may require user registration to contact landlords. Investigate whether anonymous enquiries are supported.

---

### 15. `housfy` — housfy.com

**Form type:** React SPA  
**Submission method:** Housfy internal API  
**Needs Playwright:** ✅ Yes  
**CAPTCHA:** Possible (Google reCAPTCHA detected on some pages)

**Steps:**
1. Use Playwright to navigate to the listing detail page.
2. Interact with the "Contactar" section.
3. Fill in the form fields.
4. Submit and intercept the API call — likely `POST https://api.housfy.com/...` with a JSON body.
5. If reCAPTCHA is present, integrate a solver service or flag as `MANUAL_REQUIRED`.

---

### 16. `immobarcelo` — immobarcelo.es

**Form type:** WordPress Contact Form 7 (CF7)  
**Submission method:** AJAX POST to CF7 REST endpoint  
**Needs Playwright:** No  
**CAPTCHA:** None detected

**Steps:**
1. Fetch the listing detail page.
2. Extract CF7 hidden fields: `_wpcf7`, `_wpcf7_version`, `_wpcf7_locale`, `_wpcf7_unit_tag`.
3. POST to `/wp-json/contact-form-7/v1/contact-forms/<ID>/feedback` with:
   ```
   your-name, your-email, your-phone, your-message
   _wpcf7, _wpcf7_version, _wpcf7_locale, _wpcf7_unit_tag
   ```
4. Confirm: `"status": "mail_sent"`.

**Note:** `immobarcelo.es` lists only direct phone/WhatsApp for most properties. Verify that a CF7 form exists on the detail page before attempting submission. If not, extract and log the contact phone number.

---

### 17. `locabarcelona` — www.locabarcelona.com

**Form type:** WordPress RealHomes theme  
**Submission method:** AJAX POST to `/wp-admin/admin-ajax.php`  
**Needs Playwright:** No  
**CAPTCHA:** None — privacy checkbox only

**Steps:**
1. Fetch the listing detail page.
2. Extract nonce (`inspiry_ajax_nonce`) from inline JS.
3. Extract property ID.
4. Determine enquiry type radio value (e.g. "Alquiler" / "Visita").
5. POST to `https://www.locabarcelona.com/wp-admin/admin-ajax.php`:
   ```
   action=make_an_offer_email
   property_id=<id>
   nonce=<nonce>
   name=<name>
   email=<email>
   phone=<phone>
   message=<message>
   enquiry_type=Alquiler
   privacy_policy=1
   ```

---

### 18. `monapart` — www.monapart.com

**Form type:** Next.js / custom SPA  
**Submission method:** Internal API  
**Needs Playwright:** ✅ Yes

**Steps:**
1. Use Playwright to navigate to the listing detail page.
2. Find the contact section / "Contacta con nosotros" form.
3. Fill in name, email, phone, message.
4. Intercept the API request on submit (likely `POST /api/contact` with JSON body including `listingId`).
5. Replay via `requests` if possible.

---

### 19. `myspotbarcelona` — www.myspotbarcelona.com

**Form type:** Custom SPA — likely React  
**Submission method:** Internal API  
**Needs Playwright:** ✅ Yes

**Steps:**
1. Use Playwright to navigate to the listing detail page.
2. Locate the enquiry/contact form.
3. Fill in required fields.
4. Intercept the network request to identify the endpoint.
5. Note: The site caters to short/medium-term rentals — enquiry flow may differ from standard long-term rental sites (e.g. date picker for availability).

---

### 20. `onixrenta` — www.onixrenta.com

**Form type:** Custom PHP — contact info (phone/email) displayed on listing page  
**Submission method:** No automated form — agent phone and email displayed directly  
**Needs Playwright:** No

**Steps:**
1. Fetch the listing detail page.
2. Extract agent phone number and email address from the HTML.
3. Log these as `ContactDetails` in the result — the user must contact manually or via a mailto link.

**Recommended approach:** Return `RequestResult(success=False, message="Manual contact required", ...)` with extracted phone/email in `raw_response`.

---

### 21. `remax` — www.remax.es

**Form type:** WordPress/Custom — contact form on listing detail pages  
**Submission method:** Likely WordPress AJAX or REST API  
**Needs Playwright:** ✅ Yes (listing pages are JS-rendered)

**Steps:**
1. Use Playwright to navigate to the listing detail page.
2. Wait for the contact form to render.
3. Fill in name, email, phone, message.
4. Intercept the submission request.
5. If WordPress CF7 is detected (check page source for `wpcf7`), fall back to the static CF7 approach after fetching the nonce.

---

### 22. `selektaproperties` — selektaproperties.com

**Form type:** WordPress (custom theme or Elementor)  
**Submission method:** POST — likely CF7 or Elementor Forms  
**Needs Playwright:** No  
**CAPTCHA:** None detected

**Steps:**
1. Fetch the listing detail page.
2. Detect form type:
   - If CF7: extract `_wpcf7` hidden fields → POST to CF7 REST endpoint.
   - If Elementor: extract `form_id`, `referer_title`, `post_id` hidden fields → POST to `/wp-admin/admin-ajax.php` with `action=elementor_pro_forms_send_form`.
3. Fields: `nombre/name`, `email`, `telefono/phone`, `asunto/subject`, `mensaje/message`.
4. Include `Referer` header set to the listing URL.

---

### 23. `shbarcelona` — shbarcelona.com

**Form type:** Next.js site — contact form likely calls an API route  
**Submission method:** `POST /api/contact` or similar Next.js API route  
**Needs Playwright:** ✅ Yes (recommended to handle dynamic fields and tokens)

**Steps:**
1. Use Playwright to navigate to the listing detail URL (format: `/es/l/<slug>`).
2. Find the contact form — fields include: `Nombre`, `Apellido`, `Teléfono`, `Email`, `Disponibilidad`, `Mensaje`.
3. Fill in all fields.
4. Submit and intercept the fetch call to identify the Next.js API route.
5. If the API route does not require session-specific tokens, replay directly with `requests`.
6. The site also has a **"RESERVE AHORA"** button for direct reservation — intercept that flow separately as a booking request (not just an enquiry).

---

### 24. `tecnocasa` — www.tecnocasa.es

**Form type:** Custom PHP / Tecnocasa proprietary platform  
**Submission method:** AJAX POST to internal endpoint  
**Needs Playwright:** ✅ Yes (JS-rendered listing pages)

**Steps:**
1. Use Playwright to navigate to the listing detail page.
2. Wait for the "Contactar" or "Solicitar información" form.
3. Fill in: name, email, phone, message.
4. Intercept the XHR/Fetch request to identify the endpoint (pattern: `/ajax/contact` or `/api/property/contact`).
5. Check for any required hidden fields (property code, agency ID) in the form.

---

## Common Implementation Patterns

### CF7 AJAX POST (borsalloguers, fincaseva, immobarcelo)

```python
import re, requests
from bs4 import BeautifulSoup

def submit_cf7(listing_url: str, contact: ContactInfo) -> dict:
    html = requests.get(listing_url).text
    bs = BeautifulSoup(html, "html.parser")
    form = bs.select_one("form.wpcf7-form")
    form_id = form["data-id"]

    hidden = {tag["name"]: tag.get("value","") for tag in form.select("input[type=hidden]")}
    payload = {
        **hidden,
        "your-name": contact.name,
        "your-email": contact.email,
        "your-phone": contact.phone,
        "your-message": contact.message,
    }
    base = listing_url.split("/", 3)[:3]
    endpoint = f"{'/'.join(base)}/wp-json/contact-form-7/v1/contact-forms/{form_id}/feedback"
    resp = requests.post(endpoint, data=payload, headers={"Referer": listing_url})
    return resp.json()
```

### Houzez AJAX POST (finquesmarba, gilamargos)

```python
import re, requests
from bs4 import BeautifulSoup

def submit_houzez(listing_url: str, contact: ContactInfo) -> dict:
    html = requests.get(listing_url).text

    # Extract nonce and prop_id from inline JS
    nonce = re.search(r'houzez_nonce["\s:]+["\']([^"\']+)', html).group(1)
    prop_id = re.search(r'prop_id["\s:]+["\']?(\d+)', html).group(1)

    base = listing_url.split("/", 3)[:3]
    endpoint = f"{'/'.join(base)}/wp-admin/admin-ajax.php"
    payload = {
        "action": "houzez_send_message_to_agent",
        "houzez_nonce": nonce,
        "prop_id": prop_id,
        "sender_name": contact.name,
        "sender_email": contact.email,
        "sender_phone": contact.phone,
        "message": contact.message,
        "privacy_policy": "on",
    }
    resp = requests.post(endpoint, data=payload, headers={"Referer": listing_url})
    return resp.json()
```

### RealHomes AJAX POST (finquescampanya, locabarcelona)

```python
import re, requests
from bs4 import BeautifulSoup

def submit_realhomes(listing_url: str, contact: ContactInfo) -> dict:
    html = requests.get(listing_url).text

    nonce = re.search(r'inspiry_ajax_nonce["\s:]+["\']([^"\']+)', html).group(1)
    prop_id = re.search(r'"property_id"\s*:\s*"?(\d+)', html).group(1)

    base = listing_url.split("/", 3)[:3]
    endpoint = f"{'/'.join(base)}/wp-admin/admin-ajax.php"
    payload = {
        "action": "make_an_offer_email",
        "property_id": prop_id,
        "nonce": nonce,
        "name": contact.name,
        "email": contact.email,
        "phone": contact.phone,
        "message": contact.message,
        "privacy_policy": "1",
    }
    resp = requests.post(endpoint, data=payload, headers={"Referer": listing_url})
    return resp.json()
```

### Playwright generic pattern (SPA sites)

```python
from playwright.sync_api import sync_playwright

def submit_via_playwright(listing_url: str, contact: ContactInfo,
                          form_selector: str, field_map: dict) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(listing_url, wait_until="networkidle")

        # Intercept the submission network request
        with page.expect_request("**/api/**") as req_info:
            for selector, value in field_map.items():
                page.fill(selector, value)
            page.click("button[type=submit]")

        request = req_info.value
        browser.close()
        return f"Submitted to: {request.url}"
```

---

## Priority Implementation Order

| Priority | Agent | Difficulty | Method |
|----------|-------|-----------|--------|
| 1 | `finquesmarba` | Low | Houzez AJAX |
| 2 | `gilamargos` | Low | Houzez AJAX |
| 3 | `finquescampanya` | Low | RealHomes AJAX |
| 4 | `locabarcelona` | Low | RealHomes AJAX |
| 5 | `fincaseva` | Low | CF7 REST |
| 6 | `immobarcelo` | Low | CF7 REST |
| 7 | `dianafinques` | Low | Inmoweb POST |
| 8 | `casablau` | Low | Joomla POST + CSRF token |
| 9 | `habitabarcelona` | Low-Med | WP AJAX + math captcha |
| 10 | `selektaproperties` | Med | CF7 / Elementor POST |
| 11 | `shbarcelona` | Med | Next.js API route (Playwright) |
| 12 | `donpiso` | Med | Playwright + API intercept |
| 13 | `grocasa` | Med | Playwright + API intercept |
| 14 | `monapart` | Med | Playwright + API intercept |
| 15 | `remax` | Med | Playwright + WP AJAX |
| 16 | `tecnocasa` | Med | Playwright + API intercept |
| 17 | `century21` | Med | Playwright + API intercept |
| 18 | `habitaclia` | High | Playwright + session/login |
| 19 | `housfy` | High | Playwright + reCAPTCHA |
| 20 | `myspotbarcelona` | High | Playwright + API intercept |
| 21 | `finquesbou` | High | Playwright (unknown platform) |
| 22 | `finquesteixidor` | High | External DocuWare form |
| 23 | `borsalloguers` | High | CF7 + image CAPTCHA solver |
| 24 | `onixrenta` | N/A | Phone/email only — manual |

---

## Notes

- **Rate limiting:** Space out submissions. Add a 2–5 second random delay between requests.
- **User-Agent:** Use a realistic browser User-Agent string for all requests.
- **GDPR / Terms of Service:** Automated form submission may violate some sites' terms of service. Always use for legitimate rental enquiries only and respect `robots.txt`.
- **Session cookies:** Some sites (habitaclia, housfy) may require a logged-in session to contact landlords. Add an optional `login()` method to those scrapers.
- **Nonce expiry:** WordPress nonces expire after 12–24 hours. Always fetch a fresh listing page immediately before submitting.
