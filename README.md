# Finques Barcelona – Multi-Agency Rental Scraper

A structured Python project that aggregates rental listings from **23 Barcelona
real-estate agencies** through a single search command.

---

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Playwright browsers (needed for JS-heavy sites)
playwright install chromium

# 3. Run a basic search
python main.py --max-price 1200 --type piso

# 4. More options
python main.py --help
```

---

## Usage

```
python main.py [OPTIONS]

Options:
  --city TEXT           City to search (default: Barcelona)
  --district TEXT       Neighbourhood / district filter
  --min-price INT       Minimum monthly rent (€)
  --max-price INT       Maximum monthly rent (€)
  --min-rooms INT       Minimum number of bedrooms
  --max-rooms INT       Maximum number of bedrooms
  --min-size INT        Minimum surface (m²)
  --max-size INT        Maximum surface (m²)
  --type CHOICE         piso | casa | local | parking | oficina | any
  --max-pages INT       Max result pages to fetch per site (default: 5)
  --scrapers TEXT       Comma-separated list of scraper names to run
  --no-js               Skip Playwright scrapers (no headless browser needed)
  --output FILE         Save results to a JSON file
  --list-scrapers       Print all registered scraper names and exit
  --verbose / -v        Enable debug logging
```

### Examples

```bash
# Pisos up to 1000 €/mes, 2+ bedrooms, static scrapers only
python main.py --max-price 1000 --min-rooms 2 --no-js

# All types, all sites, export to JSON
python main.py --type any --output results.json

# Only two specific agencies
python main.py --scrapers shbarcelona,borsalloguers --max-price 1500

# List all registered scrapers
python main.py --list-scrapers
```

---

## Project Structure

```
finques/
├── main.py               ← Entry point (CLI)
├── config.py             ← Timeouts, headers, enabled scrapers
├── requirements.txt
│
├── models/
│   └── __init__.py       ← SearchParams + Listing dataclasses
│
├── utils/
│   ├── __init__.py
│   ├── http.py           ← RateLimitedSession (requests + tenacity)
│   └── parser.py         ← parse_price, parse_int, soup(), …
│
├── scrapers/
│   ├── __init__.py       ← ALL_SCRAPERS registry
│   ├── base.py           ← BaseScraper (ABC)
│   ├── playwright_base.py← PlaywrightBaseScraper (headless browser)
│   │
│   │  ── Static HTML scrapers (requests + BeautifulSoup) ──
│   ├── shbarcelona.py
│   ├── tecnocasa.py
│   ├── housfy.py
│   ├── borsalloguers.py
│   ├── finquesteixidor.py
│   ├── finquescampanya.py
│   ├── finquesbou.py
│   ├── onixrenta.py
│   ├── dianafinques.py
│   │
│   │  ── Playwright / JS-rendered scrapers ──
│   ├── habitabarcelona.py
│   ├── monapart.py
│   ├── donpiso.py
│   ├── grocasa.py
│   ├── remax.py
│   ├── century21.py
│   ├── myspotbarcelona.py
│   ├── locabarcelona.py
│   ├── habitaclia.py
│   ├── gilamargos.py
│   ├── fincaseva.py
│   ├── selektaproperties.py
│   ├── casablau.py
│   └── finquesmarba.py
│
├── README.md
├── SITES.md              ← Status of all 23 sites
└── ARCHITECTURE.md       ← Design decisions and extension guide
```

---

## Output Format

Each result is a `Listing` object with these fields:

| Field            | Type    | Description                          |
|------------------|---------|--------------------------------------|
| `source`         | str     | Scraper name (e.g. `shbarcelona`)    |
| `url`            | str     | Canonical URL of the listing         |
| `title`          | str     | Short headline                       |
| `price`          | float   | Monthly rent in EUR (or None)        |
| `size_m2`        | float   | Surface in m² (or None)              |
| `bedrooms`       | int     | Number of bedrooms (or None)         |
| `bathrooms`      | int     | Number of bathrooms (or None)        |
| `location`       | str     | District / neighbourhood (or None)   |
| `city`           | str     | City                                 |
| `description`    | str     | Free-text description (or None)      |
| `ref`            | str     | Agency internal reference (or None)  |
| `extra`          | dict    | Site-specific extra fields           |

When `--output results.json` is used, each listing is serialised via
`Listing.as_dict()`.

---

## Adding a New Scraper

1. Create `scrapers/my_agency.py` subclassing `BaseScraper` (static HTML)
   or `PlaywrightBaseScraper` (JS site).
2. Set `name = "my_agency"` and implement `search(params) → List[Listing]`.
3. Register it in `scrapers/__init__.py` and `config.py`.

See `ARCHITECTURE.md` for full details.
