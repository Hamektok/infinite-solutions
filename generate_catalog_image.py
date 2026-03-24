"""
generate_catalog_image.py

Generates one Discord-ready PNG per market category:
  catalog_minerals.png
  catalog_ice_products.png
  catalog_moon_materials.png
  catalog_pi_materials.png

Single-column layout, full item name, Alliance % (blue) and Corp % (gold).

Run any time:  python generate_catalog_image.py
"""
import sqlite3, os, math
from collections import defaultdict
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
FONT_DIR    = r'C:\Windows\Fonts'

SHOW_CATS = ['minerals', 'ice_products', 'moon_materials', 'pi_materials',
             'gas_cloud_materials', 'research_equipment', 'salvaged_materials']

SALVAGE_TIERS_ORDER = ['Common', 'Uncommon', 'Rare', 'Very Rare', 'Rogue Drone']
SALVAGE_TIER_RANGES = [
    (range(1,  10),  'Common'),
    (range(10, 22),  'Uncommon'),
    (range(22, 33),  'Rare'),
    (range(33, 43),  'Very Rare'),
    (range(43, 100), 'Rogue Drone'),
]
TIER_HDR_H = 18   # height of in-image tier subheader rows

def get_salvage_tier(display_order):
    for r, name in SALVAGE_TIER_RANGES:
        if display_order in r:
            return name
    return 'Other'

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = (  8,  14,  24)
BG2     = ( 12,  20,  34)
WHITE   = (220, 238, 255)
DIM     = ( 80, 110, 135)
SUBTEXT = ( 90, 138, 170)
GREEN   = ( 50, 210, 120)
ACCENT  = (  0, 175, 255)
GOLD    = (255, 200,  50)

CAT_COLOURS = {
    'minerals':            (  0, 175, 255),
    'ice_products':        ( 40, 200, 200),
    'moon_materials':      (200,  80, 220),
    'pi_materials':        (255, 160,  30),
    'gas_cloud_materials': (  0, 220, 140),
    'research_equipment':  (180, 120, 255),
    'salvaged_materials':  (255, 140,  60),
}
CAT_LABELS = {
    'minerals':            'Minerals',
    'ice_products':        'Ice Products',
    'moon_materials':      'Moon Materials',
    'pi_materials':        'Planetary Materials',
    'gas_cloud_materials': 'Gas Cloud Materials',
    'research_equipment':  'Research Equipment',
    'salvaged_materials':  'Salvaged Materials',
}

# ── Layout ────────────────────────────────────────────────────────────────────
IMG_W    = 560
PAD      = 14
ROW_H    = 20
BANNER_H = 52
FOOTER_H = 32

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_font(name, size):
    try:    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except: return ImageFont.load_default()

def tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def truncate(draw, text, font, max_px):
    if tw(draw, text, font) <= max_px:
        return text
    while text and tw(draw, text + '…', font) > max_px:
        text = text[:-1]
    return text + '…'

def fmt_qty(n):
    if n >= 1_000_000_000: return f'{n/1_000_000_000:.1f}B'
    if n >= 1_000_000:     return f'{n/1_000_000:.1f}M'
    if n >= 1_000:         return f'{n/1_000:.1f}K'
    return f'{n:,}'


