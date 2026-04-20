# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Run admin dashboard
python admin_dashboard.py

# Rebuild static site after rate/item changes
python generate_buyback_data.py        # → buyback_data.js
python update_html_data.py             # → embeds inventory + blueprints into index_final.html
cp index_final.html index.html

# Run standalone update scripts
python update_lx_zoj_inventory.py      # ESI asset fetch → DB → index_final.html
python generate_stock_image.py         # Discord stock image (Pillow)
python generate_fuel_image.py          # Discord fuel image (Pillow)
python generate_slots_image.py         # Discord slot image (Pillow)

# Build standalone HTML pages
python _build_haul_calculator.py       # → haul_calculator.html
python _build_haul_quote.py            # → haul_quote.html
python _build_gank_watchlist.py        # → gank_watchlist.html

# Gank watchlist nightly automation (Task Scheduler)
powershell -ExecutionPolicy Bypass -File run_gank_fetch.ps1

# DB inspection
python -c "import sqlite3; conn=sqlite3.connect('mydatabase.db'); ..."
```

## Architecture

### Site Stack
- **index_final.html** — single-file static site; `index.html` is the live GitHub Pages copy
- **buyback_data.js** — generated JS data file, injected via `<script src="buyback_data.js">` in the HTML
- `update_html_data.py` embeds inventory/blueprint data directly into `index_final.html` as a `const EMBEDDED_DATA` block
- Deployed to GitHub Pages (main branch) at `https://hamektok.github.io/infinite-solutions/`
- Branch strategy: dev for features, merge to main + push to deploy

### Admin GUI
- **admin_dashboard.py** — Tkinter app (~8000+ lines), single `AdminDashboard` class
- Long-running operations use background threads with `root.after(0, callback)` for UI updates
- Always use `sys.executable` for subprocess calls, never hardcoded Python path
- Tab numbering: 1=Market Rates, 2=Buyback, 3=Inventory, 4=Actions, 5=Slot Pricing, 6=Slot Manager, 7=Ore Import, 8=Import Analysis, 9+ = more tabs; "Gank Watch" is Tab 15, "Build Requests" is Tab 12

### Database (SQLite — mydatabase.db)
Key tables:
- `tracked_market_items` — items sold; columns: type_id, type_name, category, display_order, price_percentage, alliance_discount, buyback_accepted, buyback_rate, buyback_quota, site
- `site_config` — key/value store for all site settings (market tab visibility, pricing params, etc.)
- `market_price_snapshots` — Jita price data (used by Ore Import tab)
- `market_snapshots` — 5-hub price data (used by Import Analysis tab; never mix with market_price_snapshots)
- `gank_watchlist` — ganker/cyno_alt entity tracking
- `system_security_cache` — ESI system security status cache (solar_system_id, security_status, system_name, fetched_at)
- `ore_refine_yields` — per-ore mineral yield rates (per-unit, pre-efficiency)
- `type_materials` — SDE reprocessing materials as JSON per type_id

### Market Category System
DB categories and their display names (must stay in sync across admin_dashboard.py, generate_buyback_data.py, index_final.html):
- `minerals` → Minerals
- `ice_products` → Ice Products
- `moon_materials` → Reaction Materials
- `gas_cloud_materials` → Gas Cloud Materials
- `research_equipment` → Research Equipment
- `pi_materials` → Planetary Materials
- `salvaged_materials` → Salvaged Materials
- `standard_ore` → Standard Ore (ore mineral-value pricing)
- `ice_ore` → Ice Ore (ore mineral-value pricing)
- `moon_ore` → Moon Ore (ore mineral-value pricing)

Ore categories (`standard_ore`, `ice_ore`, `moon_ore`) use mineral-value pricing: `avgJitaBuy` = mineral value at configured refining efficiency (default 90.63%), not raw ore spot price.

### Site Visibility
`site_config` table controls tab/sub-tab visibility:
- `market_tab_{key}` = '1'/'0' — show/hide main market sub-tab
- `market_sub_{tab_key}_{sub_key}` = '1'/'0' — show/hide sub-category filter button

`applyMarketVisibility()` in index_final.html reads `BUYBACK_DATA.marketVisibility` and hides/shows tabs accordingly. `generate_buyback_data.py` reads site_config and embeds this in BUYBACK_DATA.

### EVE ESI / Token Pattern
- `scripts/token_manager.py` — OAuth refresh, but hardcodes `credentials.json` path
- Character-specific credentials stored in `config/credentials_hamektok.json` (char ID 97153110), `config/credentials_gank_contact.json` (char ID 2112673557)
- For characters other than the default, do direct OAuth POST in the script rather than using token_manager

### Static Build Scripts (_build_*.py)
Each `_build_*.py` reads from DB and writes a standalone HTML file. Pattern: query DB → build Python string → write file. They live at project root. The generated HTML files are pushed to GitHub Pages.

### Subcategory Display Order Ranges
These ranges determine which sub-section an item belongs to (consistent across admin_dashboard.py, generate_buyback_data.py, generate_stock_image.py):
- ice_products: ≤4 = Fuel Blocks, ≤11 = Refined Ice, 12+ = Isotopes
- moon_materials: ≤35 = Raw, ≤124 = Processed, 125+ = Advanced
- gas_cloud_materials: <100 = Compressed Fullerenes, <200 = Compressed Booster Gas, <300 = Uncompressed Fullerenes, 300+ = Uncompressed Booster Gas
- standard_ore compressed items: display_order 101–500 range (base = 101-104, 105-108, … per ore type in groups of 4)
- moon_ore compressed: display_order 101+ grouped by tier (R4, R8, R16, R32, R64)
- ice_ore compressed: display_order 101+

### Deploy Flow
```
Edit rates/items in admin dashboard
→ python generate_buyback_data.py    (updates buyback_data.js)
→ python update_html_data.py         (embeds into index_final.html)
→ cp index_final.html index.html
→ git add buyback_data.js index_final.html index.html && git commit && git push
```
