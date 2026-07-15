#!/usr/bin/env python3
"""Iliamo site build step — the single command to run after editing the menu.

What it does (deterministic, no external dependencies):
  1. Loads and validates data/menu.json (the ONE source of truth for the menu).
  2. Injects the menu, minified, into the <script id="menu-data-fallback"> block
     inside index.html — this inline block is what the live site actually renders.
  3. Keeps app.min.js in sync with app.js (they must stay identical).
  4. Sets the cache-busting ASSET_VERSION in index.html, app.js and app.min.js to
     a hash of the shipped content, so browsers fetch fresh CSS / JS / images
     exactly when something actually changed (deterministic: same input -> same
     output, byte for byte).

Usage:
    python3 build.py            # build; fails loudly if the menu is broken
    python3 build.py --check    # validate + verify site is already up to date, write nothing

Exit code is non-zero on any error, so it is safe to gate a commit on it.
"""

from __future__ import annotations

import argparse
import hashlib
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
STYLES_CSS = ROOT / "styles.css"
STYLES_MIN_CSS = ROOT / "styles.min.css"
ASSETS_MENU = ROOT / "assets" / "menu"

# Prices are strictly "<integer> ₾" (e.g. "11 ₾") so reports and lints can
# always parse them.
PRICE_RE = re.compile(r"^(\d+) ₾$")

# Sane price corridor for this menu (data today: 6–34 ₾, kept with a 3x margin).
# A price outside it is most likely a typo ("110" instead of "11"); the owner
# confirms an intentional one via `"priceConfirmed": "<price>"` on the item.
PRICE_MIN, PRICE_MAX = 1, 100

# Files that carry the cache-busting token and must be bumped together.
VERSION_FILES = [INDEX_HTML, APP_JS, APP_MIN_JS]
VERSION_RE = re.compile(r"const ASSET_VERSION = '([^']+)'")
FALLBACK_RE = re.compile(
    r'(<script id="menu-data-fallback" type="application/json">)(.*?)(</script>)',
    re.S,
)

VALID_THEMES = {"drink", "food"}

# Glyphs known to app.js (productIcon); an unknown one degrades safely to the
# default glyph inside app.js, so it only warrants a warning here.
KNOWN_ICONS = {
    "beer", "bottle", "cocktail", "coffee", "drink", "food", "lemonade",
    "salad", "sauce", "shot", "soft", "soup", "tea", "wine", "wrap",
}


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