def make_category_image(cat, items_stock, items_all, ts_str, fonts):
    f_banner, f_sub, f_head, f_item, f_small, f_price = fonts

    colour = CAT_COLOURS[cat]
    label  = CAT_LABELS[cat]
    n_stock = len(items_stock)
    n_all   = len(items_all)

    # Pre-measure fixed column widths for right-side block
    _d_tmp    = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    pct_col_w = tw(_d_tmp, '100%',   f_price)   # width of widest % value
    qty_col_w = tw(_d_tmp, '999.9M', f_price)   # width of widest qty value
    GAP       = 14                               # gap between every column
    RIGHT_EDGE = IMG_W - PAD - 4
    # Right-to-left column anchors (right edge of each column)
    corp_right = RIGHT_EDGE
    ally_right = corp_right - pct_col_w - GAP
    qty_right  = ally_right - pct_col_w - GAP
    # Name takes all remaining space to the left of qty column
    NAME_W     = qty_right - qty_col_w - GAP - (PAD + 12)

    total_h = BANNER_H + ROW_H + n_stock * ROW_H + ROW_H + FOOTER_H

    img = Image.new('RGB', (IMG_W, total_h), BG)
    d   = ImageDraw.Draw(img)

    # ── Banner ────────────────────────────────────────────────────────────────
    d.rectangle([0, 0, IMG_W, BANNER_H], fill=BG2)
    d.rectangle([0, 0, IMG_W, 4], fill=colour)   # category-coloured top bar
    d.text((PAD, 8),  f'LX-ZOJ  ·  {label}',    font=f_banner, fill=WHITE)
    d.text((PAD, 32), f'Updated  {ts_str}',       font=f_sub,    fill=SUBTEXT)

    # Color legend (right side)
    lx = IMG_W - PAD
    ly = 8
    corp_lbl_w = tw(d, 'Corp',     f_sub)
    ally_lbl_w = tw(d, 'Alliance', f_sub)
    sw, gap, sep = 8, 4, 14

    d.text((lx, ly), 'Corp', font=f_sub, fill=GOLD, anchor='ra')
    d.rectangle([lx - corp_lbl_w - gap - sw, ly + 1,
                 lx - corp_lbl_w - gap,       ly + 1 + sw], fill=GOLD)

    ally_right = lx - corp_lbl_w - gap - sw - sep
    d.text((ally_right, ly), 'Alliance', font=f_sub, fill=ACCENT, anchor='ra')
    d.rectangle([ally_right - ally_lbl_w - gap - sw, ly + 1,
                 ally_right - ally_lbl_w - gap,       ly + 1 + sw], fill=ACCENT)

    d.text((IMG_W - PAD, 22), '% of Jita Buy',
           font=f_sub, fill=DIM, anchor='ra')
    d.text((IMG_W - PAD, 36), f'{n_stock} of {n_all} in stock',
           font=f_sub, fill=(50, 80, 100), anchor='ra')

    # ── Column headers ────────────────────────────────────────────────────────
    y = BANNER_H
    d.rectangle([0, y, IMG_W, y + ROW_H], fill=BG2)
    d.text((PAD + 12,  y + 4), 'Item',     font=f_small, fill=DIM)
    d.text((qty_right, y + 4), 'Qty',      font=f_small, fill=DIM, anchor='ra')
    d.text((ally_right,y + 4), 'Alliance', font=f_small, fill=DIM, anchor='ra')
    d.text((corp_right,y + 4), 'Corp',     font=f_small, fill=DIM, anchor='ra')
    y += ROW_H

    # ── Item rows ─────────────────────────────────────────────────────────────
    for i, (name, qty, price_pct, alliance_disc) in enumerate(items_stock):
        row_bg = BG if i % 2 == 0 else BG2
        d.rectangle([0, y, IMG_W, y + ROW_H], fill=row_bg)

        # Dot
        d.ellipse([PAD, y + 6, PAD + 8, y + 14], fill=GREEN)

        # Name — truncated to fit its column
        disp = truncate(d, name, f_item, NAME_W)
        d.text((PAD + 12, y + 3), disp, font=f_item, fill=WHITE)

        # Qty — right-aligned at qty column anchor
        d.text((qty_right, y + 4), fmt_qty(qty), font=f_price, fill=GREEN, anchor='ra')

        # Prices — right-aligned at their column anchors
        if price_pct is not None:
            d.text((ally_right, y + 4), f'{price_pct:.0f}%',
                   font=f_price, fill=ACCENT, anchor='ra')
            d.text((corp_right, y + 4), f'{price_pct - alliance_disc:.0f}%',
                   font=f_price, fill=GOLD,   anchor='ra')

        y += ROW_H

    # ── Footer ────────────────────────────────────────────────────────────────
    d.line([0, y, IMG_W, y], fill=(20, 35, 50), width=1)
    note = '@ or DM Hamektok Hakaari on Discord to purchase  ·  corp members only'
    nw = tw(d, note, f_sub)
    d.text(((IMG_W - nw) // 2, y + 10), note, font=f_sub, fill=SUBTEXT)

    out = os.path.join(PROJECT_DIR, f'catalog_{cat}.png')
    img.save(out, optimize=True)
    print(f'  Saved: catalog_{cat}.png  ({IMG_W}×{total_h}px,  {n_stock}/{n_all} in stock)')
    return out


def make_salvage_catalog_image(tier_groups_stock, n_all, n_stock, ts_str, fonts):
    """Render catalog image for salvaged_materials with tier subheaders."""
    f_banner, f_sub, f_head, f_item, f_small, f_price = fonts
    cat    = 'salvaged_materials'
    colour = CAT_COLOURS[cat]
    label  = CAT_LABELS[cat]

    _d_tmp    = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    pct_col_w = tw(_d_tmp, '100%',   f_price)
    qty_col_w = tw(_d_tmp, '999.9M', f_price)
    GAP       = 14
    RIGHT_EDGE = IMG_W - PAD - 4
    corp_right = RIGHT_EDGE
    ally_right = corp_right - pct_col_w - GAP
    qty_right  = ally_right - pct_col_w - GAP
    NAME_W     = qty_right - qty_col_w - GAP - (PAD + 12)

    n_item_rows = sum(len(items) for _, items in tier_groups_stock)
    n_tier_hdrs = sum(1 for _, items in tier_groups_stock if items)
    total_h = BANNER_H + ROW_H + n_tier_hdrs * TIER_HDR_H + n_item_rows * ROW_H + ROW_H + FOOTER_H

    img = Image.new('RGB', (IMG_W, total_h), BG)
    d   = ImageDraw.Draw(img)

    # Banner
    d.rectangle([0, 0, IMG_W, BANNER_H], fill=BG2)
    d.rectangle([0, 0, IMG_W, 4], fill=colour)
    d.text((PAD, 8),  f'LX-ZOJ  ·  {label}', font=f_banner, fill=WHITE)
    d.text((PAD, 32), f'Updated  {ts_str}',    font=f_sub,    fill=SUBTEXT)

    lx = IMG_W - PAD
    ly = 8
    corp_lbl_w = tw(d, 'Corp',     f_sub)
    ally_lbl_w = tw(d, 'Alliance', f_sub)
    sw, gap, sep = 8, 4, 14
    d.text((lx, ly), 'Corp', font=f_sub, fill=GOLD, anchor='ra')
    d.rectangle([lx - corp_lbl_w - gap - sw, ly + 1, lx - corp_lbl_w - gap, ly + 1 + sw], fill=GOLD)
    _ar = lx - corp_lbl_w - gap - sw - sep
    d.text((_ar, ly), 'Alliance', font=f_sub, fill=ACCENT, anchor='ra')
    d.rectangle([_ar - ally_lbl_w - gap - sw, ly + 1, _ar - ally_lbl_w - gap, ly + 1 + sw], fill=ACCENT)
    d.text((IMG_W - PAD, 22), '% of Jita Buy',               font=f_sub, fill=DIM,         anchor='ra')
    d.text((IMG_W - PAD, 36), f'{n_stock} of {n_all} in stock', font=f_sub, fill=(50,80,100), anchor='ra')

    # Column headers
    y = BANNER_H
    d.rectangle([0, y, IMG_W, y + ROW_H], fill=BG2)
    d.text((PAD + 12,  y + 4), 'Item',     font=f_small, fill=DIM)
    d.text((qty_right, y + 4), 'Qty',      font=f_small, fill=DIM, anchor='ra')
    d.text((ally_right,y + 4), 'Alliance', font=f_small, fill=DIM, anchor='ra')
    d.text((corp_right,y + 4), 'Corp',     font=f_small, fill=DIM, anchor='ra')
    y += ROW_H

    # Tier groups
    row_index = 0
    for tier_name, items in tier_groups_stock:
        if not items:
            continue
        d.rectangle([0, y, IMG_W, y + TIER_HDR_H], fill=(14, 22, 36))
        d.text((PAD + 4, y + 3), tier_name.upper(), font=f_small, fill=colour)
        y += TIER_HDR_H

        for name, qty, price_pct, alliance_disc in items:
            row_bg = BG if row_index % 2 == 0 else BG2
            d.rectangle([0, y, IMG_W, y + ROW_H], fill=row_bg)
            d.ellipse([PAD, y + 6, PAD + 8, y + 14], fill=GREEN)
            d.text((PAD + 12, y + 3), truncate(d, name, f_item, NAME_W), font=f_item, fill=WHITE)
            d.text((qty_right, y + 4), fmt_qty(qty), font=f_price, fill=GREEN, anchor='ra')
            if price_pct is not None:
                d.text((ally_right, y + 4), f'{price_pct:.0f}%',
                       font=f_price, fill=ACCENT, anchor='ra')
                d.text((corp_right, y + 4), f'{price_pct - alliance_disc:.0f}%',
                       font=f_price, fill=GOLD, anchor='ra')
            y += ROW_H
            row_index += 1

    # Footer
    d.line([0, y, IMG_W, y], fill=(20, 35, 50), width=1)
    note = '@ or DM Hamektok Hakaari on Discord to purchase  ·  corp members only'
    nw = tw(d, note, f_sub)
    d.text(((IMG_W - nw) // 2, y + 10), note, font=f_sub, fill=SUBTEXT)

    out = os.path.join(PROJECT_DIR, 'catalog_salvaged_materials.png')
    img.save(out, optimize=True)
    print(f'  Saved: catalog_salvaged_materials.png  ({IMG_W}×{total_h}px,  {n_stock}/{n_all} in stock)')


def main():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # ── Visibility flags ──────────────────────────────────────────────────────
    vis_rows = c.execute(
        "SELECT key, value FROM site_config WHERE key LIKE 'market_tab_%' OR key LIKE 'market_sub_%'"
    ).fetchall()
    vis = {k: (str(v) == '1') for k, v in vis_rows}

    cat_visible = {
        'minerals':            vis.get('market_tab_minerals',             True),
        'ice_products':        vis.get('market_tab_ice_products',         True),
        'moon_materials':      vis.get('market_tab_moon_materials',       True),
        'pi_materials':        vis.get('market_tab_pi_materials',         True),
        'gas_cloud_materials': vis.get('market_tab_gas_cloud_materials',  True),
        'research_equipment':  vis.get('market_tab_research_equipment',   True),
        'salvaged_materials':  vis.get('market_tab_salvaged_materials',   True),
    }

    ice_fuel     = vis.get('market_sub_ice_products_fuel_blocks',                  True)
    ice_refined  = vis.get('market_sub_ice_products_refined_ice',                  True)
    ice_isotopes = vis.get('market_sub_ice_products_isotopes',                     True)
    moon_raw     = vis.get('market_sub_moon_materials_raw',                        True)
    moon_proc    = vis.get('market_sub_moon_materials_processed',                  True)
    moon_adv     = vis.get('market_sub_moon_materials_advanced',                   True)
    gas_cf       = vis.get('market_sub_gas_cloud_materials_compressed_fullerene',  True)
    gas_cb       = vis.get('market_sub_gas_cloud_materials_compressed_booster',    True)
    gas_uf       = vis.get('market_sub_gas_cloud_materials_uncompressed_fullerene',True)
    gas_ub       = vis.get('market_sub_gas_cloud_materials_uncompressed_booster',  True)
    res_dc       = vis.get('market_sub_research_equipment_datacores',              True)
    res_dec      = vis.get('market_sub_research_equipment_decryptors',             True)

    def ice_sub_visible(display_order):
        if display_order <= 8:  return ice_fuel
        if display_order <= 11: return ice_refined
        return ice_isotopes

    def moon_sub_visible(display_order):
        if display_order < 100: return moon_raw
        if display_order < 200: return moon_proc
        return moon_adv

    def gas_sub_visible(display_order):
        if display_order < 100: return gas_cf
        if display_order < 200: return gas_cb
        if display_order < 300: return gas_uf
        return gas_ub

    def research_sub_visible(display_order):
        if display_order < 100: return res_dc
        return res_dec

    # ── Query items ───────────────────────────────────────────────────────────
    rows = c.execute('''
        SELECT t.category, t.type_name, t.display_order,
               COALESCE(MAX(i.quantity), 0) AS qty,
               t.price_percentage,
               COALESCE(t.alliance_discount, 0) AS alliance_discount
        FROM tracked_market_items t
        LEFT JOIN lx_zoj_inventory i
               ON i.type_id = t.type_id
              AND i.snapshot_timestamp = (SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory)
        GROUP BY t.type_id
        ORDER BY t.category, t.display_order, t.type_name
    ''').fetchall()

    snap_ts = c.execute(
        'SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory'
    ).fetchone()[0] or ''
    conn.close()

    try:
        dt     = datetime.fromisoformat(snap_ts)
        ts_str = dt.strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = snap_ts

    # ── Organise by category ──────────────────────────────────────────────────
    cat_all   = defaultdict(list)
    cat_stock = defaultdict(list)
    salvage_tiered_all   = defaultdict(list)   # tier -> all items
    salvage_tiered_stock = defaultdict(list)   # tier -> stocked items

    for cat, name, disp_ord, qty, price_pct, alliance_disc in rows:
        if cat not in SHOW_CATS or not cat_visible.get(cat, True):
            continue
        if cat == 'ice_products'        and not ice_sub_visible(disp_ord):      continue
        if cat == 'moon_materials'      and not moon_sub_visible(disp_ord):     continue
        if cat == 'gas_cloud_materials' and not gas_sub_visible(disp_ord):      continue
        if cat == 'research_equipment'  and not research_sub_visible(disp_ord): continue
        if cat == 'salvaged_materials':
            tier  = get_salvage_tier(disp_ord)
            entry = (name, qty, price_pct, alliance_disc)
            salvage_tiered_all[tier].append(entry)
            if qty > 0:
                salvage_tiered_stock[tier].append(entry)
            continue
        entry = (name, qty, price_pct, alliance_disc)
        cat_all[cat].append(entry)
        if qty > 0:
            cat_stock[cat].append(entry)

    # ── Fonts (shared across all images) ─────────────────────────────────────
    fonts = (
        load_font('segoeuib.ttf', 15),   # f_banner
        load_font('segoeui.ttf',  10),   # f_sub
        load_font('segoeuib.ttf', 11),   # f_head
        load_font('segoeui.ttf',  11),   # f_item
        load_font('segoeui.ttf',  10),   # f_small
        load_font('segoeuib.ttf', 10),   # f_price
    )

    # ── Generate one image per category ──────────────────────────────────────
    print('Generating catalog images...')
    for cat in SHOW_CATS:
        if not cat_visible.get(cat, True):
            print(f'  Skipped: {cat} (hidden)')
            continue
        if cat == 'salvaged_materials':
            tier_groups = [(t, salvage_tiered_stock.get(t, []))
                           for t in SALVAGE_TIERS_ORDER if salvage_tiered_all.get(t)]
            n_all   = sum(len(v) for v in salvage_tiered_all.values())
            n_stock = sum(len(v) for v in salvage_tiered_stock.values())
            make_salvage_catalog_image(tier_groups, n_all, n_stock, ts_str, fonts)
        else:
            make_category_image(cat, cat_stock.get(cat, []), cat_all.get(cat, []), ts_str, fonts)
    print('Done.')


if __name__ == '__main__':
    main()
