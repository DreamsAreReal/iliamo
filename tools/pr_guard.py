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

Usage (inside the PR head checkout, full history fetched):
    python3 tools/pr_guard.py --base <base sha>

Exit 0 — clean. Exit 1 — violations, one per line on stdout.
"""

from __future__ import annotations

import argparse
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


def at_base(base: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{base}:{path}"],
        capture_output=True, text=True, cwd=ROOT,
    )
    return result.stdout if result.returncode == 0 else None


def at_head(path: str) -> str | None:
    file = ROOT / path
    return file.read_text(encoding="utf-8") if file.exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base commit sha of the PR")
    args = parser.parse_args()

    violations: list[str] = []

    for path in ("app.js", "app.min.js"):
        base_text, head_text = at_base(args.base, path), at_head(path)
        if base_text is None or head_text is None:
            if base_text != head_text:
                violations.append(f"{path}: added or removed entirely")
            continue
        if normalise_js(base_text) != normalise_js(head_text):
            violations.append(f"{path}: changed beyond the ASSET_VERSION token")

    base_html, head_html = at_base(args.base, "index.html"), at_head("index.html")
    if base_html is None or head_html is None:
        if base_html != head_html:
            violations.append("index.html: added or removed entirely")
    elif normalise_scaffold(base_html) != normalise_scaffold(head_html):
        violations.append(
            "index.html: scaffold changed outside the generated menu block "
            "and the version token"
        )

    if violations:
        for violation in violations:
            print(f"PR GUARD VIOLATION: {violation}")
        return 1
    print("PR GUARD OK: generated files only changed in the generated way.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
