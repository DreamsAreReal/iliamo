#!/usr/bin/env bash
# Corruption harness for `python3 build.py --check`.
#
# Each case copies the pristine site into a temp dir, applies exactly one
# corruption there (the working tree is never touched), runs the check and
# expects: non-zero exit AND the offending file named in the output.
#
# Adding a case (e.g. a held-out one) takes two steps:
#   1. write a `corrupt_<name>` function that breaks the copy in "$1";
#   2. append "<name>|<file the error must mention>" to the CASES list.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ---------------------------------------------------------------------------
# Corruptions (every function gets the case dir as $1)
# ---------------------------------------------------------------------------

corrupt_broken_json() {  # invalid JSON: double comma
  python3 - "$1" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
p.write_text(p.read_text(encoding="utf-8").replace(",", ",,", 1), encoding="utf-8")
EOF
}

corrupt_price_no_lari() {  # price loses the " ₾" suffix
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
for sec in menu["sections"]:
    for gr in sec.get("groups", []):
        for it in gr.get("items", []):
            if it.get("price"):
                it["price"] = it["price"].split()[0]  # "8 ₾" -> "8"
                p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
                raise SystemExit(0)
EOF
}

corrupt_category_without_section() {  # category id with no matching section
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
menu["categories"].append({"id": "ghost", "title": "GHOST", "label": "Ghost",
                           "theme": "food", "icon": "beer"})
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

corrupt_two_leads() {  # two lead items in one section
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
for sec in menu["sections"]:
    items = [it for gr in sec.get("groups", []) for it in gr.get("items", [])]
    if len(items) >= 2:
        items[0]["lead"] = True
        items[1]["lead"] = True
        break
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

corrupt_broken_photo() {  # item points at a photo that does not exist
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
for sec in menu["sections"]:
    for gr in sec.get("groups", []):
        for it in gr.get("items", []):
            it["image"] = "assets/menu/no-such-photo.webp"
            p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
            raise SystemExit(0)
EOF
}

corrupt_stale_index() {  # menu.json edited, index.html not rebuilt
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
for sec in menu["sections"]:
    for gr in sec.get("groups", []):
        for it in gr.get("items", []):
            if it.get("price"):
                n = int(it["price"].split()[0])
                it["price"] = f"{n + 1} ₾"
                p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
                raise SystemExit(0)
EOF
}

corrupt_stale_app_min() {  # app.min.js drifts away from app.js
  printf '\n// stray manual edit\n' >> "$1/app.min.js"
}

corrupt_manual_index_edit() {  # index.html edited outside the generated block, no rebuild
  printf '<!-- stray manual edit -->\n' >> "$1/index.html"
}

corrupt_stale_styles_min() {  # styles.css edited, styles.min.css not re-minified
  python3 - "$1" <<'EOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1]) / "styles.css"
text = p.read_text(encoding="utf-8")
marker = "#C5162E"  # brand red, present in both css files
assert marker in text, "expected token not found in styles.css"
p.write_text(text.replace(marker, "#C0162E", 1), encoding="utf-8")
EOF
}

corrupt_price_out_of_range() {  # "110 ₾ instead of 11 ₾" typo, unconfirmed
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
for sec in menu["sections"]:
    for gr in sec.get("groups", []):
        for it in gr.get("items", []):
            if it.get("price"):
                it["price"] = "110 ₾"
                p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
                raise SystemExit(0)
EOF
}

corrupt_duplicate_names() {  # the same item twice in one group
  python3 - "$1" <<'EOF'
import copy, json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
group = menu["sections"][0]["groups"][0]
group["items"].append(copy.deepcopy(group["items"][0]))
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

corrupt_empty_group() {  # a group left with no items
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
menu["sections"][0]["groups"][0]["items"] = []
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

corrupt_html_in_name() {  # markup smuggled into an item name
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
item = menu["sections"][0]["groups"][0]["items"][0]
item["name"] = item["name"] + ' <img src=x onerror="alert(1)">'
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

corrupt_brand_links_string() {  # brand.links collapses to a bare string (kills renderBrand)
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
menu["brand"]["links"] = "instagram"
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

corrupt_link_without_url() {  # a header link loses its url
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
del menu["brand"]["links"][0]["url"]
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

corrupt_lead_sections_ghost() {  # leadSections points at a section that does not exist
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
menu["leadSections"].append("ghost")
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

corrupt_navigation_ghost() {  # navigation.initialSection points nowhere
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
menu["navigation"]["initialSection"] = "ghost"
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

corrupt_theme_typo() {  # section theme outside the {drink, food} enum
  python3 - "$1" <<'EOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "data" / "menu.json"
menu = json.loads(p.read_text(encoding="utf-8"))
menu["sections"][0]["theme"] = "fod"
p.write_text(json.dumps(menu, ensure_ascii=False, indent=2), encoding="utf-8")
EOF
}

# ---------------------------------------------------------------------------
# Cases: <corruption name>|<file the error message must mention>
# ---------------------------------------------------------------------------
CASES=(
  "broken_json|data/menu.json"
  "price_no_lari|data/menu.json"
  "category_without_section|data/menu.json"
  "two_leads|data/menu.json"
  "broken_photo|data/menu.json"
  "stale_index|index.html"
  "stale_app_min|app.min.js"
  "stale_styles_min|styles.min.css"
  "manual_index_edit|index.html"
  "price_out_of_range|data/menu.json"
  "duplicate_names|data/menu.json"
  "empty_group|data/menu.json"
  "html_in_name|data/menu.json"
  "brand_links_string|data/menu.json"
  "link_without_url|data/menu.json"
  "lead_sections_ghost|data/menu.json"
  "navigation_ghost|data/menu.json"
  "theme_typo|data/menu.json"
)

make_copy() {
  local dir="$1"
  mkdir -p "$dir/data"
  cp "$ROOT/build.py" "$ROOT/index.html" "$ROOT/app.js" "$ROOT/app.min.js" \
     "$ROOT/styles.css" "$ROOT/styles.min.css" "$dir/"
  cp "$ROOT/data/menu.json" "$dir/data/"
  ln -s "$ROOT/assets" "$dir/assets"
}

# Control: the pristine copy must pass, otherwise every case would "pass" vacuously.
control="$WORK/control"
make_copy "$control"
if ! (cd "$control" && python3 build.py --check > /dev/null 2>&1); then
  echo "CONTROL FAILED: pristine copy does not pass --check; fix that first."
  exit 1
fi
echo "control (no corruption): --check green, harness is meaningful"

pass=0
fail=0
for case_spec in "${CASES[@]}"; do
  name="${case_spec%%|*}"
  expect_file="${case_spec##*|}"
  dir="$WORK/$name"
  make_copy "$dir"
  "corrupt_$name" "$dir"
  output="$(cd "$dir" && python3 build.py --check 2>&1)"
  status=$?
  if [ "$status" -ne 0 ] && printf '%s' "$output" | grep -qF "$expect_file"; then
    echo "PASS  $name (exit=$status, names $expect_file)"
    pass=$((pass + 1))
  else
    echo "FAIL  $name (exit=$status)"
    printf '%s\n' "$output" | sed 's/^/      | /'
    fail=$((fail + 1))
  fi
done

echo "----------------------------------------"
echo "corruption harness: $pass/$((pass + fail)) caught"
[ "$fail" -eq 0 ]
