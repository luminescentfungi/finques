#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py – Single entry point to search ALL (or selected) Barcelona rental sites.

Usage examples
--------------
# Search all sites, pisos, max 1200 €/mes
python main.py --max-price 1200 --type piso

# Search only static-HTML scrapers, 2+ rooms
python main.py --min-rooms 2 --no-js

# Search specific scrapers
python main.py --scrapers shbarcelona,tecnocasa --max-price 1000

# Save results to JSON
python main.py --max-price 900 --output results.json

# Print help
python main.py --help
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import List

from rich.console import Console
from rich.table import Table
from rich.progress import track

from models import SearchParams, Listing, ContactInfo, RequestResult
from scrapers import ALL_SCRAPERS
from config import ENABLED_SCRAPERS
from requester import send_request
from notify import notify_new_listings
from bot import BotState, TelegramBotListener

SCRAPED_FILE = "scraped.txt"


def _load_scraped() -> set:
    """Load the set of already-seen URLs from SCRAPED_FILE."""
    try:
        with open(SCRAPED_FILE, encoding="utf-8") as fh:
            return {line.strip() for line in fh if line.strip()}
    except FileNotFoundError:
        return set()


def _save_scraped(urls: set) -> None:
    """Append *urls* (only new ones) to SCRAPED_FILE."""
    existing = _load_scraped()
    new_urls = sorted(urls - existing)
    if new_urls:
        with open(SCRAPED_FILE, "a", encoding="utf-8") as fh:
            for url in new_urls:
                fh.write(url + "\n")

