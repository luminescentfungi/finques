"""
bot.py — Telegram bot command listener for the Finques scraper.

Runs in a background thread while the main scraping loop is active.
Uses long-polling (no webhook needed) against the Telegram Bot API.

Supported commands
------------------
/help            — list all commands
/status          — current iteration, running/paused state
/args            — show active search parameters
/list            — list enabled agencies for this run
/remove <name>   — disable agency for next iterations
/add <name>      — re-enable agency for next iterations
/agencies        — list ALL known agencies and their on/off state
/max-price <n>   — change max rent filter
/min-price <n>   — change min rent filter
/max-rooms <n>   — change max rooms filter
/min-rooms <n>   — change min rooms filter
/max-size <n>    — change max size (m²) filter
/min-size <n>    — change min size (m²) filter
/district <name> — change district filter  (/district clear → remove filter)
/type <type>     — change property type (piso/casa/local/parking/oficina/any)
/interval <s>    — change loop interval in seconds
/pause           — pause after the current iteration finishes
/resume          — resume a paused loop
/stop            — stop the loop gracefully after current iteration
/clear-seen      — forget all previously-seen URLs (scraped.txt)
/reload          — reload ENABLED_SCRAPERS from config.py
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state (modified by bot thread, read by main loop thread)
# ---------------------------------------------------------------------------

@dataclass
class BotState:
    """
    Thread-safe container for runtime state shared between the main scraping
    loop and the Telegram bot listener.

    The main loop reads `paused`, `stopped`, `loop_interval` and `active_scrapers`
    on every iteration; the bot thread mutates them.
    All attribute access is protected by `lock`.
    """
    # Concurrency
    lock: threading.Lock = field(default_factory=threading.Lock)

    # Control flags
    paused:  bool = False
    stopped: bool = False

    # Search parameters (mirrors argparse.Namespace fields)
    max_price:     Optional[int] = None
    min_price:     Optional[int] = None
    max_rooms:     Optional[int] = None
    min_rooms:     Optional[int] = None
    max_size:      Optional[int] = None
    min_size:      Optional[int] = None
    district:      Optional[str] = None
    property_type: str           = "piso"
    max_pages:     int           = 5
    loop_interval: int           = 5

    # Active scrapers — set of name strings; None means "use config defaults"
    active_scrapers: Optional[Set[str]] = None

    # Progress counters (written by main loop)
    iteration:       int = 0
    last_new_count:  int = 0
    total_new_count: int = 0

    # All known scraper names (populated at startup)
    all_scrapers: Set[str] = field(default_factory=set)

    def snapshot(self) -> dict:
        """Return a plain-dict snapshot (safe to use outside the lock)."""
        with self.lock:
            return {
                "paused":        self.paused,
                "stopped":       self.stopped,
                "max_price":     self.max_price,
                "min_price":     self.min_price,
                "max_rooms":     self.max_rooms,
                "min_rooms":     self.min_rooms,
                "max_size":      self.max_size,
                "min_size":      self.min_size,
                "district":      self.district,
                "property_type": self.property_type,
                "max_pages":     self.max_pages,
                "loop_interval": self.loop_interval,
                "active_scrapers": (
                    sorted(self.active_scrapers)
                    if self.active_scrapers is not None else None
                ),
                "iteration":       self.iteration,
                "last_new_count":  self.last_new_count,
                "total_new_count": self.total_new_count,
                "all_scrapers":    sorted(self.all_scrapers),
            }


# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------

_BASE = "https://api.telegram.org/bot{token}/{method}"


def _api(token: str, method: str, **kwargs) -> dict:
    url  = _BASE.format(token=token, method=method)
    data = urllib.parse.urlencode(kwargs).encode()
    req  = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.debug("Telegram API %s error: %s", method, exc)
        return {}


def _send(token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> None:
    _api(
        token, "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        disable_web_page_preview="true",
    )


def _get_updates(token: str, offset: int, timeout: int = 25) -> list:
    resp = _api(
        token, "getUpdates",
        offset=offset,
        timeout=timeout,
        allowed_updates='["message"]',
    )
    return resp.get("result", [])


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

_HELP_TEXT = """\
<b>🤖 Finques bot commands</b>

<b>Info</b>
/help — this message
/status — loop progress and state
/args — current search filters
/list — enabled agencies
/agencies — all agencies with on/off state

<b>Agencies</b>
/add &lt;name&gt; — enable agency
/remove &lt;name&gt; — disable agency
/reload — reload enabled list from config.py

<b>Filters</b>
/max-price &lt;€&gt;
/min-price &lt;€&gt;
/max-rooms &lt;n&gt;
/min-rooms &lt;n&gt;
/max-size &lt;m²&gt;
/min-size &lt;m²&gt;
/district &lt;name|clear&gt;
/type &lt;piso|casa|local|parking|oficina|any&gt;

