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
    return p.parse_args()


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def run_search(args: argparse.Namespace) -> List[Listing]:
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    params = SearchParams(
        city=args.city,
        district=args.district,
        min_price=args.min_price,
        max_price=args.max_price,
        min_rooms=args.min_rooms,
        max_rooms=args.max_rooms,
        min_size=args.min_size,
        max_size=args.max_size,
        property_type=args.property_type,
        max_pages=args.max_pages,
    )

    # Determine which scrapers to run
    if args.scrapers:
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
            notify_new_listings(unique, scraper.name)
        except Exception as exc:
            console.print(f"  [red]{scraper.name:25s} ERROR: {exc}[/red]")

    _save_scraped(new_urls)
    if new_urls:
        console.print(f"  [dim]→ {len(new_urls)} URL(s) appended to {SCRAPED_FILE}[/dim]")

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
        console.print(
            f"[bold cyan]🔁  Loop mode — polling every {args.loop_interval}s "
            f"(Ctrl+C to stop)[/bold cyan]"
        )
        try:
            while True:
                run_search(args)
                time.sleep(args.loop_interval)
        except KeyboardInterrupt:
            console.print("\n[yellow]Loop stopped.[/yellow]")
        return

    results = run_search(args)
    display_results(results, args)

    if args.output:
        save_results(results, args.output)

    if args.send:
        run_send(results)


if __name__ == "__main__":
    main()
