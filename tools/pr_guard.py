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
        for name in sorted(changed_item_names(args.base, args.head)):
            if name not in body:
                violations.append(
                    f'report does not mention the changed item "{name}"'
                )

    if violations:
        for violation in violations:
            print(f"PR GUARD VIOLATION: {violation}")
        return 1
    print("PR GUARD OK: generated files only changed in the generated way.")
    return 0


def item_index(commit: str) -> dict[tuple[str, str, str], str] | None:
    """Map (section id, group title, item name) -> canonical item JSON."""
    raw = at_commit(commit, "data/menu.json")
    if raw is None:
        return None
    try:
        menu = json.loads(raw)
    except json.JSONDecodeError:
        return None
    index: dict[tuple[str, str, str], str] = {}
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
                    index[key] = json.dumps(item, ensure_ascii=False, sort_keys=True)
    return index


def changed_item_names(base: str, head: str) -> set[str]:
    """Names of menu items added, removed or modified between two commits.

    The report==diff rule (G8): every one of these names must appear in the
    PR body, otherwise the owner cannot see what actually changed.
    """
    base_items, head_items = item_index(base), item_index(head)
    if base_items is None or head_items is None:
        return set()  # unparseable side: build-check rejects the PR anyway
    changed: set[str] = set()
    for key in base_items.keys() | head_items.keys():
        if base_items.get(key) != head_items.get(key):
            changed.add(key[2])
    return changed


if __name__ == "__main__":
    raise SystemExit(main())