def validate_menu(menu: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Every error is "what is wrong — how to fix"."""
    errors: list[str] = []
    warnings: list[str] = []

    for key in ("brand", "categories", "sections"):
        if key not in menu:
            errors.append(
                f'missing the required top-level key "{key}" — restore it '
                "(see git history for the expected shape)"
            )
    if errors:
        return errors, warnings

    _validate_brand(menu["brand"], errors)
    categories = menu["categories"]
    sections = menu["sections"]
    if not isinstance(categories, list) or not isinstance(sections, list):
        errors.append(
            '"categories" and "sections" must both be lists — restore them '
            "from git history"
        )
        return errors, warnings

    category_ids: list[str] = []
    for cat in categories:
        if not isinstance(cat, dict):
            errors.append(f"every category must be an object, got: {cat!r}")
            continue
        cid = cat.get("id")
        if not cid or not isinstance(cid, str):
            errors.append(f'a category has no string "id": {cat!r} — add one')
            continue
        if cid in category_ids:
            errors.append(f'duplicate category id "{cid}" — remove or rename one')
        category_ids.append(cid)
        for field in ("title", "label", "icon"):
            if not cat.get(field):
                warnings.append(f'category "{cid}" is missing "{field}"')
        if cat.get("theme") not in VALID_THEMES:
            errors.append(
                f'category "{cid}": theme {cat.get("theme")!r} is invalid — '
                f"use one of {sorted(VALID_THEMES)} (it drives the page colours)"
            )
        icon = cat.get("icon")
        if isinstance(icon, str) and icon and icon not in KNOWN_ICONS:
            warnings.append(
                f'category "{cid}" icon "{icon}" is not a known glyph '
                "(the site will show the default glyph instead)"
            )

    section_ids: list[str] = []
    for sec in sections:
        if not isinstance(sec, dict):
            errors.append(f"every section must be an object, got: {sec!r}")
            continue
        sid = sec.get("id")
        if not sid or not isinstance(sid, str):
            errors.append(f'a section has no string "id": {list(sec)!r} — add one')
            continue
        if sid not in category_ids:
            errors.append(
                f'section "{sid}" has no matching category — every section id '
                "must also appear in categories (add the category or drop the section)"
            )
        if sid in section_ids:
            errors.append(f'duplicate section id "{sid}" — remove or rename one')
        section_ids.append(sid)
        if sec.get("theme") not in VALID_THEMES:
            errors.append(
                f'section "{sid}": theme {sec.get("theme")!r} is invalid — '
                f"use one of {sorted(VALID_THEMES)} (it drives the page colours)"
            )

        groups = sec.get("groups", [])
        if not isinstance(groups, list):
            errors.append(f'section "{sid}": "groups" must be a list')
            continue
        lead_names: list[str] = []
        item_count = 0
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("items", []), list):
                errors.append(
                    f'section "{sid}": every group must be an object with an '
                    f'"items" list, got: {group!r}'
                )
                continue
            items = group.get("items", [])
            if not items:
                errors.append(
                    f'section "{sid}": group "{group.get("title") or "(untitled)"}" '
                    "has no items — add items or remove the empty group"
                )
                continue
            item_count += len(items)
            # Duplicate names are checked per group: the same name in two
            # groups of one section is legitimate (e.g. draft vs bottled beer).
            seen: set[str] = set()
            for item in items:
                _validate_item(sid, item, errors, warnings)
                if isinstance(item, dict):
                    if item.get("lead"):
                        lead_names.append(str(item.get("name")))
                    item_name = item.get("name")
                    if isinstance(item_name, str):
                        if item_name in seen:
                            errors.append(
                                f'section "{sid}", group '
                                f'"{group.get("title") or "(untitled)"}" has two '
                                f'items named "{item_name}" — rename or remove one '
                                "(duplicates confuse both guests and edits)"
                            )
                        seen.add(item_name)
        if item_count == 0:
            errors.append(
                f'section "{sid}" has no items at all — add items or remove '
                "the section together with its category"
            )
        if len(lead_names) > 1:
            errors.append(
                f'section "{sid}" has {len(lead_names)} lead items '
                f'({", ".join(lead_names)}) — at most 1 is allowed, '
                'remove "lead" from the others'
            )

    for cid in category_ids:
        if cid not in section_ids:
            errors.append(
                f'category "{cid}" has a button but no section — every category '
                "id must also appear in sections (add the section or drop the category)"
            )

    # leadSections and navigation reference sections by id; a ghost id is a
    # silent no-op in the renderer, which always hides a typo — reject it.
    lead_sections = menu.get("leadSections", [])
    if not isinstance(lead_sections, list):
        errors.append('"leadSections" must be a list of section ids')
    else:
        for sid in lead_sections:
            if not isinstance(sid, str) or sid not in section_ids:
                errors.append(
                    f'"leadSections" mentions {sid!r}, but there is no such '
                    "section — fix the id or remove it"
                )
    navigation = menu.get("navigation")
    if navigation is not None:
        if not isinstance(navigation, dict):
            errors.append('"navigation" must be an object')
        else:
            initial = navigation.get("initialSection")
            if initial is not None and (
                not isinstance(initial, str) or initial not in section_ids
            ):
                errors.append(
                    f'"navigation.initialSection" is {initial!r}, but there is '
                    "no such section — fix the id or remove it"
                )

    return errors, warnings


def _validate_brand(brand: object, errors: list[str]) -> None:
    """brand.* feeds the header render in app.js; a wrong shape there kills
    the whole page (links.map on a non-list throws before anything renders)."""
    if not isinstance(brand, dict):
        errors.append('"brand" must be an object — restore it from git history')
        return
    for field in ("name", "subtitle", "logo", "siteUrl"):
        value = brand.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f'"brand.{field}" must be a string, got: {value!r}')
    logo = brand.get("logo")
    if isinstance(logo, str) and logo and not (ROOT / logo).exists():
        errors.append(
            f'"brand.logo" points at "{logo}" but that file does not exist — '
            "fix the path or add the file"
        )
    links = brand.get("links")
    if links is None:
        return
    if not isinstance(links, list):
        errors.append(
            f'"brand.links" must be a LIST of link objects, got: {links!r} — '
            "the site cannot render the header links otherwise"
        )
        return
    for link in links:
        if not isinstance(link, dict):
            errors.append(
                f'every entry of "brand.links" must be an object, got: {link!r}'
            )
            continue
        url = link.get("url")
        if not url or not isinstance(url, str):
            errors.append(
                f'a brand link has no string "url": {link!r} — add the address'
            )
        elif not url.startswith(("https://", "http://")):
            errors.append(
                f'a brand link url must start with http(s)://, got: "{url}" — '
                "javascript:/data: and other schemes are not allowed"
            )
        if not isinstance(link.get("icon") or link.get("id"), str):
            errors.append(
                f'a brand link needs a string "icon" or "id": {link!r}'
            )
        label = link.get("label")
        if label is not None and not isinstance(label, str):
            errors.append(f'"label" of a brand link must be a string, got: {label!r}')


def _validate_item(
    section_id: str, item: dict, errors: list[str], warnings: list[str]
) -> None:
    if not isinstance(item, dict):
        errors.append(f'section "{section_id}": every item must be an object, got: {item!r}')
        return
    name = item.get("name")
    if not name or not isinstance(name, str):
        errors.append(
            f'an item in section "{section_id}" has no name: {item!r} — add "name"'
        )
        return
    if any(ord(ch) < 32 for ch in name) or "<" in name or ">" in name:
        errors.append(
            f'item name {name!r} in section "{section_id}" contains HTML or '
            "control characters — use plain text only"
        )
    for field in ("desc", "icon", "image"):
        value = item.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f'"{name}": "{field}" must be a string, got: {value!r}')
    if item.get("lead") is not None and not isinstance(item["lead"], bool):
        errors.append(f'"{name}": "lead" must be true or false, got: {item["lead"]!r}')
    icon = item.get("icon")
    if isinstance(icon, str) and icon and icon not in KNOWN_ICONS:
        warnings.append(
            f'"{name}" icon "{icon}" is not a known glyph '
            "(the site will show the default glyph instead)"
        )
    price = item.get("price")
    if price is not None:
        if not isinstance(price, str) or not PRICE_RE.match(price):
            errors.append(
                f'"{name}": price {price!r} is not in the "N ₾" format — '
                'write it like "11 ₾" (integer, space, ₾)'
            )
        else:
            value = int(PRICE_RE.match(price).group(1))
            confirmed = item.get("priceConfirmed")
            if not (PRICE_MIN <= value <= PRICE_MAX) and confirmed != price:
                errors.append(
                    f'"{name}": price "{price}" is outside the sane range '
                    f"{PRICE_MIN}–{PRICE_MAX} ₾ — probably a typo; if it is "
                    "really intended, the owner must confirm it explicitly and "
                    f'then set "priceConfirmed": "{price}" on this item'
                )
    image = item.get("image")
    if image:
        path = ROOT / str(image)
        if not path.exists():
            errors.append(
                f'"{name}" points at image "{image}" but that file does not exist — '
                f"add the photo to {ASSETS_MENU.relative_to(ROOT)}/ first"
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
    """Content hash of the shipped assets: same input -> same version.

    The version token itself lives inside the hashed files, so hashing them
    literally would make the version depend on itself and never converge.
    Instead the token (and the generated menu block in index.html) is
    normalised to a placeholder before hashing; app.min.js is a byte copy of
    app.js after the build, so hashing normalised app.js is equivalent to
    hashing the normalised shipped file (spike S2 / ADR-0002).

    The index.html scaffold (everything outside the generated menu block) is
    part of the hash on purpose: a manual edit of index.html that is not
    followed by `python3 build.py` makes ASSET_VERSION stale, which --check
    reports as an error (M1-R1 finding).
    """
    hasher = hashlib.sha256()
    hasher.update(MENU_JSON.read_bytes())
    hasher.update((ROOT / "styles.min.css").read_bytes())
    js_text = APP_JS.read_text(encoding="utf-8")
    js_normalised = VERSION_RE.sub("const ASSET_VERSION = 'X'", js_text)
    hasher.update(js_normalised.encode("utf-8"))
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    token = VERSION_RE.search(html_text)
    if token:
        html_text = html_text.replace(token.group(1), "X")
    html_scaffold = FALLBACK_RE.sub(r"\1X\3", html_text, count=1)
    hasher.update(html_scaffold.encode("utf-8"))
    return hasher.hexdigest()[:10]


def current_version() -> str:
    match = VERSION_RE.search(INDEX_HTML.read_text(encoding="utf-8"))
    if not match:
        raise BuildError("index.html: could not find ASSET_VERSION — restore the token")
    return match.group(1)


def css_fingerprint(text: str) -> str:
    """CSS text reduced to a comparable fingerprint.

    styles.min.css is styles.css minus comments, whitespace and optional
    semicolons before "}" (verified byte-level against the shipped files), so
    applying the same reduction to BOTH files must yield identical strings.
    The fingerprint is only ever compared, never served.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"\s+", "", text)
    return text.replace(";}", "}")


