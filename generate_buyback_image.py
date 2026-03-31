"""
generate_buyback_image.py

Generates two Discord-ready buyback PNGs:
  buyback_miners.png   — Minerals, Ice Products, Moon Materials, Gas Cloud Materials
  buyback_salvage.png  — Salvaged Materials, Research Equipment

Run any time: python generate_buyback_image.py
"""
import os, sqlite3, math
from collections import OrderedDict
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
FONT_DIR    = r'C:\Windows\Fonts'

# ── Palette ───────────────────────────────────────────────────────────────────
BG        = ( 10,  21,  32)
BG_HDR    = (  6,  14,  24)
BG_ROW_A  = ( 10,  21,  32)
BG_ROW_B  = ( 13,  26,  42)
BG_SECHDR = ( 14,  30,  50)
ACCENT    = (  0, 170, 255)
WHITE     = (232, 244, 255)
GREEN     = ( 68, 221, 136)
GOLD      = (255, 200,  50)
DIM       = ( 40,  68,  90)
SUBTEXT   = ( 90, 138, 170)
GRAY      = ( 90, 110, 130)

# ── Layout constants ──────────────────────────────────────────────────────────
W           = 900
PAD         = 24
ROW_H       = 22
SEC_H       = 28
GAP         = 12
COL_GAP     = 16
HDR_H       = 72
FOOTER_H    = 46
BUYBACK_BAR = 3
RATE_W      = 46
QUOTA_W     = 100

