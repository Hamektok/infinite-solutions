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

# Item flags — mirrors ITEM_FLAGS in admin_dashboard.py (out_of_stock excluded)
_FLAGS_RAW = [
    ('low_stock',    'Low Stock',      '#ff8844'),
    ('hot_item',     'Hot Item',       '#ff4444'),
    ('new_arrival',  'New Arrival',    '#44aaff'),
    ('limited',      'Limited Supply', '#cc66ff'),
    ('popular',      'Popular',        '#44cc88'),
]

def _hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# key -> (label, fg_rgb, bg_rgb)
FLAG_DISPLAY = {
    k: (lbl, _hex_rgb(col), tuple(int(c * 0.18) for c in _hex_rgb(col)))
    for k, lbl, col in _FLAGS_RAW
}

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


def _draw_flag(d, x, y, text, fg, bg, font):
    """Draw a small flat badge at (x, y+4) inside a 20-px row. Returns badge right-edge x."""
    fw = tw(d, text, font) + 6
    d.rectangle([x, y + 4, x + fw, y + 15], fill=bg)
    d.text((x + 3, y + 5), text, font=font, fill=fg)
    return x + fw + 3   # next badge x (with 3-px gap)


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
    for i, (name, qty, price_pct, alliance_disc, flags) in enumerate(items_stock):
        row_bg = BG if i % 2 == 0 else BG2
        d.rectangle([0, y, IMG_W, y + ROW_H], fill=row_bg)

        # Dot
        d.ellipse([PAD, y + 6, PAD + 8, y + 14], fill=GREEN)

        # Measure total flag badge width so name can be truncated correctly
        flag_w = sum(tw(d, lbl, f_small) + 6 + 3 for lbl, _, _ in flags)

        # Name — truncated to leave room for flags
        name_avail = NAME_W - flag_w
        disp = truncate(d, name, f_item, name_avail)
        d.text((PAD + 12, y + 3), disp, font=f_item, fill=WHITE)

        # Flags — drawn immediately after the (possibly truncated) name
        fx = PAD + 12 + tw(d, disp, f_item) + 5
        for lbl, fg, bg in flags:
            fx = _draw_flag(d, fx, y, lbl, fg, bg, f_small)

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
        SELECT t.type_id, t.category, t.type_name, t.display_order,
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

    # Build flags lookup: type_id -> [(label, fg, bg), ...]
    flags_lookup: dict = {}
    for tid, fk in c.execute(
            "SELECT type_id, flag_key FROM item_flags WHERE flag_key != 'out_of_stock'"):
        if fk in FLAG_DISPLAY:
            flags_lookup.setdefault(tid, []).append(FLAG_DISPLAY[fk])

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

    for type_id, cat, name, disp_ord, qty, price_pct, alliance_disc in rows:
        if cat not in SHOW_CATS or not cat_visible.get(cat, True):
            continue
        if cat == 'ice_products'   and not ice_sub_visible(disp_ord):
            continue
        if cat == 'moon_materials' and not moon_sub_visible(disp_ord):
            continue
        entry = (name, qty, price_pct, alliance_disc, flags_lookup.get(type_id, []))
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
