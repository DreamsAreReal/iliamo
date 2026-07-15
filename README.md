# Iliamo Menu


Static single-page menu for **Iliamo Kitchen & Bar**, published at
https://www.iliamo.bar via Cloudflare Pages. No backend, no framework — plain HTML,
CSS and JavaScript.

## Editing the menu

**`data/menu.json` is the single source of truth for all menu content.** After editing
it you must run the build, which renders the menu into `index.html` and bumps the cache
version:

```
python3 build.py            # build after any menu change (required)
python3 build.py --check    # validate + verify nothing is stale (used in CI/pre-commit)
```

The site renders from an inline `<script id="menu-data-fallback">` block inside
`index.html` that `build.py` generates from `data/menu.json`. Editing `menu.json`
without running the build has **no effect** on the live site.

Data shape (`data/menu.json`):
- `categories` — order, labels and icons of the section buttons;
- `sections` — sections, groups, items, prices, descriptions and photos;
- `brand.links` — social / map links in the header (`icon` picks the glyph);
- `leadSections` — sections allowed to show a large lead card;
- `lead: true` on an item — which item becomes that lead card;
- `image` on an item — path to a photo in `assets/menu/`.

See **AGENTS.md** for the full schema and the exact edit → build → publish workflow
(this repository is set up so a non-technical owner can make menu changes through
Codex; the owner-facing guide is **КАК-МЕНЯТЬ-САЙТ.md**).

## Publishing

Push to the default branch. Cloudflare Pages is connected to this repository and
redeploys `iliamo.bar` automatically (no build command; the site is served as static
files from the repository root).

## Local preview

```
python3 server.py           # serves the site at http://localhost:8000/ with gzip + cache headers
```

Also handy for a local Lighthouse run.





