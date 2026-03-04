"""
generate_fuel_image.py

Creates a Discord-ready PNG showing current fuel (ice products) stock at LX-ZOJ.
Designed for posting in main alliance/corp Discord channels.
Run any time to regenerate:  python generate_fuel_image.py
Output: fuel_image.png
"""
import sqlite3
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
OUT_PATH    = os.path.join(PROJECT_DIR, 'fuel_image.png')
FONT_DIR    = r'C:\Windows\Fonts'

# ── Palette ──────────────────────────────────────────────────────────────────
BG       = ( 10,  21,  32)
BG_HDR   = (  6,  14,  24)
BG_ROW_A = ( 10,  21,  32)
BG_ROW_B = ( 13,  26,  42)
ACCENT   = (  0, 170, 255)
WHITE    = (232, 244, 255)
SUBTEXT  = ( 90, 138, 170)
GREEN    = ( 68, 221, 136)
YELLOW   = (255, 200,  50)
RED      = (255,  80,  80)
GRAY     = ( 90, 110, 130)
DIM      = ( 40,  68,  90)
GOLD     = (255, 200,  50)

# ── Layout ───────────────────────────────────────────────────────────────────
W      = 800
PAD    = 28
ROW_H  = 32   # taller rows — more readable for a focused image
BB_BAR = 3

LOW_THRESHOLD = 50_000   # below this → yellow LOW

# ── Helpers ──────────────────────────────────────────────────────────────────
def load_font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except Exception:
        return ImageFont.load_default()

def fmt_qty(n):
    if   n >= 1_000_000_000: return f'{n / 1_000_000_000:.2f}B'
    elif n >= 1_000_000:      return f'{n / 1_000_000:.1f}M'
    elif n >= 1_000:          return f'{n / 1_000:.1f}K'
    return f'{n:,}'

def tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

# ── Fonts ────────────────────────────────────────────────────────────────────
F_TITLE = load_font('segoeuib.ttf', 26)
F_HDR   = load_font('segoeuib.ttf', 14)
F_ITEM  = load_font('segoeui.ttf',  15)
F_QTY   = load_font('segoeuib.ttf', 15)
F_SUB   = load_font('segoeui.ttf',  12)
F_TAG   = load_font('segoeuib.ttf', 10)


def draw_fuel_row(draw, x, y, col_w, name, qty, buyback, row_bg):
    draw.rectangle([(x, y), (x + col_w, y + ROW_H - 1)], fill=row_bg)

    if buyback:
        draw.rectangle([(x, y), (x + BB_BAR, y + ROW_H - 1)], fill=GOLD)

    name_x = x + BB_BAR + 7

    if qty == 0:
        name_color = GRAY
        qty_str    = 'OUT'
        qty_color  = RED
    elif qty < LOW_THRESHOLD:
        name_color = WHITE
        qty_str    = fmt_qty(qty)
        qty_color  = YELLOW
    else:
        name_color = WHITE
        qty_str    = fmt_qty(qty)
        qty_color  = GREEN

    qw = tw(draw, qty_str, F_QTY)
    draw.text((name_x,            y + 8), name,    font=F_ITEM, fill=name_color)
    draw.text((x + col_w - qw,    y + 8), qty_str, font=F_QTY,  fill=qty_color)


def draw_group(draw, label, items, x, y, col_w):
    """Draw a labelled group. Returns final y."""
    draw.text((x, y), label, font=F_HDR, fill=ACCENT)
    line_y = y + 20
    draw.line([(x, line_y), (x + col_w, line_y)], fill=DIM, width=1)
    y = line_y + 4

    for i, (name, qty, buyback) in enumerate(items):
        row_bg = BG_ROW_B if i % 2 == 1 else BG_ROW_A
        draw_fuel_row(draw, x, y, col_w, name, qty, buyback, row_bg)
        y += ROW_H

    return y


