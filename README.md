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

Publication goes through a pull request into `main` — never push to `main`
directly (`main` is protected by the required `check` and `guard` statuses;
direct pushes bypass the pre-merge safety net and are rolled back by the
push-watchdog workflow when red).

The delivery pipeline (see `.github/workflows/`):

- **build-check** — runs `python3 build.py --check` on every PR and on every
  push to `main`; a red check cannot merge.
- **automerge** — the trusted judge (`pull_request_target`, executes from the
  base branch): menu-content PRs from `codex/*` branches that pass the diff
  guard (`tools/pr_guard.py`, including the report==diff body check) are
  merged automatically; anything touching code, styles source or workflows
  waits for the owner. It also dispatches the post-merge smoke and deletes
  the merged branch.
- **smoke** — after each deploy, verifies that production serves exactly what
  `main` holds (byte-for-byte); on failure prepares a revert PR.
- **push-watchdog** — direct pushes to `main` (admin bypass): green ones get
  the smoke, red ones get an automatic revert PR.

Cloudflare Pages is connected to this repository and redeploys `iliamo.bar`
on every change of `main` (no build command; the site is served as static
files from the repository root). Every PR branch gets a preview at
`https://<branch>.aspen-bar.pages.dev` (with `/` replaced by `-`).

## Local preview

```
python3 server.py           # serves the site at http://localhost:8000/ with gzip + cache headers
```

Also handy for a local Lighthouse run.



