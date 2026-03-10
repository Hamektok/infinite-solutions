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

SHOW_CATS = ['minerals', 'ice_products', 'moon_materials', 'pi_materials']

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
    'minerals':      (  0, 175, 255),
    'ice_products':  ( 40, 200, 200),
    'moon_materials':(200,  80, 220),
    'pi_materials':  (255, 160,  30),
}
CAT_LABELS = {
    'minerals':      'Minerals',
    'ice_products':  'Ice Products',
    'moon_materials':'Moon Materials',
    'pi_materials':  'Planetary Materials',
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

    # Pre-measure columns
    _d_tmp     = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    pct_max_w  = tw(_d_tmp, '100%', f_price)
    qty_max_w  = tw(_d_tmp, '999.9M', f_price)
    GAP        = 10
    QTY_GAP    = 8
    RIGHT_W    = pct_max_w + GAP + pct_max_w + 4
    COL_W      = IMG_W - PAD * 2
    NAME_W     = COL_W - 12 - QTY_GAP - qty_max_w - GAP - RIGHT_W - 4  # 12 = dot

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
    d.text((PAD + 12, y + 4), 'Item', font=f_small, fill=DIM)
    right = IMG_W - PAD - 4
    d.text((right, y + 4), 'Corp', font=f_small, fill=DIM, anchor='ra')
    corp_hdr_w = tw(d, 'Corp', f_small)
    ally_x = right - corp_hdr_w - GAP
    d.text((ally_x, y + 4), 'Alliance', font=f_small, fill=DIM, anchor='ra')
    ally_hdr_w = tw(d, 'Alliance', f_small)
    qty_hdr_x = ally_x - ally_hdr_w - GAP - QTY_GAP
    d.text((qty_hdr_x, y + 4), 'Qty', font=f_small, fill=DIM, anchor='ra')
    y += ROW_H

    # ── Item rows ─────────────────────────────────────────────────────────────
    for i, (name, qty, price_pct, alliance_disc) in enumerate(items_stock):
        row_bg = BG if i % 2 == 0 else BG2
        d.rectangle([0, y, IMG_W, y + ROW_H], fill=row_bg)

        cx    = PAD
        right = IMG_W - PAD - 4

        # Dot
        d.ellipse([cx, y + 6, cx + 8, y + 14], fill=GREEN)

        # Name
        disp = truncate(d, name, f_item, NAME_W)
        d.text((cx + 12, y + 3), disp, font=f_item, fill=WHITE)

        # Qty
        qty_str = fmt_qty(qty)
        qty_x   = right - (pct_max_w + GAP + pct_max_w + 4) - QTY_GAP
        d.text((qty_x, y + 4), qty_str, font=f_price, fill=GREEN, anchor='ra')

        # Prices
        if price_pct is not None:
            corp_str = f'{price_pct - alliance_disc:.0f}%'
            ally_str = f'{price_pct:.0f}%'
            d.text((right, y + 4), corp_str, font=f_price, fill=GOLD,  anchor='ra')
            corp_w = tw(d, corp_str, f_price)
            d.text((right - corp_w - GAP, y + 4), ally_str,
                   font=f_price, fill=ACCENT, anchor='ra')

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


def main():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # ── Visibility flags ──────────────────────────────────────────────────────
    vis_rows = c.execute(
        "SELECT key, value FROM site_config WHERE key LIKE 'market_tab_%' OR key LIKE 'market_sub_%'"
    ).fetchall()
    vis = {k: (str(v) == '1') for k, v in vis_rows}

    cat_visible = {
        'minerals':      vis.get('market_tab_minerals',       True),
        'ice_products':  vis.get('market_tab_ice_products',   True),
        'moon_materials':vis.get('market_tab_moon_materials', True),
        'pi_materials':  vis.get('market_tab_pi_materials',   True),
    }

    ice_fuel     = vis.get('market_sub_ice_products_fuel_blocks',  True)
    ice_refined  = vis.get('market_sub_ice_products_refined_ice',  True)
    ice_isotopes = vis.get('market_sub_ice_products_isotopes',     True)
    moon_raw     = vis.get('market_sub_moon_materials_raw',        True)
    moon_proc    = vis.get('market_sub_moon_materials_processed',  True)
    moon_adv     = vis.get('market_sub_moon_materials_advanced',   True)

    def ice_sub_visible(display_order):
        if display_order <= 8:  return ice_fuel
        if display_order <= 11: return ice_refined
        return ice_isotopes

    def moon_sub_visible(display_order):
        if display_order < 100: return moon_raw
        if display_order < 200: return moon_proc
        return moon_adv

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

    for cat, name, disp_ord, qty, price_pct, alliance_disc in rows:
        if cat not in SHOW_CATS or not cat_visible.get(cat, True):
            continue
        if cat == 'ice_products'   and not ice_sub_visible(disp_ord):
            continue
        if cat == 'moon_materials' and not moon_sub_visible(disp_ord):
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
        make_category_image(
            cat,
            cat_stock.get(cat, []),
            cat_all.get(cat, []),
            ts_str,
            fonts,
        )
    print('Done.')


if __name__ == '__main__':
    main()