def main():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # Load visibility flags from site_config
    vis_rows = c.execute(
        "SELECT key, value FROM site_config WHERE key LIKE 'market_sub_ice_%'"
    ).fetchall()
    vis = {k: (str(v) == '1') for k, v in vis_rows}
    show_fuel     = vis.get('market_sub_ice_products_fuel_blocks', True)
    show_refined  = vis.get('market_sub_ice_products_refined_ice', True)
    show_isotopes = vis.get('market_sub_ice_products_isotopes',    True)

    def ice_sub_visible(display_order):
        if display_order <= 8:   return show_fuel
        if display_order <= 11:  return show_refined
        return show_isotopes

    c.execute('''
        SELECT t.type_name, i.quantity, tm.buyback_accepted, tm.display_order
        FROM lx_zoj_current_inventory i
        JOIN tracked_market_items tm ON i.type_id = tm.type_id
        JOIN inv_types t             ON i.type_id = t.type_id
        WHERE tm.category = 'ice_products'
        ORDER BY tm.display_order
    ''')
    all_ice = [r for r in c.fetchall() if ice_sub_visible(r[3])]

    c.execute('SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory')
    snap_ts = c.fetchone()[0] or ''
    conn.close()

    if not all_ice:
        print('No visible ice product sub-categories — nothing to render.')
        return

    # Split into isotopes vs auxiliaries (fuel blocks + refined ice)
    isotope_names = {'Oxygen Isotopes', 'Hydrogen Isotopes',
                     'Helium Isotopes', 'Nitrogen Isotopes'}
    isotopes = [(n, q, b) for n, q, b, _ in all_ice if n     in isotope_names]
    aux      = [(n, q, b) for n, q, b, _ in all_ice if n not in isotope_names]

    try:
        dt     = datetime.fromisoformat(snap_ts)
        ts_str = dt.strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = snap_ts

    # ── Layout heights ────────────────────────────────────────────────────
    HDR_H   = 76
    SEC_H   = 26
    FOOTER  = 46
    GAP     = 18
    COL_GAP = 20

    col_w  = (W - PAD * 2 - COL_GAP) // 2
    full_w = W - PAD * 2

    show_iso = bool(isotopes)
    show_aux = bool(aux)

    if show_iso and show_aux:
        body_h = max(SEC_H + len(isotopes) * ROW_H, SEC_H + len(aux) * ROW_H)
    elif show_iso:
        body_h = SEC_H + len(isotopes) * ROW_H
    else:
        body_h = SEC_H + len(aux) * ROW_H

    total_h = HDR_H + PAD + body_h + GAP + FOOTER

    # ── Render ───────────────────────────────────────────────────────────
    img  = Image.new('RGB', (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([(0, 0), (W, HDR_H)], fill=BG_HDR)
    draw.line([(0, HDR_H), (W, HDR_H)], fill=ACCENT, width=2)
    draw.text((PAD, 12), 'LX-ZOJ  ·  FUEL STOCK', font=F_TITLE, fill=WHITE)
    draw.text((PAD, 50), f'Updated  {ts_str}', font=F_SUB, fill=SUBTEXT)

    y   = HDR_H + PAD
    x_l = PAD
    x_r = PAD + col_w + COL_GAP

    if show_iso and show_aux:
        draw_group(draw, 'ISOTOPES',              isotopes, x_l, y, col_w)
        draw_group(draw, 'FUEL BLOCK COMPONENTS', aux,      x_r, y, col_w)
    elif show_iso:
        draw_group(draw, 'ISOTOPES',              isotopes, x_l, y, full_w)
    else:
        draw_group(draw, 'FUEL BLOCK COMPONENTS', aux,      x_l, y, full_w)

    # Footer
    footer_y = total_h - FOOTER
    draw.line([(0, footer_y), (W, footer_y)], fill=DIM, width=1)

    # Legend
    lx = PAD
    ly = footer_y + 10
    draw.rectangle([(lx, ly + 1), (lx + BB_BAR, ly + 13)], fill=GOLD)
    draw.text((lx + BB_BAR + 5, ly), 'Buyback accepted', font=F_SUB, fill=SUBTEXT)

    low_x = lx + BB_BAR + 5 + tw(draw, 'Buyback accepted', F_SUB) + 18
    draw.text((low_x, ly), 'LOW', font=F_TAG, fill=YELLOW)
    draw.text((low_x + tw(draw, 'LOW', F_TAG) + 6, ly), f'= Under {LOW_THRESHOLD//1000}K units', font=F_SUB, fill=SUBTEXT)

    note = '@ or DM Hamektok Hakaari on Discord to purchase'
    nw   = tw(draw, note, F_SUB)
    draw.text(((W - nw) // 2, footer_y + 28), note, font=F_SUB, fill=SUBTEXT)

    img.save(OUT_PATH, optimize=True)
    print(f'Saved:  {OUT_PATH}')
    print(f'Size      {W} x {total_h} px')


if __name__ == '__main__':
    main()
