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
        records = changed_item_records(args.base, args.head)

        # Every changed item name must be mentioned at all.
        for name, old_price, new_price in records:
            if name not in body:
                violations.append(
                    f'report does not mention the changed item "{name}"'
                )

        # W2-F1: the price changes must be reported TRUTHFULLY. It is not enough
        # that the real values appear somewhere — no CONFLICTING price may sit
        # next to the item either (evaluator bypass R1/R2/R3: a fabricated value
        # beside the honest one used to pass). Records that share a name (two
        # items with the same name in different groups) are checked together:
        # each real price change needs its own report line, and no report line
        # for that name may carry a price outside the real values.
        by_name: dict[str, list[tuple[str | None, str | None]]] = {}
        for name, old_price, new_price in records:
            if old_price == new_price:
                continue  # price untouched (desc/photo edit): nothing to verify
            by_name.setdefault(name, []).append(
                (normalise_price(old_price), normalise_price(new_price))
            )
        for name, changes in by_name.items():
            if name not in body:
                continue  # already reported as a missing-name violation above
            violations.extend(price_report_problems(body, name, changes))

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
    body, and when the price changed, the report must state the real values —
    otherwise the owner cannot tell an accurate report from a hallucinated one
    (a fabricated price passed weaker checks, found in reviews M3-R1 / W2-F1).
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
    """Canonical price form: collapse any run of whitespace (incl. the Unicode
    no-break space U+00A0 and narrow no-break U+202F) to one ASCII space.

    build.py --check already rejects prices not in the `N <currency>` format,
    so a changed price here is well-formed; this only neutralises spacing
    variants so the body may use a plain or a no-break space.
    """
    if price is None:
        return None
    collapsed = price.replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", collapsed).strip()


# Report vocabulary lives in a JSON data resource, not in code, because the
# product language is Russian and the guard must match the exact words and the
# currency sign of the status-panel report the owner reads. WAS marks the
# previous value, NOW the resulting value, ARROW separates them, CURRENCY is
# the lari sign that terminates every price token.
_MARKERS = json.loads(
    (ROOT / "tools" / "report_markers.json").read_text(encoding="utf-8")
)
WAS: str = _MARKERS["was"]
NOW: str = _MARKERS["now"]
ARROW: str = _MARKERS["arrow"]
CURRENCY: str = _MARKERS["currency"]

PRICE_TOKEN_RE = re.compile(rf"(?<!\d)(\d+)\s*{re.escape(CURRENCY)}")


def _norm(text: str) -> str:
    return re.sub(r"[  ]", " ", text)


def price_tokens(text: str) -> list[str]:
    """Every standalone `<number> <currency>` price, in order of appearance.

    A lookbehind stops a shorter number matching inside a longer one (the tail
    of 19 is not read as 9)."""
    return [f"{m.group(1)} {CURRENCY}" for m in PRICE_TOKEN_RE.finditer(_norm(text))]


def item_price_lines(body: str, name: str) -> list[str]:
    """Report lines that name the item AND carry at least one price token.

    HTML comments are dropped first: the truth must be VISIBLE to the owner, so
    a real value hidden in a comment does not excuse a lie in the visible line
    (evaluator cross-bypass)."""
    visible = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    return [
        ln for ln in visible.splitlines()
        if name in ln and PRICE_TOKEN_RE.search(_norm(ln))
    ]


def _line_matches_change(line: str, old_n: str | None, new_n: str | None) -> bool:
    """The line reports exactly this one change, truthfully and in order.

    Its price tokens must be exactly {old, new} for a change (old before new),
    just [new] for an addition, or just [old] for a removal — no extra price.
    """
    tokens = price_tokens(line)
    if old_n is not None and new_n is not None:
        if old_n == new_n or sorted(tokens) != sorted([old_n, new_n]):
            return False
        norm = _norm(line)
        return norm.find(old_n) < norm.find(new_n)
    if new_n is not None:  # addition
        return tokens == [new_n]
    if old_n is not None:  # removal
        return tokens == [old_n]
    return False


def price_report_problems(
    body: str,
    name: str,
    changes: list[tuple[str | None, str | None]],
) -> list[str]:
    """Violations for every price change of items sharing this name.

    Conjunctive truthfulness (evaluator R1/R2/R3): each real change needs its
    own report line whose price tokens are EXACTLY its real values in the right
    order; and NO price line for this name may carry a value outside the real
    set — a fabricated 15/20, a hallucinated chain, or a "still 20" aside.
    """
    problems: list[str] = []
    real_values = {v for old, new in changes for v in (old, new) if v is not None}
    lines = item_price_lines(body, name)

    # (1) No line for this name may show a price outside the real values.
    if any(tok not in real_values for line in lines for tok in price_tokens(line)):
        problems.append(
            f'report shows a price that is not a real value of "{name}"'
        )

    # (2) Each real change must be reported on exactly one dedicated line.
    used: set[int] = set()
    for old_n, new_n in changes:
        matched = next(
            (i for i, line in enumerate(lines)
             if i not in used and _line_matches_change(line, old_n, new_n)),
            None,
        )
        if matched is None:
            problems.append(
                f'report does not truthfully state the price change of "{name}"'
                + describe_expected(old_n, new_n)
            )
        else:
            used.add(matched)

    # (3) No leftover price line for this name beyond the real changes
    # (a duplicate/conflicting bullet the checks above did not consume).
    if len(lines) > len(changes):
        problems.append(f'report has an extra price line for "{name}"')

    return problems


def describe_expected(old_price: str | None, new_price: str | None) -> str:
    old_n, new_n = normalise_price(old_price), normalise_price(new_price)
    if old_n is not None and new_n is not None:
        return f" (expected {WAS} {old_n} {ARROW} {NOW} {new_n})"
    if new_n is not None:
        return f" (expected the new price {new_n})"
    if old_n is not None:
        return f" (expected the old price {old_n})"
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