<b>Loop control</b>
/interval &lt;seconds&gt;
/pause — pause after current iteration
/resume — resume a paused loop
/stop — stop the loop after current iteration
/clear-seen — forget all already-seen URLs
"""


def _handle(token: str, chat_id: str, text: str, state: BotState) -> None:
    """Dispatch a single command and reply."""
    parts = text.strip().split()
    if not parts:
        return
    cmd = parts[0].lower().lstrip("/").split("@")[0]  # strip bot username suffix
    args = parts[1:]

    # ------------------------------------------------------------------ info
    if cmd == "help":
        _send(token, chat_id, _HELP_TEXT)

    elif cmd == "status":
        s = state.snapshot()
        state_str = "⏸ paused" if s["paused"] else ("🛑 stopped" if s["stopped"] else "▶ running")
        msg = (
            f"<b>🔄 Loop status</b>\n"
            f"State       : {state_str}\n"
            f"Iteration   : {s['iteration']}\n"
            f"New (last)  : {s['last_new_count']}\n"
            f"New (total) : {s['total_new_count']}\n"
            f"Interval    : {s['loop_interval']} s"
        )
        _send(token, chat_id, msg)

    elif cmd == "args":
        s = state.snapshot()
        def fmt(v, suffix=""): return f"{v}{suffix}" if v is not None else "–"
        msg = (
            f"<b>🔧 Search parameters</b>\n"
            f"City        : Barcelona\n"
            f"District    : {fmt(s['district'])}\n"
            f"Min price   : {fmt(s['min_price'], ' €')}\n"
            f"Max price   : {fmt(s['max_price'], ' €')}\n"
            f"Min rooms   : {fmt(s['min_rooms'])}\n"
            f"Max rooms   : {fmt(s['max_rooms'])}\n"
            f"Min size    : {fmt(s['min_size'], ' m²')}\n"
            f"Max size    : {fmt(s['max_size'], ' m²')}\n"
            f"Type        : {s['property_type']}\n"
            f"Max pages   : {s['max_pages']}"
        )
        _send(token, chat_id, msg)

    elif cmd == "list":
        s = state.snapshot()
        scrapers = s["active_scrapers"] if s["active_scrapers"] is not None else s["all_scrapers"]
        if not scrapers:
            _send(token, chat_id, "No active agencies.")
        else:
            lines = "\n".join(f"  • {n}" for n in sorted(scrapers))
            _send(token, chat_id, f"<b>✅ Active agencies ({len(scrapers)})</b>\n{lines}")

    elif cmd == "agencies":
        s = state.snapshot()
        active = set(s["active_scrapers"]) if s["active_scrapers"] is not None else set(s["all_scrapers"])
        if not s["all_scrapers"]:
            _send(token, chat_id, "No agencies loaded yet.")
            return
        lines = []
        for n in sorted(s["all_scrapers"]):
            icon = "✅" if n in active else "❌"
            lines.append(f"  {icon} {n}")
        _send(token, chat_id, f"<b>🏢 All agencies</b>\n" + "\n".join(lines))

    # -------------------------------------------------------------- agencies
    elif cmd == "add":
        if not args:
            _send(token, chat_id, "Usage: /add &lt;agency_name&gt;")
            return
        name = args[0].lower()
        with state.lock:
            if name not in state.all_scrapers:
                _send(token, chat_id, f"❌ Unknown agency: <code>{name}</code>\nSend /agencies for the full list.")
                return
            if state.active_scrapers is None:
                state.active_scrapers = set(state.all_scrapers)
            state.active_scrapers.add(name)
        _send(token, chat_id, f"✅ <code>{name}</code> added to active agencies.")

    elif cmd == "remove":
        if not args:
            _send(token, chat_id, "Usage: /remove &lt;agency_name&gt;")
            return
        name = args[0].lower()
        with state.lock:
            if state.active_scrapers is None:
                state.active_scrapers = set(state.all_scrapers)
            if name not in state.active_scrapers:
                _send(token, chat_id, f"ℹ️ <code>{name}</code> is already disabled (or unknown).")
                return
            state.active_scrapers.discard(name)
        _send(token, chat_id, f"🗑 <code>{name}</code> removed from active agencies.")

    elif cmd == "reload":
        from config import ENABLED_SCRAPERS
        with state.lock:
            state.active_scrapers = {n for n, on in ENABLED_SCRAPERS.items() if on}
        _send(token, chat_id, "🔄 Active agencies reloaded from config.py.")

    # --------------------------------------------------------------- filters
    elif cmd in ("max-price", "min-price", "max-rooms", "min-rooms",
                 "max-size",  "min-size"):
        if not args:
            _send(token, chat_id, f"Usage: /{cmd} &lt;number&gt;")
            return
        try:
            val = int(args[0])
        except ValueError:
            _send(token, chat_id, "❌ Value must be an integer.")
            return
        attr = cmd.replace("-", "_")
        with state.lock:
            setattr(state, attr, val)
        units = {"max_price": "€", "min_price": "€",
                 "max_size": "m²", "min_size": "m²"}.get(attr, "")
        _send(token, chat_id, f"✅ <b>{cmd}</b> set to <code>{val}{units}</code>")

    elif cmd == "district":
        if not args:
            _send(token, chat_id, "Usage: /district &lt;name&gt;  or  /district clear")
            return
        val = None if args[0].lower() == "clear" else " ".join(args)
        with state.lock:
            state.district = val
        if val:
            _send(token, chat_id, f"✅ District set to <code>{val}</code>")
        else:
            _send(token, chat_id, "✅ District filter cleared.")

    elif cmd == "type":
        valid = {"piso", "casa", "local", "parking", "oficina", "any"}
        if not args or args[0].lower() not in valid:
            _send(token, chat_id, f"Usage: /type &lt;{'|'.join(sorted(valid))}&gt;")
            return
        with state.lock:
            state.property_type = args[0].lower()
        _send(token, chat_id, f"✅ Property type set to <code>{args[0].lower()}</code>")

    # -------------------------------------------------------------- control
    elif cmd == "interval":
        if not args:
            _send(token, chat_id, "Usage: /interval &lt;seconds&gt;")
            return
        try:
            val = int(args[0])
            if val < 1:
                raise ValueError
        except ValueError:
            _send(token, chat_id, "❌ Value must be a positive integer.")
            return
        with state.lock:
            state.loop_interval = val
        _send(token, chat_id, f"✅ Loop interval set to <code>{val}s</code>")

    elif cmd == "pause":
        with state.lock:
            state.paused = True
        _send(token, chat_id, "⏸ Loop will pause after the current iteration.")

    elif cmd in ("resume", "start"):
        with state.lock:
            state.paused = False
            state.stopped = False
        _send(token, chat_id, "▶ Loop resumed.")

    elif cmd == "stop":
        with state.lock:
            state.stopped = True
        _send(token, chat_id, "🛑 Loop will stop after the current iteration.")

    elif cmd == "clear-seen":
        import os
        try:
            open("scraped.txt", "w").close()
            _send(token, chat_id, "🗑 scraped.txt cleared — all URLs will be re-fetched.")
        except Exception as exc:
            _send(token, chat_id, f"❌ Could not clear scraped.txt: {exc}")

    else:
        _send(token, chat_id, f"❓ Unknown command: <code>/{cmd}</code>\nSend /help for the list.")


# ---------------------------------------------------------------------------
# Listener thread
# ---------------------------------------------------------------------------

class TelegramBotListener(threading.Thread):
    """
    Long-polls the Telegram Bot API in a background daemon thread.

    Parameters
    ----------
    token        : Bot token from BotFather.
    chat_id      : The chat ID to send replies to (same as notify.py uses).
    state        : Shared BotState instance.
    allowed_ids  : Optional set of integer user IDs that may send commands.
                   When empty/None, all users who message the bot are accepted.
    poll_timeout : Long-poll timeout in seconds (must be ≤ 50 for Telegram).
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        state: BotState,
        allowed_ids: Optional[Set[int]] = None,
        poll_timeout: int = 25,
    ):
        super().__init__(daemon=True, name="TelegramBotListener")
        self.token       = token
        self.chat_id     = chat_id
        self.state       = state
        self.allowed_ids = set(allowed_ids) if allowed_ids else set()
        self.poll_timeout = poll_timeout
        self._offset     = 0
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    def run(self) -> None:
        logger.info("TelegramBotListener started (long-poll timeout=%ds)", self.poll_timeout)
        _send(self.token, self.chat_id,
              "🤖 <b>Finques bot online.</b> Send /help for commands.")

        while not self._stop_event.is_set():
            try:
                updates = _get_updates(self.token, self._offset, self.poll_timeout)
            except Exception as exc:
                logger.debug("getUpdates error: %s", exc)
                time.sleep(5)
                continue

            for upd in updates:
                self._offset = upd["update_id"] + 1
                try:
                    self._process(upd)
                except Exception as exc:
                    logger.debug("Update processing error: %s", exc)

        logger.info("TelegramBotListener stopped.")

    # ------------------------------------------------------------------
    def _process(self, upd: dict) -> None:
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return
        text = msg.get("text", "")
        if not text.startswith("/"):
            return  # ignore non-command messages

        from_user = msg.get("from", {})
        user_id   = from_user.get("id")
        username  = from_user.get("username", str(user_id))
        reply_chat = str(msg["chat"]["id"])

        if self.allowed_ids and user_id not in self.allowed_ids:
            logger.debug("Rejected command from unauthorized user %s", user_id)
            _send(self.token, reply_chat,
                  "⛔ You are not authorised to control this bot.")
            return

        logger.info("Bot command from @%s: %s", username, text.split()[0])
        _handle(self.token, reply_chat, text, self.state)
