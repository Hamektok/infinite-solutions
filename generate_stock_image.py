"""
generate_stock_image.py

Creates a Discord-ready PNG showing current mineral and materials stock at LX-ZOJ.
Run any time to regenerate:  python generate_stock_image.py
Output: stock_image.png
"""
import sqlite3
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
OUT_PATH    = os.path.join(PROJECT_DIR, 'stock_image.png')
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
DIM      = ( 40,  68,  90)
GOLD     = (255, 204,  68)

# ── Layout ───────────────────────────────────────────────────────────────────
W       = 900
PAD     = 24
ROW_H   = 24
COL_GAP = 20

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

def th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]

# ── Fonts ────────────────────────────────────────────────────────────────────
F_TITLE = load_font('segoeuib.ttf', 24)
F_HDR   = load_font('segoeuib.ttf', 13)
F_ITEM  = load_font('segoeui.ttf',  13)
F_QTY   = load_font('segoeuib.ttf', 13)
F_SUB   = load_font('segoeui.ttf',  12)


def draw_section(draw, label, items, x, y, col_w, show_alternating=True):
    """Draw a labelled section: header line then item rows. Returns final y."""
    # Section label
    draw.text((x, y), label, font=F_HDR, fill=ACCENT)
    line_y = y + 18
    draw.line([(x, line_y), (x + col_w, line_y)], fill=DIM, width=1)
    y = line_y + 5

    for i, (name, qty) in enumerate(items):
        row_bg = BG_ROW_B if (i % 2 == 1 and show_alternating) else BG_ROW_A
        draw.rectangle([(x, y), (x + col_w, y + ROW_H - 1)], fill=row_bg)
        qty_str = fmt_qty(qty)
        qw = tw(draw, qty_str, F_QTY)
        draw.text((x + 6,          y + 4), name,    font=F_ITEM, fill=WHITE)
        draw.text((x + col_w - qw, y + 4), qty_str, font=F_QTY,  fill=GREEN)
        y += ROW_H

    return y


def main():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute('''
        SELECT tm.category, t.type_name, i.quantity
        FROM lx_zoj_current_inventory i
        JOIN tracked_market_items tm ON i.type_id = tm.type_id
        JOIN inv_types t             ON i.type_id = t.type_id
        WHERE i.quantity > 0
        ORDER BY tm.category, tm.display_order
    ''')
    rows = c.fetchall()

    c.execute('SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory')
    snap_ts = c.fetchone()[0] or ''
    conn.close()

    by_cat = {}
    for cat, name, qty in rows:
        by_cat.setdefault(cat, []).append((name, qty))

    minerals  = by_cat.get('minerals',       [])
    ice       = by_cat.get('ice_products',   [])
    moon_mats = by_cat.get('moon_materials', [])

    try:
        dt     = datetime.fromisoformat(snap_ts)
        ts_str = dt.strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = snap_ts

    # ── Calculate heights ─────────────────────────────────────────────────
    HDR_H   = 72
    SEC_HDR = 24   # label + divider
    FOOTER  = 34
    GAP     = 16

    col_w     = (W - PAD * 2 - COL_GAP) // 2
    half_moon = (len(moon_mats) + 1) // 2

    top_rows  = max(len(minerals), len(ice))
    top_h     = SEC_HDR + top_rows * ROW_H + GAP

    moon_h    = SEC_HDR + half_moon * ROW_H + GAP

    total_h   = HDR_H + PAD + top_h + GAP + moon_h + FOOTER

    # ── Render ───────────────────────────────────────────────────────────
    img  = Image.new('RGB', (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([(0, 0), (W, HDR_H)], fill=BG_HDR)
    draw.line([(0, HDR_H), (W, HDR_H)], fill=ACCENT, width=2)

    title = 'LX-ZOJ  ·  MINERAL & MATERIALS STOCK'
    draw.text((PAD, 12), title, font=F_TITLE, fill=WHITE)
    draw.text((PAD, 46), f'Updated  {ts_str}', font=F_SUB, fill=SUBTEXT)

    y = HDR_H + PAD

    # Minerals (left) + Ice Products (right)
    x_l = PAD
    x_r = PAD + col_w + COL_GAP

    y_after_l = draw_section(draw, 'MINERALS',     minerals, x_l, y, col_w)
    y_after_r = draw_section(draw, 'ICE PRODUCTS', ice,      x_r, y, col_w)

    y = max(y_after_l, y_after_r) + GAP

    # Moon materials — full-width header, two-column rows side by side
    full_w = W - PAD * 2
    draw.text((x_l, y), 'MOON MATERIALS', font=F_HDR, fill=ACCENT)
    line_y = y + 18
    draw.line([(x_l, line_y), (x_l + full_w, line_y)], fill=DIM, width=1)
    yr = line_y + 5

    left_moon  = moon_mats[:half_moon]
    right_moon = moon_mats[half_moon:]

    for i in range(half_moon):
        row_bg = BG_ROW_B if (i % 2 == 1) else BG_ROW_A
        # Full-width alternating stripe
        draw.rectangle([(x_l, yr), (x_l + full_w, yr + ROW_H - 1)], fill=row_bg)
        # Left item
        if i < len(left_moon):
            name, qty = left_moon[i]
            qty_str = fmt_qty(qty)
            qw = tw(draw, qty_str, F_QTY)
            draw.text((x_l + 6,          yr + 4), name,    font=F_ITEM, fill=WHITE)
            draw.text((x_l + col_w - qw, yr + 4), qty_str, font=F_QTY,  fill=GREEN)
        # Right item
        if i < len(right_moon):
            name, qty = right_moon[i]
            qty_str = fmt_qty(qty)
            qw = tw(draw, qty_str, F_QTY)
            draw.text((x_r + 6,          yr + 4), name,    font=F_ITEM, fill=WHITE)
            draw.text((x_r + col_w - qw, yr + 4), qty_str, font=F_QTY,  fill=GREEN)
        yr += ROW_H

    # Footer
    footer_y = total_h - FOOTER
    draw.line([(0, footer_y), (W, footer_y)], fill=DIM, width=1)
    note = '@ or DM Hamektok Hakaari on Discord to purchase  ·  corp members only'
    nw = tw(draw, note, F_SUB)
    draw.text(((W - nw) // 2, footer_y + 10), note, font=F_SUB, fill=SUBTEXT)

    img.save(OUT_PATH, optimize=True)
    print(f'Saved:  {OUT_PATH}')
    print(f'Size      {W} × {total_h} px')


if __name__ == '__main__':
    main()
