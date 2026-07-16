#!/usr/bin/env python3
"""Strip metadata from owner-uploaded menu photos and convert them to webp.

The owner uploads photos straight to `assets/menu/` (direct push to main, see
ADR-0003 / the owner guide). The repository is public, so camera EXIF — GPS in
particular — must not stay there, and raw jpg/HEIC also bloat the page. This
tool rewrites every menu photo that is not yet a clean webp into a stripped
webp, keeping the pixels and dropping ALL metadata (Pillow simply does not
copy EXIF unless asked to), then updates any `data/menu.json` reference from
`<name>.<ext>` to `<name>.webp` so the site keeps pointing at the file.

A photo is "already processed" iff it is webp AND carries no EXIF — those are
skipped, so a re-run is a no-op (the anti-loop marker; the CI job also relies
on GITHUB_TOKEN bot pushes not re-triggering workflows).

Usage:
    python3 tools/photo_process.py [--check] [path ...]

Without paths it scans all of `assets/menu/`. `--check` reports what WOULD be
processed and exits non-zero if anything needs processing, without writing —
used to prove idempotence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

try:  # HEIC (iPhone default) support is optional; register if available.
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC = True
except Exception:  # pragma: no cover - depends on the environment
    HEIC = False

ROOT = Path(__file__).resolve().parent.parent
MENU_DIR = ROOT / "assets" / "menu"
MENU_JSON = ROOT / "data" / "menu.json"
WEBP_QUALITY = 82
WEBP_METHOD = 6


def has_metadata(path: Path) -> bool:
    """True when the image carries any EXIF block (camera info, GPS, ...)."""
    try:
        exif = Image.open(path).getexif()
    except Exception:
        return False
    return len(dict(exif)) > 0


def is_clean_webp(path: Path) -> bool:
    """The anti-loop marker: a webp with no EXIF is already processed."""
    if path.suffix.lower() != ".webp":
        return False
    try:
        img = Image.open(path)
    except Exception:
        return False
    return img.format == "WEBP" and not has_metadata(path)


def needs_processing(path: Path) -> bool:
    return path.is_file() and not is_clean_webp(path)


def process_one(path: Path) -> Path:
    """Rewrite `path` as a stripped webp; return the resulting webp path.

    Pillow writes no EXIF unless an exif= argument is passed, so saving the
    RGB pixels into a fresh webp is metadata-free by construction (verified:
    the resulting image has zero EXIF keys and no GPS). The original non-webp
    file is removed once the webp exists.
    """
    with Image.open(path) as src:
        src.load()
        rgb = src.convert("RGB")

    webp_path = path.with_suffix(".webp")
    rgb.save(webp_path, "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    if path.suffix.lower() != ".webp" and path.exists():
        path.unlink()
    return webp_path


def rewrite_menu_reference(old_rel: str, new_rel: str) -> bool:
    """Point any menu.json image reference from old_rel to new_rel.

    Returns True when the file changed. Uses a plain text replacement so the
    JSON formatting (indentation, key order) is preserved byte-for-byte apart
    from the reference itself.
    """
    if old_rel == new_rel or not MENU_JSON.exists():
        return False
    text = MENU_JSON.read_text(encoding="utf-8")
    needle = f'"{old_rel}"'
    if needle not in text:
        return False
    MENU_JSON.write_text(text.replace(needle, f'"{new_rel}"'), encoding="utf-8")
    return True


def collect_targets(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(p) if Path(p).is_absolute() else ROOT / p for p in paths]
    if not MENU_DIR.is_dir():
        return []
    return sorted(p for p in MENU_DIR.iterdir() if p.is_file())


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report what would be processed, write nothing")
    parser.add_argument("paths", nargs="*",
                        help="specific files (default: all of assets/menu/)")
    args = parser.parse_args()

    targets = [p for p in collect_targets(args.paths) if needs_processing(p)]

    if args.check:
        for p in targets:
            print(f"WOULD PROCESS: {rel(p)}")
        if targets:
            print(f"{len(targets)} photo(s) need processing")
            return 1
        print("all menu photos are clean webp (nothing to process)")
        return 0

    if not targets:
        print("nothing to process")
        return 0

    # Process per file: one unreadable / non-image file must not abort the run
    # and strand valid photos beside it. A skipped file stays in the tree as-is
    # (build.py --check still governs whether a referenced image is valid).
    done = 0
    skipped: list[str] = []
    for path in targets:
        old_rel = rel(path)
        try:
            webp = process_one(path)
        except Exception as exc:  # noqa: BLE001 - report and continue
            skipped.append(old_rel)
            print(f"WARNING: skipped {old_rel} \u2014 not a usable image ({exc})")
            continue
        new_rel = rel(webp)
        changed_ref = rewrite_menu_reference(old_rel, new_rel)
        note = " (menu.json reference updated)" if changed_ref else ""
        print(f"processed: {old_rel} -> {new_rel}{note}")
        done += 1

    print(f"processed {done} photo(s), skipped {len(skipped)}; HEIC support: {HEIC}")
    # Success as long as we did not crash: skipped files are reported, not fatal.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
