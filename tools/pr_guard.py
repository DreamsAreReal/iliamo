#!/usr/bin/env python3
"""Diff guard for the automerge workflow: generated files must change only
in the generated way.

Auto-merge is allowed when, compared to the PR base:
  * app.js and app.min.js differ ONLY in the ASSET_VERSION token;
  * the index.html scaffold — everything outside the generated
    menu-data-fallback block and the version token — is identical.

Everything else in the allowlist is policed elsewhere: data/menu.json by
build.py --check, styles.min.css by the freshness fingerprint (styles.css
itself is outside the allowlist), assets by the photo existence check.

The script runs from a TRUSTED checkout (the PR base, i.e. main) and reads
both sides via `git show`, so PR content is data only and can never replace
the guard that judges it.

Usage (both commits fetched into the local repository):
    python3 tools/pr_guard.py --base <base sha> --head <head sha>

Exit 0 — clean. Exit 1 — violations, one per line on stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r"const ASSET_VERSION = '([^']+)'")
FALLBACK_RE = re.compile(
    r'(<script id="menu-data-fallback" type="application/json">)(.*?)(</script>)',
    re.S,
)


def normalise_js(text: str) -> str:
    return VERSION_RE.sub("const ASSET_VERSION = 'X'", text)


def normalise_scaffold(text: str) -> str:
    token = VERSION_RE.search(text)
    if token:
        text = text.replace(token.group(1), "X")
    return FALLBACK_RE.sub(r"\1X\3", text, count=1)


def at_commit(commit: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        capture_output=True, text=True, cwd=ROOT,
    )
    return result.stdout if result.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base commit sha of the PR")
    parser.add_argument("--head", required=True, help="head commit sha of the PR")
    parser.add_argument(
        "--body-file",
        default=None,
        help="file with the PR body; when given, every changed menu item name "
        "must be mentioned there (the report==diff enforcement, G8)",
    )
    args = parser.parse_args()

    violations: list[str] = []

    for path in ("app.js", "app.min.js"):
        base_text = at_commit(args.base, path)
        head_text = at_commit(args.head, path)
        if base_text is None or head_text is None:
            if base_text != head_text:
                violations.append(f"{path}: added or removed entirely")
            continue
        if normalise_js(base_text) != normalise_js(head_text):
            violations.append(f"{path}: changed beyond the ASSET_VERSION token")

    base_html = at_commit(args.base, "index.html")
    head_html = at_commit(args.head, "index.html")
    if base_html is None or head_html is None:
        if base_html != head_html:
            violations.append("index.html: added or removed entirely")
    elif normalise_scaffold(base_html) != normalise_scaffold(head_html):
        violations.append(
            "index.html: scaffold changed outside the generated menu block "
            "and the version token"
        )

    if args.body_file is not None:
        body = Path(args.body_file).read_text(encoding="utf-8")
        for name, old_price, new_price in changed_item_records(args.base, args.head):
            if name not in body:
                violations.append(
                    f'report does not mention the changed item "{name}"'
                )
                continue
            if old_price == new_price:
                continue  # price untouched (desc/photo edit): nothing to verify

            # W2-F1: the price change must be reported SEMANTICALLY, not just
            # mentioned. Find the report line(s) that name this item and check
            # that one of them states the REAL old and new values with the
            # was/now markers. A fabricated old value is a violation even if
            # the real one appears somewhere else in the body.
            lines = [ln for ln in body.splitlines() if name in ln]
            if reports_price_change(lines, old_price, new_price):
                continue
            violations.append(
                f'report does not state the real price change of "{name}"'
                + describe_expected(old_price, new_price)
            )

    if violations:
        for violation in violations:
            print(f"PR GUARD VIOLATION: {violation}")
        return 1
    print("PR GUARD OK: generated files only changed in the generated way.")
    return 0


def item_index(commit: str) -> dict[tuple[str, str, str], dict] | None:
    """Map (section id, group title, item name) -> the item object."""
    raw = at_commit(commit, "data/menu.json")
    if raw is None:
        return None
    try:
        menu = json.loads(raw)
    except json.JSONDecodeError:
        return None
    index: dict[tuple[str, str, str], dict] = {}
    for section in menu.get("sections", []):
        if not isinstance(section, dict):
            continue
        for group in section.get("groups", []) or []:
            if not isinstance(group, dict):
                continue
            for item in group.get("items", []) or []:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    key = (
                        str(section.get("id")),
                        str(group.get("title")),
                        item["name"],
                    )
                    index[key] = item
    return index


def changed_item_records(
    base: str, head: str
) -> list[tuple[str, str | None, str | None]]:
    """(name, old price, new price) for every item added, removed or modified.

    The report==diff rule (G8): every changed item name must appear in the PR
    body, and when the price changed, BOTH real price values must appear too —
    otherwise the owner cannot tell an accurate report from a hallucinated one
    (a fabricated old price passed the name-only check, found in review M3-R1).
    """
    base_items, head_items = item_index(base), item_index(head)
    if base_items is None or head_items is None:
        return []  # unparseable side: build-check rejects the PR anyway
    records: list[tuple[str, str | None, str | None]] = []
    for key in sorted(base_items.keys() | head_items.keys()):
        old_item, new_item = base_items.get(key), head_items.get(key)
        old_canon = json.dumps(old_item, ensure_ascii=False, sort_keys=True)
        new_canon = json.dumps(new_item, ensure_ascii=False, sort_keys=True)
        if old_canon != new_canon:
            records.append(
                (
                    key[2],
                    old_item.get("price") if old_item else None,
                    new_item.get("price") if new_item else None,
                )
            )
    return records


def normalise_price(price: str | None) -> str | None:
    """Canonical `N ₾` form: collapse any run of whitespace (incl. the Unicode
    no-break space U+00A0 and narrow no-break U+202F) to one ASCII space.

    build.py --check already rejects prices that are not `N ₾`, so a changed
    price here is well-formed; this only neutralises spacing variants so the
    body may be written with a plain or a no-break space.
    """
    if price is None:
        return None
    return re.sub(r"\s+", " ", price.replace("\u00a0", " ").replace("\u202f", " ")).strip()


def price_in_line(price: str, line: str) -> bool:
    """True when the (normalised) price occurs in the line as a standalone
    value — a lookbehind stops `9 ₾` matching inside `19 ₾`."""
    norm_price = normalise_price(price)
    norm_line = re.sub(r"[\u00a0\u202f]", " ", line)
    return re.search(rf"(?<!\d){re.escape(norm_price)}", norm_line) is not None


# Report vocabulary lives in a JSON data resource, not in code, because the
# product language is Russian and the guard must match the exact words of the
# status-panel report the owner reads. WAS marks the previous value, NOW the
# resulting value, ARROW separates them in the bullet.
_MARKERS = json.loads(
    (ROOT / "tools" / "report_markers.json").read_text(encoding="utf-8")
)
WAS: str = _MARKERS["was"]
NOW: str = _MARKERS["now"]
ARROW: str = _MARKERS["arrow"]


def reports_price_change(
    lines: list[str], old_price: str | None, new_price: str | None
) -> bool:
    """True when one report line for this item states the real change.

    - both prices present (a real change): the line must carry the real old
      value after the WAS marker and the real new value after the NOW marker,
      in that order;
    - added item (no old price): the line must carry the real new value;
    - removed item (no new price): the line must carry the real old value.
    """
    for line in lines:
        if old_price is not None and new_price is not None:
            if not (price_in_line(old_price, line) and price_in_line(new_price, line)):
                continue
            # Order guard: the old value must read as the previous one and the
            # new as the result, so a swapped bullet cannot pass off a rise as
            # a cut.
            if _ordered_change(line, old_price, new_price):
                return True
        elif new_price is not None:  # addition
            if price_in_line(new_price, line):
                return True
        elif old_price is not None:  # removal
            if price_in_line(old_price, line):
                return True
    return False


def _ordered_change(line: str, old_price: str, new_price: str) -> bool:
    """The old price is stated as the previous value and the new as the result.

    Accepts the canonical WAS <old> ARROW NOW <new> bullet and the tolerant
    <old> ARROW <new> (old before the arrow, new after it)."""
    norm = re.sub(r"[\u00a0\u202f]", " ", line)
    old_n, new_n = normalise_price(old_price), normalise_price(new_price)

    was_m = re.search(rf"{re.escape(WAS)}\s+{re.escape(old_n)}", norm)
    now_m = re.search(rf"{re.escape(NOW)}\s+{re.escape(new_n)}", norm)
    if was_m and now_m and was_m.start() < now_m.start():
        return True

    arrow = norm.find(ARROW)
    if arrow == -1:
        return False
    before, after = norm[:arrow], norm[arrow:]
    old_before = re.search(rf"(?<!\d){re.escape(old_n)}", before) is not None
    new_after = re.search(rf"(?<!\d){re.escape(new_n)}", after) is not None
    return old_before and new_after


def describe_expected(old_price: str | None, new_price: str | None) -> str:
    old_n, new_n = normalise_price(old_price), normalise_price(new_price)
    if old_n is not None and new_n is not None:
        return f" (expected {_MARKERS['was']} {old_n} {_MARKERS['arrow']} {_MARKERS['now']} {new_n})"
    if new_n is not None:
        return f" (expected the new price {new_n})"
    if old_n is not None:
        return f" (expected the old price {old_n})"
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
