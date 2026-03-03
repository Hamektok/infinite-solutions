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
RED      = (255,  80,  80)
DIM      = ( 40,  68,  90)
GRAY     = ( 90, 110, 130)
GOLD     = (255, 200,  50)

# ── Layout ───────────────────────────────────────────────────────────────────
W        = 900
PAD      = 24
ROW_H    = 24
COL_GAP  = 20
BB_BAR   = 3   # buyback indicator bar width

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
F_TITLE = load_font('segoeuib.ttf', 24)
F_HDR   = load_font('segoeuib.ttf', 13)
F_ITEM  = load_font('segoeui.ttf',  13)
F_QTY   = load_font('segoeuib.ttf', 13)
F_SUB   = load_font('segoeui.ttf',  12)
F_TAG   = load_font('segoeuib.ttf', 10)


def draw_item_row(draw, x, y, col_w, name, qty, buyback, row_bg):
    """Draw a single item row. Items have (name, qty, buyback_accepted)."""
    in_stock = qty > 0

    draw.rectangle([(x, y), (x + col_w, y + ROW_H - 1)], fill=row_bg)

    # Buyback indicator — gold vertical bar on left edge
    if buyback:
        draw.rectangle([(x, y), (x + BB_BAR, y + ROW_H - 1)], fill=GOLD)

    name_x = x + BB_BAR + 5
    name_color = WHITE if in_stock else GRAY

    if in_stock:
        qty_str   = fmt_qty(qty)
        qty_color = GREEN
    else:
        qty_str   = 'OUT'
        qty_color = RED

    qw = tw(draw, qty_str, F_QTY)
    draw.text((name_x,             y + 4), name,    font=F_ITEM, fill=name_color)
    draw.text((x + col_w - qw,     y + 4), qty_str, font=F_QTY,  fill=qty_color)


def draw_section(draw, label, items, x, y, col_w):
    """Draw a labelled two-column section. items = [(name, qty, buyback), ...]"""
    draw.text((x, y), label, font=F_HDR, fill=ACCENT)
    line_y = y + 18
    draw.line([(x, line_y), (x + col_w, line_y)], fill=DIM, width=1)
    y = line_y + 5

    for i, (name, qty, buyback) in enumerate(items):
        row_bg = BG_ROW_B if i % 2 == 1 else BG_ROW_A
        draw_item_row(draw, x, y, col_w, name, qty, buyback, row_bg)
        y += ROW_H

    return y


def main():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # Fetch ALL items (including out of stock) with buyback flag
    c.execute('''
        SELECT tm.category, t.type_name, i.quantity, tm.buyback_accepted
        FROM lx_zoj_current_inventory i
        JOIN tracked_market_items tm ON i.type_id = tm.type_id
        JOIN inv_types t             ON i.type_id = t.type_id
        WHERE tm.category IN ('minerals', 'ice_products', 'moon_materials')
        ORDER BY tm.category, tm.display_order
    ''')
    rows = c.fetchall()

    c.execute('SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory')
    snap_ts = c.fetchone()[0] or ''
    conn.close()

    by_cat = {}
    for cat, name, qty, buyback in rows:
        by_cat.setdefault(cat, []).append((name, qty, buyback))

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
    SEC_HDR = 24
    FOOTER  = 46   # taller to fit legend
    GAP     = 16

    col_w     = (W - PAD * 2 - COL_GAP) // 2
    half_moon = (len(moon_mats) + 1) // 2

    top_rows = max(len(minerals), len(ice))
    top_h    = SEC_HDR + top_rows * ROW_H + GAP
    moon_h   = SEC_HDR + half_moon * ROW_H + GAP

    total_h  = HDR_H + PAD + top_h + GAP + moon_h + FOOTER

    # ── Render ───────────────────────────────────────────────────────────
    img  = Image.new('RGB', (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([(0, 0), (W, HDR_H)], fill=BG_HDR)
    draw.line([(0, HDR_H), (W, HDR_H)], fill=ACCENT, width=2)
    draw.text((PAD, 12), 'LX-ZOJ  ·  MINERAL & MATERIALS STOCK', font=F_TITLE, fill=WHITE)
    draw.text((PAD, 46), f'Updated  {ts_str}', font=F_SUB, fill=SUBTEXT)

    y   = HDR_H + PAD
    x_l = PAD
    x_r = PAD + col_w + COL_GAP

    # Minerals (left) + Ice Products (right)
    y_after_l = draw_section(draw, 'MINERALS',     minerals, x_l, y, col_w)
    y_after_r = draw_section(draw, 'ICE PRODUCTS', ice,      x_r, y, col_w)
    y = max(y_after_l, y_after_r) + GAP

    # Moon materials — full-width header, two-column rows with shared stripes
    full_w = W - PAD * 2
    draw.text((x_l, y), 'MOON MATERIALS', font=F_HDR, fill=ACCENT)
    line_y = y + 18
    draw.line([(x_l, line_y), (x_l + full_w, line_y)], fill=DIM, width=1)
    yr = line_y + 5

    left_moon  = moon_mats[:half_moon]
    right_moon = moon_mats[half_moon:]

    for i in range(half_moon):
        row_bg = BG_ROW_B if i % 2 == 1 else BG_ROW_A
        draw.rectangle([(x_l, yr), (x_l + full_w, yr + ROW_H - 1)], fill=row_bg)
        if i < len(left_moon):
            name, qty, buyback = left_moon[i]
            draw_item_row(draw, x_l, yr, col_w, name, qty, buyback, row_bg)
        if i < len(right_moon):
            name, qty, buyback = right_moon[i]
            draw_item_row(draw, x_r, yr, col_w, name, qty, buyback, row_bg)
        yr += ROW_H

    # Footer with legend
    footer_y = total_h - FOOTER
    draw.line([(0, footer_y), (W, footer_y)], fill=DIM, width=1)

    # Legend: buyback indicator explanation
    lx = PAD
    ly = footer_y + 10
    draw.rectangle([(lx, ly + 1), (lx + BB_BAR, ly + 13)], fill=GOLD)
    draw.text((lx + BB_BAR + 5, ly), 'Buyback accepted', font=F_SUB, fill=SUBTEXT)

    dot_x = lx + BB_BAR + 5 + tw(draw, 'Buyback accepted', F_SUB) + 20
    out_w = tw(draw, 'OUT', F_TAG)
    draw.rectangle([(dot_x, ly + 1), (dot_x + out_w + 6, ly + 13)], fill=(40, 15, 15))
    draw.text((dot_x + 3, ly), 'OUT', font=F_TAG, fill=RED)
    draw.text((dot_x + out_w + 10, ly), '= Out of stock', font=F_SUB, fill=SUBTEXT)

    note = '@ or DM Hamektok Hakaari on Discord to purchase  ·  corp members only'
    nw   = tw(draw, note, F_SUB)
    draw.text(((W - nw) // 2, footer_y + 28), note, font=F_SUB, fill=SUBTEXT)

    img.save(OUT_PATH, optimize=True)
    print(f'Saved:  {OUT_PATH}')
    print(f'Size      {W} x {total_h} px')


if __name__ == '__main__':
    main()