console = Console()
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Search Barcelona rental listings across multiple agencies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--city",       default="Barcelona",  help="City (default: Barcelona)")
    p.add_argument("--district",                         help="Neighbourhood / district filter")
    p.add_argument("--min-price",  type=int,             help="Minimum monthly rent (€)")
    p.add_argument("--max-price",  type=int,             help="Maximum monthly rent (€)")
    p.add_argument("--min-rooms",  type=int,             help="Minimum number of bedrooms")
    p.add_argument("--max-rooms",  type=int,             help="Maximum number of bedrooms")
    p.add_argument("--min-size",   type=int,             help="Minimum surface (m²)")
    p.add_argument("--max-size",   type=int,             help="Maximum surface (m²)")
    p.add_argument(
        "--type", dest="property_type", default="piso",
        choices=["piso", "casa", "local", "parking", "oficina", "any"],
        help="Property type (default: piso)",
    )
    p.add_argument("--max-pages",  type=int, default=5,  help="Max pages to fetch per site")
    p.add_argument(
        "--scrapers", default=None,
        help="Comma-separated list of scraper names to use (default: all enabled)",
    )
    p.add_argument(
        "--no-js", action="store_true",
        help="Skip Playwright/JS scrapers (faster, no headless browser needed)",
    )
    p.add_argument(
        "--output", default=None,
        help="Save results to a JSON file",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging",
    )
    p.add_argument(
        "--list-scrapers", action="store_true",
        help="Print available scraper names and exit",
    )
    p.add_argument(
        "--send", action="store_true", default=False,
        help="Automatically submit a rental enquiry for each result using contact_info.json",
    )
    p.add_argument(
        "--loop", action="store_true", default=False,
        help="Run search repeatedly every 5 s, notifying on new results only (disables RESULT.md and --send)",
    )
    p.add_argument(
        "--loop-interval", type=int, default=5, metavar="SECONDS",
        help="Seconds between loop iterations (default: 5, only used with --loop)",
    )
    p.add_argument(
        "--max-runtime", type=int, default=0, metavar="MINUTES",
        help="Exit the loop after this many minutes (0 = run forever, default: 0)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def run_search(args: argparse.Namespace, state: "BotState | None" = None) -> List[Listing]:
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # When a BotState is active, its values override the CLI args for this iteration
    if state is not None:
        with state.lock:
            state.iteration += 1
            _max_price     = state.max_price     if state.max_price     is not None else args.max_price
            _min_price     = state.min_price     if state.min_price     is not None else args.min_price
            _max_rooms     = state.max_rooms     if state.max_rooms     is not None else args.max_rooms
            _min_rooms     = state.min_rooms     if state.min_rooms     is not None else args.min_rooms
            _max_size      = state.max_size      if state.max_size      is not None else args.max_size
            _min_size      = state.min_size      if state.min_size      is not None else args.min_size
            _district      = state.district      if state.district      is not None else args.district
            _property_type = state.property_type
            _max_pages     = state.max_pages
            _active_scrapers = (
                list(state.active_scrapers)
                if state.active_scrapers is not None else None
            )
    else:
        _max_price     = args.max_price
        _min_price     = args.min_price
        _max_rooms     = args.max_rooms
        _min_rooms     = args.min_rooms
        _max_size      = args.max_size
        _min_size      = args.min_size
        _district      = args.district
        _property_type = args.property_type
        _max_pages     = args.max_pages
        _active_scrapers = None

    params = SearchParams(
        city=args.city,
        district=_district,
        min_price=_min_price,
        max_price=_max_price,
        min_rooms=_min_rooms,
        max_rooms=_max_rooms,
        min_size=_min_size,
        max_size=_max_size,
        property_type=_property_type,
        max_pages=_max_pages,
    )

    # Determine which scrapers to run
    if _active_scrapers is not None:
        selected = _active_scrapers
    elif args.scrapers:
        selected = [s.strip() for s in args.scrapers.split(",")]
    else:
        selected = [name for name, enabled in ENABLED_SCRAPERS.items() if enabled]

    active: list = []
    for name in selected:
        cls = ALL_SCRAPERS.get(name)
        if cls is None:
            console.print(f"[yellow]⚠  Unknown scraper '{name}' – skipped[/yellow]")
            continue
        scraper = cls()
        if args.no_js and scraper.uses_js:
            continue
        active.append(scraper)

    if not active:
        console.print("[red]No scrapers to run.[/red]")
        return []

    console.print(
        f"\n[bold cyan]🔍  Searching {len(active)} site(s)[/bold cyan] "
        f"· city=[green]{params.city}[/green]"
        + (f"  district=[green]{params.district}[/green]" if params.district else "")
        + (f"  max=[green]{params.max_price}€[/green]" if params.max_price else "")
        + (f"  min=[green]{params.min_price}€[/green]" if params.min_price else "")
        + (f"  rooms≥[green]{params.min_rooms}[/green]" if params.min_rooms else "")
        + f"  type=[green]{params.property_type}[/green]\n"
    )

    already_scraped: set = _load_scraped()
    all_results: List[Listing] = []
    seen_urls: set = set(already_scraped)  # dedup: persistent + within this run
    new_urls: set = set()
    for scraper in track(active, description="Scraping…", console=console):
        try:
            listings = scraper.search(params)
            if not isinstance(listings, list):
                listings = []
            unique = [l for l in listings if l.url not in seen_urls]
            seen_urls.update(l.url for l in unique)
            new_urls.update(l.url for l in unique)
            all_results.extend(unique)
            skipped = len(listings) - len(unique)
            console.print(
                f"  [dim]{scraper.name:25s}[/dim] → "
                f"[bold]{len(unique):3d}[/bold] new"
                + (f"  [dim]({skipped} already seen)[/dim]" if skipped else "")
            )
            try:
                notify_new_listings(unique, scraper.name)
            except Exception as notify_exc:
                logger.warning("Notification error for %s: %s", scraper.name, notify_exc)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            console.print(f"  [red]{scraper.name:25s} ERROR: {exc}[/red]")
            logger.exception("Scraper %s raised an unhandled exception", scraper.name)

    _save_scraped(new_urls)
    if new_urls:
        console.print(f"  [dim]→ {len(new_urls)} URL(s) appended to {SCRAPED_FILE}[/dim]")

    if state is not None:
        with state.lock:
            state.last_new_count   = len(new_urls)
            state.total_new_count += len(new_urls)

    return all_results


def display_results(results: List[Listing], params: argparse.Namespace) -> None:
    from datetime import datetime

    md_path = "RESULT.md"

    lines: List[str] = []
    lines.append(f"# Search Results\n")
    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n")

    # Search parameters summary
    filters = []
    filters.append(f"city: **{params.city}**")
    if params.district:
        filters.append(f"district: **{params.district}**")
    if params.min_price:
        filters.append(f"min-price: **{params.min_price} €**")
    if params.max_price:
        filters.append(f"max-price: **{params.max_price} €**")
    if params.min_rooms:
        filters.append(f"min-rooms: **{params.min_rooms}**")
    if params.max_rooms:
        filters.append(f"max-rooms: **{params.max_rooms}**")
    if params.min_size:
        filters.append(f"min-size: **{params.min_size} m²**")
    if params.max_size:
        filters.append(f"max-size: **{params.max_size} m²**")
    filters.append(f"type: **{params.property_type}**")
    lines.append("**Filters:** " + "  |  ".join(filters) + "\n")

    if not results:
        lines.append("\n_No listings found._\n")
    else:
        lines.append(f"**{len(results)} listings found** (sorted by price)\n")
        lines.append("")
        lines.append("| Source | Title | Price €/mo | Rooms | m² | Location | URL |")
        lines.append("|--------|-------|-----------|-------|----|----------|-----|")
        for lst in sorted(results, key=lambda x: (x.price or 999999)):
            source   = lst.source or "–"
            title    = (lst.title or "–").replace("|", "\\|")
            price    = f"{lst.price:.0f}" if lst.price else "–"
            rooms    = str(lst.bedrooms) if lst.bedrooms is not None else "–"
            size     = f"{lst.size_m2:.0f}" if lst.size_m2 else "–"
            location = (lst.location or lst.city or "–").replace("|", "\\|")
            url      = f"[link]({lst.url})" if lst.url else "–"
            lines.append(f"| {source} | {title} | {price} | {rooms} | {size} | {location} | {url} |")

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    console.print(f"\n[green]✔  Results written to {md_path}[/green] ({len(results)} listings)")


def save_results(results: List[Listing], path: str) -> None:
    data = [r.as_dict() for r in results]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    console.print(f"\n[green]✔  Results saved to {path}[/green]")


def run_send(results: List[Listing]) -> List[RequestResult]:
    """Submit rental enquiries for all *results* and return a list of RequestResult."""
    from datetime import datetime

    try:
        contact = ContactInfo.load()
    except FileNotFoundError:
        console.print(
            "[red]contact_info.json not found — cannot send requests.[/red]\n"
            "Create it with your name, email, phone_full and phone_local."
        )
        return []

    console.print(
        f"\n[bold cyan]📨  Sending enquiries for {len(results)} listing(s)[/bold cyan] "
        f"as [green]{contact.name}[/green] <{contact.email}>\n"
    )

    send_results: List[RequestResult] = []
    icons = {"sent": "✅", "captcha": "🔒", "manual": "📋",
             "playwright_required": "🎭", "not_implemented": "❓", "error": "❌"}

    for listing in track(results, description="Sending…", console=console):
        result = send_request(listing, contact)
        send_results.append(result)
        icon = icons.get(result.status, "❓")
        colour = "green" if result.success else ("yellow" if result.status in ("captcha", "manual", "playwright_required") else "red")
        console.print(
            f"  {icon} [{colour}]{result.source:22s}[/{colour}] "
            f"{result.status:22s} {result.message[:80]}"
        )

    # Summary
    sent  = sum(1 for r in send_results if r.success)
    skips = len(send_results) - sent
    console.print(
        f"\n[bold]Send summary:[/bold] "
        f"[green]{sent} sent[/green]  [yellow]{skips} skipped/manual[/yellow]"
    )

    # Save JSON log
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f"send_log_{ts}.json"
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump([r.as_dict() for r in send_results], fh, ensure_ascii=False, indent=2)
    console.print(f"[green]✔  Send log saved to {log_path}[/green]")

    return send_results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.list_scrapers:
        console.print("\n[bold]Available scrapers:[/bold]")
        for name, cls in ALL_SCRAPERS.items():
            tag = "[yellow]JS[/yellow]" if cls.uses_js else "[green]HTTP[/green]"
            enabled = "✔" if ENABLED_SCRAPERS.get(name) else "✗"
            console.print(f"  {enabled}  {tag}  {name}")
        sys.exit(0)

    if args.loop:
        import time
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ALLOWED_USERS

        # Initialise shared state from CLI defaults
        state = BotState(
            max_price     = args.max_price,
            min_price     = args.min_price,
            max_rooms     = args.max_rooms,
            min_rooms     = args.min_rooms,
            max_size      = args.max_size,
            min_size      = args.min_size,
            district      = args.district,
            property_type = args.property_type,
            max_pages     = args.max_pages,
            loop_interval = args.loop_interval,
            all_scrapers  = set(ALL_SCRAPERS.keys()),
        )

        # Compute deadline (0 = no limit)
        deadline: float = (
            time.monotonic() + args.max_runtime * 60
            if args.max_runtime > 0 else float("inf")
        )

        # Start the Telegram bot listener if credentials are available
        bot_listener = None
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            bot_listener = TelegramBotListener(
                token       = TELEGRAM_BOT_TOKEN,
                chat_id     = TELEGRAM_CHAT_ID,
                state       = state,
                allowed_ids = TELEGRAM_ALLOWED_USERS,
            )
            bot_listener.start()
            console.print(
                "[bold green]🤖  Telegram bot listener started[/bold green] "
                "(send /help in your chat)"
            )
        else:
            console.print(
                "[yellow]⚠  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — "
                "bot listener disabled[/yellow]"
            )

        runtime_msg = (
            f"{args.max_runtime} min limit"
            if args.max_runtime > 0 else "no time limit"
        )
        console.print(
            f"[bold cyan]🔁  Loop mode — polling every {args.loop_interval}s, "
            f"{runtime_msg} (Ctrl+C to stop)[/bold cyan]"
        )
        try:
            while True:
                # --- runtime deadline ---
                if time.monotonic() >= deadline:
                    console.print(
                        f"[yellow]⏱  Max runtime ({args.max_runtime} min) reached — exiting cleanly.[/yellow]"
                    )
                    break

                with state.lock:
                    _stopped = state.stopped
                    _paused  = state.paused

                if _stopped:
                    console.print("[yellow]🛑  Stop requested via bot.[/yellow]")
                    break
                if _paused:
                    console.print("[dim]⏸  Paused — waiting for /resume …[/dim]")
                    time.sleep(2)
                    continue

                # --- robust iteration: never let a crash kill the loop ---
                try:
                    run_search(args, state=state)
                except KeyboardInterrupt:
                    raise
                except Exception as iter_exc:
                    console.print(f"[red]❌  Iteration error (will retry next cycle): {iter_exc}[/red]")
                    logger.exception("Unhandled error in run_search iteration")

                with state.lock:
                    _interval = state.loop_interval

                # Sleep in small chunks so we can respect deadline / stop flag
                slept = 0
                while slept < _interval:
                    if time.monotonic() >= deadline:
                        break
                    with state.lock:
                        if state.stopped:
                            break
                    time.sleep(min(2, _interval - slept))
                    slept += 2

        except KeyboardInterrupt:
            console.print("\n[yellow]Loop stopped.[/yellow]")
        finally:
            if bot_listener:
                bot_listener.stop()
        return

    results = run_search(args)
    display_results(results, args)

    if args.output:
        save_results(results, args.output)

    if args.send:
        run_send(results)


if __name__ == "__main__":
    main()
