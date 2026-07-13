#!/usr/bin/env python3
"""Iliamo site build step — the single command to run after editing the menu.

What it does (deterministic, no external dependencies):
  1. Loads and validates data/menu.json (the ONE source of truth for the menu).
  2. Injects the menu, minified, into the <script id="menu-data-fallback"> block
     inside index.html — this inline block is what the live site actually renders.
  3. Keeps app.min.js in sync with app.js (they must stay identical).
  4. Bumps the cache-busting ASSET_VERSION in index.html, app.js and app.min.js so
     browsers fetch the fresh CSS / JS / images instead of a stale cached copy.

Usage:
    python3 build.py            # build; fails loudly if the menu is broken
    python3 build.py --check    # validate + verify site is already up to date, write nothing

Exit code is non-zero on any error, so it is safe to gate a commit on it.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MENU_JSON = ROOT / "data" / "menu.json"
INDEX_HTML = ROOT / "index.html"
APP_JS = ROOT / "app.js"
APP_MIN_JS = ROOT / "app.min.js"
ASSETS_MENU = ROOT / "assets" / "menu"

# Files that carry the cache-busting token and must be bumped together.
VERSION_FILES = [INDEX_HTML, APP_JS, APP_MIN_JS]
VERSION_RE = re.compile(r"const ASSET_VERSION = '([^']+)'")
FALLBACK_RE = re.compile(
    r'(<script id="menu-data-fallback" type="application/json">)(.*?)(</script>)',
    re.S,
)

VALID_THEMES = {"drink", "food"}


class BuildError(Exception):
    """A problem that must stop the build (broken menu, missing photo, ...)."""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def load_menu() -> dict:
    if not MENU_JSON.exists():
        raise BuildError(f"{MENU_JSON} not found")
    raw = MENU_JSON.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BuildError(
            f"data/menu.json is not valid JSON: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno}). "
            "A common cause is a missing comma or an extra comma before } or ]."
        ) from exc


def validate_menu(menu: dict) -> list[str]:
    """Return a list of non-fatal warnings. Raise BuildError on fatal problems."""
    warnings: list[str] = []

    for key in ("brand", "categories", "sections"):
        if key not in menu:
            raise BuildError(f'menu.json is missing the required top-level key "{key}"')

    categories = menu["categories"]
    sections = menu["sections"]
    if not isinstance(categories, list) or not isinstance(sections, list):
        raise BuildError('"categories" and "sections" must both be lists')

    category_ids: list[str] = []
    for cat in categories:
        cid = cat.get("id")
        if not cid:
            raise BuildError(f"a category has no id: {cat!r}")
        if cid in category_ids:
            raise BuildError(f'duplicate category id "{cid}"')
        category_ids.append(cid)
        for field in ("title", "label", "icon"):
            if not cat.get(field):
                warnings.append(f'category "{cid}" is missing "{field}"')
        if cat.get("theme") not in VALID_THEMES:
            warnings.append(
                f'category "{cid}" has theme "{cat.get("theme")}" '
                f"(expected one of {sorted(VALID_THEMES)})"
            )

    section_ids: list[str] = []
    for sec in sections:
        sid = sec.get("id")
        if not sid:
            raise BuildError(f"a section has no id: {sec!r}")
        if sid not in category_ids:
            raise BuildError(
                f'section "{sid}" has no matching category — every section id '
                "must also appear in categories"
            )
        section_ids.append(sid)
        for group in sec.get("groups", []):
            for item in group.get("items", []):
                _validate_item(sid, item, warnings)

    for cid in category_ids:
        if cid not in section_ids:
            warnings.append(f'category "{cid}" has a button but no section with items')

    return warnings


def _validate_item(section_id: str, item: dict, warnings: list[str]) -> None:
    name = item.get("name")
    if not name:
        raise BuildError(f'an item in section "{section_id}" has no name: {item!r}')
    price = item.get("price")
    if price is not None and not any(ch.isdigit() for ch in str(price)):
        warnings.append(f'"{name}" has a price "{price}" with no number in it')
    image = item.get("image")
    if image:
        path = ROOT / image
        if not path.exists():
            raise BuildError(
                f'"{name}" points at image "{image}" but that file does not exist. '
                f"Add the photo to {ASSETS_MENU.relative_to(ROOT)}/ first."
            )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def inline_json(menu: dict) -> str:
    """Compact JSON, safe to embed inside an HTML <script> tag."""
    compact = json.dumps(menu, ensure_ascii=False, separators=(",", ":"))
    # Escape "<" so a value can never accidentally close the <script> element.
    return compact.replace("<", "\\u003c")


def new_version() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def current_version() -> str:
    match = VERSION_RE.search(INDEX_HTML.read_text(encoding="utf-8"))
    if not match:
        raise BuildError("could not find ASSET_VERSION in index.html")
    return match.group(1)


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build(check_only: bool) -> int:
    menu = load_menu()
    warnings = validate_menu(menu)
    for warning in warnings:
        print(f"  warning: {warning}")

    html = INDEX_HTML.read_text(encoding="utf-8")
    if not FALLBACK_RE.search(html):
        raise BuildError(
            'could not find the <script id="menu-data-fallback"> block in index.html'
        )

    payload = inline_json(menu)
    old_payload = FALLBACK_RE.search(html).group(2)
    new_html = FALLBACK_RE.sub(
        lambda m: m.group(1) + payload + m.group(3), html, count=1
    )

    old_version = current_version()
    version = old_version if check_only else new_version()
    if not check_only:
        new_html = new_html.replace(old_version, version)

    menu_changed = payload != old_payload
    js_out_of_sync = (
        not APP_MIN_JS.exists()
        or APP_MIN_JS.read_bytes() != APP_JS.read_bytes()
    )

    if check_only:
        # In check mode we ignore the version (kept equal above): report only
        # whether the rendered menu or the js mirror are stale.
        stale = FALLBACK_RE.search(html).group(2) != payload
        if stale or js_out_of_sync:
            print("OUT OF DATE: run `python3 build.py` before committing.")
            return 1
        print("OK: index.html menu and app.min.js are up to date.")
        return 0

    INDEX_HTML.write_text(new_html, encoding="utf-8")

    if js_out_of_sync:
        shutil.copyfile(APP_JS, APP_MIN_JS)
    # Bump the version token inside the js files too (mirror already copied).
    for path in (APP_JS, APP_MIN_JS):
        text = path.read_text(encoding="utf-8")
        bumped = text.replace(old_version, version)
        if bumped != text:
            path.write_text(bumped, encoding="utf-8")

    print(f"built: menu inlined into index.html, cache version -> {version}")
    if menu_changed:
        print("       (menu content changed)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Iliamo menu site.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate and report staleness without writing any files",
    )
    args = parser.parse_args()
    try:
        return build(check_only=args.check)
    except BuildError as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
