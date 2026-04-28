"""
Central configuration for the Finques Barcelona scraper project.
Edit this file to adjust timeouts, headers, delays, and enabled scrapers.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# HTTP defaults
# ---------------------------------------------------------------------------
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,ca;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
}

REQUEST_TIMEOUT = 30          # seconds
REQUEST_DELAY = 1.5           # seconds between requests (per scraper)
MAX_RETRIES = 3
MAX_PAGES = 10                # safety cap for pagination

# ---------------------------------------------------------------------------
# Playwright / headless browser defaults
# ---------------------------------------------------------------------------
PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_TIMEOUT = 30_000   # ms

# ---------------------------------------------------------------------------
# Enabled scrapers
# Each key is the scraper module name; set to False to disable it.
# ---------------------------------------------------------------------------
ENABLED_SCRAPERS: dict[str, bool] = {
    # --- requests/BeautifulSoup based (static HTML) ---
    "shbarcelona":       True,
    "tecnocasa":         True,
    "housfy":            True,
    "borsalloguers":     True,
    "finquesteixidor":   True,
    "finquescampanya":   True,
    "finquesbou":        True,
    "onixrenta":         True,
    "dianafinques":      True,
    # --- Playwright / JS-rendered (need headless browser) ---
    "habitabarcelona":   True,
    "monapart":          True,
    "donpiso":           True,
    "grocasa":           True,
    "remax":             True,
    "century21":         True,
    "myspotbarcelona":   True,
    "locabarcelona":     True,
    "habitaclia":        True,
    "gilamargos":        False,  # temporarily disabled
    "fincaseva":         False, # temporarily disabled
    "selektaproperties": True,
    "casablau":          False,  # temporarily disabled
    "finquesmarba":      True,
    "immobarcelo":       True,
}

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
import os as _os
from dotenv import load_dotenv as _load_dotenv
_load_dotenv()  # loads .env if present; env vars set externally (CI) take precedence

# Telegram bot — set via .env locally or GitHub Secrets in CI
TELEGRAM_BOT_TOKEN: str = _os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID:   str = _os.getenv("TELEGRAM_CHAT_ID", "")

# Sound: path to a .wav/.oga file, or leave empty for a system beep
NOTIFICATION_SOUND: str = _os.getenv("NOTIFICATION_SOUND", "")

# In CI (GitHub Actions) the CI env var is automatically set to "true"
_in_ci = _os.getenv("CI", "").lower() in ("true", "1")
NOTIFY_SOUND:    bool = not _in_ci
NOTIFY_DESKTOP:  bool = not _in_ci
NOTIFY_TELEGRAM: bool = True
