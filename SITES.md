# Site Status

All 23 sites investigated.  
**✅ Included** = scraper implemented.  
**⚠️ Partial** = scraper implemented with best-effort; may need tuning after live test.  
**❌ Problematic** = site is JS-rendered with no apparent parseable structure or actively
blocks automated access; scraper implemented with Playwright but results not guaranteed.

---

## Included Sites (Static HTML – reliable)

| # | Site | URL | Engine | Notes |
|---|------|-----|--------|-------|
| 1 | **shbarcelona** | https://shbarcelona.com/es/rent/yearly | requests + BS4 | All listings on a single page. Price, rooms, size, ref fully parseable. |
| 2 | **tecnocasa** | https://www.tecnocasa.es/alquiler/inmuebles/cataluna/barcelona/barcelona.html | requests + BS4 | ~15 listings. District filter via URL path. |
| 3 | **housfy** | https://housfy.com/alquiler-pisos/barcelona | requests + BS4 | Paginated. Supports price/rooms query params. |
| 4 | **borsalloguers** | https://borsalloguers.com/inmuebles/ | requests + BS4 | WordPress. URL-based city + type filters. Good structure. |
| 5 | **finquesteixidor** | https://www.finquesteixidor.com/es/alquiler-barcelona.cfm | requests + BS4 | ColdFusion CMS. Single page, ~24 listings. Price visible in headings. |
| 6 | **finquescampanya** | https://finquescampanya.com/es/resultado-de-la-busqueda/ | requests + BS4 | WP Real Homes theme. GET params map directly to filters. |
| 7 | **finquesbou** | https://inmobiliariaenbarcelona.finquesbou.es/propiedades/alquiler/defecto | requests + BS4 | Laende CMS. Clean card HTML, paginated with ?page=N. |
| 8 | **onixrenta** | https://www.onixrenta.com/viviendas/ | requests + BS4 | Custom CMS. Filter by zona, precio, habitaciones via GET. |
| 9 | **dianafinques** | https://www.dianafinques.com/results/ | requests + BS4 | Inmoweb CMS. Rich GET params: type, price, size, rooms, etc. |

---

## Included Sites (Playwright / JS-rendered – best effort)

| # | Site | URL | Notes |
|---|------|-----|-------|
| 10 | **habitabarcelona** | https://habitabarcelona.com/ | React/Vue SPA. Page structure unknown (no static HTML returned). Generic link extraction. |
| 11 | **monapart** | https://www.monapart.com/viviendas-barcelona-alquiler | JS-rendered. Pagination via ?page=N. Generic link extraction. |
| 12 | **donpiso** | https://www.donpiso.com/alquiler-casas-y-pisos/barcelona-barcelona/listado | React SPA. Supports price/rooms query params. |
| 13 | **grocasa** | https://www.grocasa.com/inmuebles#alquilar | Heavy JS, hash-based routing. Generic extraction after render. |
| 14 | **remax** | https://www.remax.es/buscador-de-inmuebles/alquiler/todos/barcelona/barcelona/todos/ | Angular SPA. Rooms filter via URL segment. |
| 15 | **century21** | http://century21.es/alquilar?... | Angular SPA. Filters via query params. |
| 16 | **myspotbarcelona** | https://www.myspotbarcelona.com/properties?location=Barcelona&operation=Rent | JS-rendered. Filters via query params. |
| 17 | **locabarcelona** | https://www.locabarcelona.com/es/busqueda-inmuebles/?status=alquiler-larga-estancia | JS-rendered. Long-stay only. Filters via GET params. |
| 18 | **habitaclia** | https://www.habitaclia.com/alquiler-en-barcelones.htm | JS-heavy Catalan portal. Type codes (st=), price (pmax=). |
| 19 | ~~gilamargos~~ | https://gilamargos.com/es | **Temporarily disabled** (`ENABLED_SCRAPERS["gilamargos"] = False`). Re-enable to restore. |
| 20 | **fincaseva** | https://www.fincaseva.com/ | Structure unknown – static HTML extraction failed. Generic Playwright scraper. |
| 21 | **selektaproperties** | https://selektaproperties.com/ | Structure unknown – static HTML extraction failed. Generic Playwright scraper. |
| 22 | ~~casablau~~ | https://casablau.net/alquiler/pisos-en-alquiler | **Temporarily disabled** (`ENABLED_SCRAPERS["casablau"] = False`). Re-enable to restore. |
| 23 | **finquesmarba** | https://www.finquesmarba.com/alquiler/ | Two-phase Playwright. Grid URLs via `span.property_url`; detail pages for title (`h1.page-title` first text node) and price (`div.price > span`). "Local" listings discarded. |

---

## Notes on "Problematic" Sites

Sites 20–21 (fincaseva, selektaproperties) returned no meaningful content during the initial fetch. Possible reasons:

- **Cloudflare / bot protection** – returns challenge page or empty body.
- **Cookie consent wall** – page is blank until cookie banner is dismissed.
- **Full SPA with no SSR** – all content is injected after complex JS execution.

The scrapers for these sites use Playwright with a network-idle wait, which
resolves most of these issues. If a scraper still returns 0 results after a live
test, the selectors in the `search()` method will need updating based on
inspecting the actual rendered DOM.

---

## Summary

| Category | Count |
|----------|-------|
| Static HTML (requests) | 9 |
| JS-rendered (Playwright) | 14 |
| **Total** | **23** |