def check_styles_fresh(errors: list[str]) -> None:
    for path in (STYLES_CSS, STYLES_MIN_CSS):
        if not path.exists():
            errors.append(f"{path.name}: file is missing — restore it from git history")
            return
    if css_fingerprint(STYLES_CSS.read_text(encoding="utf-8")) != css_fingerprint(
        STYLES_MIN_CSS.read_text(encoding="utf-8")
    ):
        errors.append(
            "styles.min.css: content differs from styles.css (ignoring comments "
            "and whitespace) — the site ships styles.min.css, so re-minify it "
            "from styles.css or revert the stray edit"
        )


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build(check_only: bool) -> int:
    menu = load_menu()
    errors, warnings = validate_menu(menu)
    errors = [f"data/menu.json: {e}" for e in errors]
    for warning in warnings:
        print(f"  warning: {warning}")
    check_styles_fresh(errors)

    html = INDEX_HTML.read_text(encoding="utf-8")
    if not FALLBACK_RE.search(html):
        errors.append(
            'index.html: could not find the <script id="menu-data-fallback"> '
            "block — restore it from git history"
        )
    if errors:
        raise BuildError("\n" + "\n".join(f"  - {e}" for e in errors))

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
        stale: list[str] = []
        if FALLBACK_RE.search(html).group(2) != payload:
            stale.append(
                "index.html: inlined menu does not match data/menu.json — "
                "run `python3 build.py` before committing"
            )
        if js_out_of_sync:
            stale.append(
                "app.min.js: not a byte copy of app.js — "
                "run `python3 build.py` before committing"
            )
        expected_version = new_version()
        if old_version != expected_version:
            stale.append(
                f"index.html: ASSET_VERSION '{old_version}' does not match the "
                f"content hash '{expected_version}' — run `python3 build.py` "
                "before committing"
            )
        for path in (APP_JS, APP_MIN_JS):
            match = VERSION_RE.search(path.read_text(encoding="utf-8"))
            if not match or match.group(1) != old_version:
                stale.append(
                    f"{path.name}: ASSET_VERSION does not match index.html — "
                    "run `python3 build.py` before committing"
                )
        if stale:
            print("OUT OF DATE:")
            for line in stale:
                print(f"  - {line}")
            return 1
        print("OK: menu, ASSET_VERSION, app.min.js and styles.min.css are up to date.")
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