CAT_LABELS = {
    'minerals':            'Minerals',
    'ice_products':        'Ice Products',
    'moon_materials':      'Moon Materials',
    'gas_cloud_materials': 'Gas Cloud Materials',
    'research_equipment':  'Research Equipment',
    'salvaged_materials':  'Salvaged Materials',
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_font(name, size):
    try:    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except: return ImageFont.load_default()

def tw(d, text, font):
    bb = d.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def fmt_remaining(quota, stock):
    if quota == 0:
        return 'No Limit'
    return f'{max(0, quota - stock):,}'

def remaining_color(quota, stock):
    if quota == 0:
        return SUBTEXT
    remaining = max(0, quota - stock)
    if remaining == 0:
        return GRAY
    if remaining < quota * 0.25:
        return GOLD
    return GREEN

def truncate(d, text, font, max_w):
    if tw(d, text, font) <= max_w:
        return text
    while text and tw(d, text + '…', font) > max_w:
        text = text[:-1]
    return text + '…'

def section_height(items, two_col=True):
    if not items:
        return 0
    rows = math.ceil(len(items) / 2) if two_col else len(items)
    return SEC_H + rows * ROW_H

def pair_height(l_items, r_items):
    return max(section_height(l_items, two_col=False),
               section_height(r_items, two_col=False))

# ── Drawing primitives ────────────────────────────────────────────────────────
def draw_section_header(d, x, y, w, label, font):
    d.rectangle([x, y, x + w, y + SEC_H - 1], fill=BG_SECHDR)
    d.line([x, y, x + w, y], fill=ACCENT, width=1)
    d.text((x + 8, y + (SEC_H - tw(d, 'A', font)) // 2 - 1), label, font=font, fill=ACCENT)

def draw_row(d, x, y, col_w, name, rate, quota, stock, fonts, row_idx):
    f_item, f_qty, f_rate = fonts
    bg = BG_ROW_A if row_idx % 2 == 0 else BG_ROW_B
    d.rectangle([x, y, x + col_w, y + ROW_H - 1], fill=bg)
    d.rectangle([x, y, x + BUYBACK_BAR, y + ROW_H - 1], fill=GOLD)

    name_w  = col_w - BUYBACK_BAR - 6 - RATE_W - QUOTA_W - 8
    name_x  = x + BUYBACK_BAR + 5
    rate_x  = x + col_w - QUOTA_W - RATE_W - 4
    quota_x = x + col_w - QUOTA_W
    text_y  = y + (ROW_H - 13) // 2

    d.text((name_x, text_y), truncate(d, name, f_item, name_w), font=f_item, fill=WHITE)
    rate_str = f'{rate}%'
    d.text((rate_x + RATE_W - tw(d, rate_str, f_rate), text_y), rate_str, font=f_rate, fill=GOLD)
    q_str = fmt_remaining(quota, stock)
    d.text((quota_x + QUOTA_W - tw(d, q_str, f_qty), text_y), q_str, font=f_qty,
           fill=remaining_color(quota, stock))

def draw_single_col(d, x, y, col_w, items, fonts):
    for i, (name, rate, quota, stock) in enumerate(items):
        draw_row(d, x, y + i * ROW_H, col_w, name, rate, quota, stock, fonts, i)
    return y + len(items) * ROW_H

def draw_two_col(d, x, y, half_w, items, fonts):
    mid   = math.ceil(len(items) / 2)
    left  = items[:mid]
    right = items[mid:]
    cx    = [x, x + half_w + COL_GAP]
    for col_idx, col_items in enumerate((left, right)):
        for i, (name, rate, quota, stock) in enumerate(col_items):
            draw_row(d, cx[col_idx], y + i * ROW_H, half_w,
                     name, rate, quota, stock, fonts, i)
    return y + max(len(left), len(right)) * ROW_H

# ── Image builder ─────────────────────────────────────────────────────────────
def generate_image(cat_items, title, subtitle, ts_str, out_path,
                   pairs, fulls, fonts):
    """
    pairs: list of (left_cat, right_cat) rendered side-by-side
    fulls: list of cat keys rendered full-width in two columns
    """
    f_title, f_sub, f_hdr, item_fonts = fonts
    inner_w = W - 2 * PAD
    half_w  = (inner_w - COL_GAP) // 2
    full_w  = inner_w

    # Calculate canvas height
    content_h = 0
    for lc, rc in pairs:
        l = cat_items.get(lc, [])
        r = cat_items.get(rc, [])
        if l or r:
            content_h += pair_height(l, r) + GAP
    for cat in fulls:
        items = cat_items.get(cat, [])
        if items:
            content_h += section_height(items, two_col=True) + GAP

    H = HDR_H + PAD + content_h + PAD + FOOTER_H

    img = Image.new('RGB', (W, H), BG)
    d   = ImageDraw.Draw(img)

    # Header
    d.rectangle([0, 0, W, HDR_H], fill=BG_HDR)
    d.line([0, HDR_H - 1, W, HDR_H - 1], fill=ACCENT, width=1)
    d.text(((W - tw(d, title, f_title)) // 2, 14), title, font=f_title, fill=WHITE)
    d.text(((W - tw(d, subtitle, f_sub)) // 2, 42), subtitle, font=f_sub, fill=SUBTEXT)
    d.text((W - PAD - tw(d, ts_str, f_sub), 56), ts_str, font=f_sub, fill=DIM)

    # Column header labels
    rate_lbl  = 'Rate'
    quota_lbl = 'Buying'
    d.text((W - PAD - QUOTA_W - RATE_W - tw(d, rate_lbl, f_sub) // 2, 57),
           rate_lbl, font=f_sub, fill=DIM)
    d.text((W - PAD - QUOTA_W + (QUOTA_W - tw(d, quota_lbl, f_sub)) // 2, 57),
           quota_lbl, font=f_sub, fill=DIM)

    # Body
    y = HDR_H + PAD

    for lc, rc in pairs:
        l_items = cat_items.get(lc, [])
        r_items = cat_items.get(rc, [])
        if not l_items and not r_items:
            continue
        lx = PAD
        rx = PAD + half_w + COL_GAP
        if l_items:
            draw_section_header(d, lx, y, half_w, CAT_LABELS.get(lc, lc), f_hdr)
        if r_items:
            draw_section_header(d, rx, y, half_w, CAT_LABELS.get(rc, rc), f_hdr)
        body_y = y + SEC_H
        if l_items:
            draw_single_col(d, lx, body_y, half_w, l_items, item_fonts)
        if r_items:
            draw_single_col(d, rx, body_y, half_w, r_items, item_fonts)
        y += pair_height(l_items, r_items) + GAP

    for cat in fulls:
        items = cat_items.get(cat, [])
        if not items:
            continue
        draw_section_header(d, PAD, y, full_w, CAT_LABELS.get(cat, cat), f_hdr)
        draw_two_col(d, PAD, y + SEC_H, half_w, items, item_fonts)
        y += section_height(items, two_col=True) + GAP

    # Footer
    fy = H - FOOTER_H
    d.line([0, fy, W, fy], fill=DIM, width=1)
    d.rectangle([PAD, fy + 16, PAD + BUYBACK_BAR, fy + 30], fill=GOLD)
    d.text((PAD + BUYBACK_BAR + 6, fy + 15), 'Buyback accepted', font=f_sub, fill=SUBTEXT)
    d.text((PAD + 160, fy + 15), 'Rate = % of Jita Buy Value', font=f_sub, fill=SUBTEXT)
    d.text((PAD + 340, fy + 15),
           'Buying = units still wanted  (No Limit = unlimited)  |  Yellow = almost full',
           font=f_sub, fill=SUBTEXT)
    cats_shown = [c for p in pairs for c in p] + fulls
    total = sum(len(cat_items.get(c, [])) for c in cats_shown)
    total_str = f'{total} items  ·  stock as of {ts_str}'
    d.text(((W - tw(d, total_str, f_sub)) // 2, fy + 30), total_str, font=f_sub, fill=DIM)

    img.save(out_path, optimize=True)
    print(f'Saved: {out_path}  ({W}x{H}px)')


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''SELECT t.category, t.type_name, t.buyback_rate, t.buyback_quota,
                        COALESCE(i.quantity, 0) as current_stock
                 FROM tracked_market_items t
                 LEFT JOIN lx_zoj_current_inventory i ON i.type_id = t.type_id
                 WHERE t.buyback_accepted = 1
                 ORDER BY t.category, t.display_order, t.type_name''')
    rows = c.fetchall()

    snap_ts = c.execute(
        'SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory'
    ).fetchone()[0] or ''
    conn.close()

    cat_items = OrderedDict()
    for cat, name, rate, quota, stock in rows:
        cat_items.setdefault(cat, []).append((name, rate, quota, stock))

    try:
        ts_str = datetime.fromisoformat(snap_ts).strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = datetime.now(timezone.utc).strftime('%d %b %Y  %H:%M UTC')

    # Fonts
    f_title    = load_font('segoeuib.ttf', 22)
    f_sub      = load_font('segoeui.ttf',  11)
    f_hdr      = load_font('segoeuib.ttf', 12)
    f_item     = load_font('segoeui.ttf',  13)
    f_qty      = load_font('segoeuib.ttf', 12)
    f_rate     = load_font('segoeuib.ttf', 12)
    item_fonts = (f_item, f_qty, f_rate)
    fonts      = (f_title, f_sub, f_hdr, item_fonts)

    sub = 'Items currently accepted  ·  Contact Hamektok Hakaari on Discord to sell'

    # Image 1: Miners — Minerals, Ice, Moon, Gas
    generate_image(
        cat_items,
        title     = 'LX-ZOJ  ·  BUYBACK  —  MINING & GAS',
        subtitle  = sub,
        ts_str    = ts_str,
        out_path  = os.path.join(PROJECT_DIR, 'buyback_miners.png'),
        pairs     = [('minerals', 'ice_products'),
                     ('moon_materials', 'gas_cloud_materials')],
        fulls     = [],
        fonts     = fonts,
    )

    # Image 2: Salvage & Research
    generate_image(
        cat_items,
        title     = 'LX-ZOJ  ·  BUYBACK  —  SALVAGE & RESEARCH',
        subtitle  = sub,
        ts_str    = ts_str,
        out_path  = os.path.join(PROJECT_DIR, 'buyback_salvage.png'),
        pairs     = [],
        fulls     = ['salvaged_materials', 'research_equipment'],
        fonts     = fonts,
    )


if __name__ == '__main__':
    main()
