"""
generate_catalog_image.py

Generates one Discord-ready PNG per market category, with tier subheaders.
  catalog_minerals.png
  catalog_ice_products.png
  catalog_moon_materials.png
  catalog_pi_materials.png
  catalog_gas_cloud_materials.png
  catalog_research_equipment.png
  catalog_salvaged_materials.png

Run any time:  python generate_catalog_image.py
"""
import sqlite3, os
from collections import defaultdict
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
FONT_DIR    = r'C:\Windows\Fonts'

SHOW_CATS = ['minerals', 'ice_products', 'moon_materials', 'pi_materials',
             'gas_cloud_materials', 'research_equipment', 'salvaged_materials']

# ── Tier definitions per category ─────────────────────────────────────────────
CAT_TIER_ORDER = {
    'minerals':           ['Base Minerals'],
    'ice_products':       ['Fuel Blocks', 'Refined Ice', 'Isotopes'],
    'moon_materials':     ['Raw', 'Processed', 'Advanced'],
    'pi_materials':       ['P1 — Basic', 'P2 — Refined', 'P3 — Specialized', 'P4 — Advanced'],
    'gas_cloud_materials':['Compressed Fullerenes', 'Compressed Booster Gas',
                           'Uncompressed Fullerenes', 'Uncompressed Booster Gas'],
    'research_equipment': ['Datacores', 'Decryptors'],
    'salvaged_materials': ['Common', 'Uncommon', 'Rare', 'Very Rare', 'Rogue Drone'],
}

# PI tier lookup: inv_market_groups market_group_id → tier label
PI_GROUP_TO_TIER = {
    1334: 'P1 — Basic',
    1335: 'P2 — Refined',
    1336: 'P3 — Specialized',
    1337: 'P4 — Advanced',
}


def get_item_tier(cat, name, disp_ord, pi_tiers):
    if cat == 'minerals':
        return 'Base Minerals'
    elif cat == 'ice_products':
        if disp_ord <= 8:  return 'Fuel Blocks'
        if disp_ord <= 11: return 'Refined Ice'
        return 'Isotopes'
    elif cat == 'moon_materials':
        if disp_ord < 100: return 'Raw'
        if disp_ord < 200: return 'Processed'
        return 'Advanced'
    elif cat == 'pi_materials':
        return pi_tiers.get(name, 'Other')
    elif cat == 'gas_cloud_materials':
        if disp_ord < 100: return 'Compressed Fullerenes'
        if disp_ord < 200: return 'Compressed Booster Gas'
        if disp_ord < 300: return 'Uncompressed Fullerenes'
        return 'Uncompressed Booster Gas'
    elif cat == 'research_equipment':
        if disp_ord < 100: return 'Datacores'
        return 'Decryptors'
    elif cat == 'salvaged_materials':
        for r, tier in [(range(1,10),'Common'),(range(10,22),'Uncommon'),
                        (range(22,33),'Rare'),(range(33,43),'Very Rare'),
                        (range(43,100),'Rogue Drone')]:
            if disp_ord in r: return tier
    return 'Other'


# ── Palette ───────────────────────────────────────────────────────────────────
BG      = (  8,  14,  24)
BG2     = ( 12,  20,  34)
BG_TIER = ( 14,  22,  36)
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
TIER_H   = 18   # tier subheader row height
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


