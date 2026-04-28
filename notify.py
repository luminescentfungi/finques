"""
notify.py — Real-time new-listing notifications.

Three channels (each can be disabled independently in config.py):
  1. Sound      — plays a .oga/.wav file or falls back to a terminal bell
  2. Desktop    — Linux libnotify (notify-send)
  3. Telegram   — sends a message via the Bot API

All calls are non-blocking and swallow errors so a notification failure
never interrupts the scraping loop.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import Listing

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_bg(fn, *args) -> None:
    """Run *fn* in a daemon thread so it never blocks the scraper."""
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()


def _sound(sound_path: str) -> None:
    try:
        if sound_path and os.path.exists(sound_path):
            # Try paplay (PulseAudio), then aplay, then mpg123
            for player, flag in [("paplay", None), ("aplay", None), ("mpg123", "-q")]:
                if subprocess.run(["which", player], capture_output=True).returncode == 0:
                    cmd = [player, sound_path] if flag is None else [player, flag, sound_path]
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
        else:
            # Terminal bell fallback
            print("\a", end="", flush=True)
    except Exception as exc:
        logger.debug("Sound notification failed: %s", exc)


def _desktop(title: str, body: str, icon: str = "dialog-information") -> None:
    try:
        subprocess.Popen(
            ["notify-send", "-i", icon, "-t", "8000", title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.debug("notify-send not available")
    except Exception as exc:
        logger.debug("Desktop notification failed: %s", exc)


def _telegram(token: str, chat_id: str, text: str) -> None:
    try:
        import urllib.request, urllib.parse, json as _json
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass  # fire-and-forget
    except Exception as exc:
        logger.debug("Telegram notification failed: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def notify_new_listings(listings: "list[Listing]", source: str) -> None:
    """
    Fire notifications for *listings* found by *source* that are new
    (already filtered — caller passes only the unique/new ones).

    Called immediately inside run_search() after each scraper returns,
    before moving to the next agency.
    """
    if not listings:
        return

    from config import (
        TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
        NOTIFICATION_SOUND,
        NOTIFY_SOUND, NOTIFY_DESKTOP, NOTIFY_TELEGRAM,
    )

    count = len(listings)
    plural = "s" if count > 1 else ""

    # Build a short desktop / sound notification
    notif_title = f"🏠 {count} new listing{plural} — {source}"
    notif_body_lines = []
    for lst in listings[:5]:  # cap at 5 lines for readability
        price = f"{lst.price:.0f} €" if lst.price else "–"
        rooms = f"{lst.bedrooms}h" if lst.bedrooms is not None else ""
        size  = f"{lst.size_m2:.0f}m²" if lst.size_m2 else ""
        meta  = "  ".join(filter(None, [price, rooms, size]))
        notif_body_lines.append(f"• {lst.title[:60]}  {meta}")
    if count > 5:
        notif_body_lines.append(f"  … and {count - 5} more")
    notif_body = "\n".join(notif_body_lines)

    # Build Telegram message (HTML, richer)
    tg_lines = [f"<b>🏠 {count} new listing{plural} from {source}</b>\n"]
    for lst in listings[:10]:
        price = f"{lst.price:.0f} €/mes" if lst.price else "–"
        rooms = f"{lst.bedrooms}h" if lst.bedrooms is not None else ""
        size  = f"{lst.size_m2:.0f}m²" if lst.size_m2 else ""
        loc   = lst.location or lst.city or ""
        meta  = "  ".join(filter(None, [price, rooms, size, loc]))
        tg_lines.append(
            f'• <a href="{lst.url}">{lst.title[:70]}</a>\n  {meta}'
        )
    if count > 10:
        tg_lines.append(f"\n… and {count - 10} more")
    tg_text = "\n".join(tg_lines)

    if NOTIFY_SOUND:
        _run_bg(_sound, NOTIFICATION_SOUND)

    if NOTIFY_DESKTOP:
        _run_bg(_desktop, notif_title, notif_body)

    if NOTIFY_TELEGRAM and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        _run_bg(_telegram, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, tg_text)
    elif NOTIFY_TELEGRAM and (not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID):
        logger.debug("Telegram notifications enabled but token/chat_id not set in config.py")
