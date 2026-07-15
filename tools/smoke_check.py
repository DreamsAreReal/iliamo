#!/usr/bin/env python3
"""Post-deploy smoke check: production must serve exactly what main holds.

Compares the production index.html byte-for-byte (sha256) with the local
checkout and, for a precise error message, also compares the inlined menu
block against data/menu.json. A plain HTTP 200 proves nothing here: the
Cloudflare Pages project has no 404.html, so ANY path answers 200 with
index.html (SPA fallback, verified live during F5).

Production lags a merge by ~30 s, so the check retries before failing.

Usage:
    python3 tools/smoke_check.py --url https://www.iliamo.bar
    python3 tools/smoke_check.py --url ... --expect-sha256 <hex>   # test injection

Exit code: 0 — production matches, 1 — it does not (or never answered).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FALLBACK_RE = re.compile(
    r'<script id="menu-data-fallback" type="application/json">(.*?)</script>',
    re.S,
)


# Cloudflare Web Analytics injects this <script> into HTML responses served
# to clients that ask for text/html; it is provider noise, not our content.
BEACON_RE = re.compile(
    rb'<script[^>]*src="https://static\.cloudflareinsights\.com/[^"]*"[^>]*>'
    rb"</script>\n?"
)


def fetch(url: str) -> bytes:
    # Verified live: no User-Agent -> Cloudflare answers 403; an Accept header
    # of text/html (or none) -> Cloudflare injects the analytics beacon.
    # "Accept: */*" returns the file exactly as deployed.
    request = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "User-Agent": "iliamo-smoke/1.0",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def menu_payload_from_source() -> str:
    """The exact string build.py inlines into index.html (same algorithm)."""
    menu = json.loads((ROOT / "data" / "menu.json").read_text(encoding="utf-8"))
    compact = json.dumps(menu, ensure_ascii=False, separators=(",", ":"))
    return compact.replace("<", "\\u003c")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="production URL to check")
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--delay", type=float, default=15.0)
    parser.add_argument(
        "--expect-sha256",
        default=None,
        help="override the expected index.html sha256 (used to TEST the failure "
        "path without touching production)",
    )
    args = parser.parse_args()

    expected = args.expect_sha256 or hashlib.sha256(
        (ROOT / "index.html").read_bytes()
    ).hexdigest()
    print(f"expected index.html sha256: {expected}")

    body = b""
    got = "(no successful response)"
    for attempt in range(1, args.attempts + 1):
        try:
            body = fetch(args.url)
            got = hashlib.sha256(body).hexdigest()
        except OSError as exc:
            got = f"(request failed: {exc})"
        print(f"attempt {attempt}/{args.attempts}: production sha256: {got}")
        if got == expected:
            print("SMOKE OK: production matches the repository byte for byte.")
            return 0
        if body and hashlib.sha256(BEACON_RE.sub(b"", body)).hexdigest() == expected:
            print("SMOKE OK: production matches the repository after stripping "
                  "the Cloudflare analytics beacon (provider-injected script).")
            return 0
        if attempt < args.attempts:
            time.sleep(args.delay)

    print("SMOKE FAILED: production does not match the repository.")
    if not body:
        print("  detail: production never answered successfully")
        return 1
    match = FALLBACK_RE.search(body.decode("utf-8", errors="replace"))
    if match is None:
        print("  detail: production HTML has no menu-data-fallback block at all")
    elif match.group(1) != menu_payload_from_source():
        print("  detail: the menu served on production differs from data/menu.json")
    else:
        print("  detail: menu block matches; the difference is outside the menu "
              "(scaffold/assets version)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