def make_tiered_catalog_image(cat, tier_groups_stock, n_all, n_stock, ts_str, fonts):
    """
    Render a catalog PNG with tier subheader rows between groups.
    tier_groups_stock: [(tier_name, [(name, qty, price_pct, alliance_disc), ...])]
                       ordered; only tiers with at least 1 stocked item shown.
    """
    f_banner, f_sub, f_head, f_item, f_small, f_price = fonts
    colour = CAT_COLOURS[cat]
    label  = CAT_LABELS[cat]

    # Column geometry
    _d_tmp    = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    pct_col_w = tw(_d_tmp, '100%',   f_price)
    qty_col_w = tw(_d_tmp, '999.9M', f_price)
    GAP        = 14
    RIGHT_EDGE = IMG_W - PAD - 4
    corp_right = RIGHT_EDGE
    ally_right = corp_right - pct_col_w - GAP
    qty_right  = ally_right - pct_col_w - GAP
    NAME_W     = qty_right - qty_col_w - GAP - (PAD + 12)

    # Height: banner + col-header + tier-headers + item-rows + padding + footer
    n_tier_hdrs = sum(1 for _, items in tier_groups_stock if items)
    n_item_rows = sum(len(items) for _, items in tier_groups_stock)
    total_h = BANNER_H + ROW_H + n_tier_hdrs * TIER_H + n_item_rows * ROW_H + ROW_H + FOOTER_H

    img = Image.new('RGB', (IMG_W, total_h), BG)
    d   = ImageDraw.Draw(img)

    # ── Banner ────────────────────────────────────────────────────────────────
    d.rectangle([0, 0, IMG_W, BANNER_H], fill=BG2)
    d.rectangle([0, 0, IMG_W, 4], fill=colour)
    d.text((PAD, 8),  f'LX-ZOJ  ·  {label}', font=f_banner, fill=WHITE)
    d.text((PAD, 32), f'Updated  {ts_str}',   font=f_sub,    fill=SUBTEXT)

    lx = IMG_W - PAD
    ly = 8
    corp_lbl_w = tw(d, 'Corp',     f_sub)
    ally_lbl_w = tw(d, 'Alliance', f_sub)
    sw, gap, sep = 8, 4, 14
    d.text((lx, ly), 'Corp', font=f_sub, fill=GOLD, anchor='ra')
    d.rectangle([lx - corp_lbl_w - gap - sw, ly + 1,
                 lx - corp_lbl_w - gap,       ly + 1 + sw], fill=GOLD)
    _ar = lx - corp_lbl_w - gap - sw - sep
    d.text((_ar, ly), 'Alliance', font=f_sub, fill=ACCENT, anchor='ra')
    d.rectangle([_ar - ally_lbl_w - gap - sw, ly + 1,
                 _ar - ally_lbl_w - gap,       ly + 1 + sw], fill=ACCENT)
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

    # ── Tier groups ───────────────────────────────────────────────────────────
    row_index = 0
    for tier_name, items in tier_groups_stock:
        if not items:
            continue
        # Tier subheader
        d.rectangle([0, y, IMG_W, y + TIER_H], fill=BG_TIER)
        d.text((PAD + 4, y + 3), tier_name.upper(), font=f_small, fill=colour)
        y += TIER_H

        for name, qty, price_pct, alliance_disc in items:
            row_bg = BG if row_index % 2 == 0 else BG2
            d.rectangle([0, y, IMG_W, y + ROW_H], fill=row_bg)
            d.ellipse([PAD, y + 6, PAD + 8, y + 14], fill=GREEN)
            d.text((PAD + 12, y + 3), truncate(d, name, f_item, NAME_W),
                   font=f_item, fill=WHITE)
            d.text((qty_right, y + 4), fmt_qty(qty),
                   font=f_price, fill=GREEN, anchor='ra')
            if price_pct is not None:
                d.text((ally_right, y + 4), f'{price_pct:.0f}%',
                       font=f_price, fill=ACCENT, anchor='ra')
                d.text((corp_right, y + 4), f'{price_pct - alliance_disc:.0f}%',
                       font=f_price, fill=GOLD, anchor='ra')
            y += ROW_H
            row_index += 1

    # ── Footer ────────────────────────────────────────────────────────────────
    d.line([0, y, IMG_W, y], fill=(20, 35, 50), width=1)
    note = '@ or DM Hamektok Hakaari on Discord to purchase  ·  corp members only'
    nw = tw(d, note, f_sub)
    d.text(((IMG_W - nw) // 2, y + 10), note, font=f_sub, fill=SUBTEXT)

    out = os.path.join(PROJECT_DIR, f'catalog_{cat}.png')
    img.save(out, optimize=True)
    print(f'  Saved: catalog_{cat}.png  ({IMG_W}×{total_h}px,  {n_stock}/{n_all} in stock)')


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

    def ice_sub_visible(do):
        if do <= 8:  return ice_fuel
        if do <= 11: return ice_refined
        return ice_isotopes

    def moon_sub_visible(do):
        if do < 100: return moon_raw
        if do < 200: return moon_proc
        return moon_adv

    def gas_sub_visible(do):
        if do < 100: return gas_cf
        if do < 200: return gas_cb
        if do < 300: return gas_uf
        return gas_ub

    def research_sub_visible(do):
        return res_dc if do < 100 else res_dec

    # ── PI tier lookup (market group → P-tier label) ──────────────────────────
    pi_tiers = {}
    c.execute('''
        SELECT t.type_name, it.market_group_id
        FROM tracked_market_items t
        JOIN inv_types it ON t.type_id = it.type_id
        WHERE t.category = "pi_materials"
    ''')
    for name, mgid in c.fetchall():
        pi_tiers[name] = PI_GROUP_TO_TIER.get(mgid, 'Other')

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

    # ── Organise into tiered dicts ────────────────────────────────────────────
    # tiered_all[cat][tier]   = [(name, qty, pct, disc), ...]  (all items)
    # tiered_stock[cat][tier] = [(name, qty, pct, disc), ...]  (qty > 0 only)
    tiered_all   = {cat: defaultdict(list) for cat in SHOW_CATS}
    tiered_stock = {cat: defaultdict(list) for cat in SHOW_CATS}

    for cat, name, disp_ord, qty, price_pct, alliance_disc in rows:
        if cat not in SHOW_CATS or not cat_visible.get(cat, True):
            continue
        if cat == 'ice_products'        and not ice_sub_visible(disp_ord):      continue
        if cat == 'moon_materials'      and not moon_sub_visible(disp_ord):     continue
        if cat == 'gas_cloud_materials' and not gas_sub_visible(disp_ord):      continue
        if cat == 'research_equipment'  and not research_sub_visible(disp_ord): continue

        tier  = get_item_tier(cat, name, disp_ord, pi_tiers)
        entry = (name, qty, price_pct, alliance_disc)
        tiered_all[cat][tier].append(entry)
        if qty > 0:
            tiered_stock[cat][tier].append(entry)

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

        tier_order = CAT_TIER_ORDER[cat]
        # Build tier_groups preserving defined order; include tier if it has any items at all
        tier_groups_stock = [
            (tier, tiered_stock[cat].get(tier, []))
            for tier in tier_order
            if tiered_all[cat].get(tier)   # skip tiers with zero items even in "all"
        ]
        n_all   = sum(len(v) for v in tiered_all[cat].values())
        n_stock = sum(len(v) for v in tiered_stock[cat].values())

        if not n_all:
            print(f'  Skipped: {cat} (no items)')
            continue

        make_tiered_catalog_image(cat, tier_groups_stock, n_all, n_stock, ts_str, fonts)
    print('Done.')


if __name__ == '__main__':
    main()
