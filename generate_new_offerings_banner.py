"""
generate_new_offerings_banner.py

Discord announcement banner for LX-ZOJ's new market categories:
  Fuel Blocks, Gas Cloud Materials, Research Equipment, Salvaged Materials

Output: new_offerings_banner.png
Run any time:  python generate_new_offerings_banner.py
"""
import sqlite3, os
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(PROJECT_DIR, 'mydatabase.db')
OUT_PATH = os.path.join(PROJECT_DIR, 'new_offerings_banner.png')
FONT_DIR = r'C:\Windows\Fonts'

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = (  8,  14,  24)
BG2      = ( 12,  20,  34)
BG_PANEL = ( 11,  19,  31)
WHITE    = (220, 238, 255)
DIM      = ( 70, 100, 128)
SUBTEXT  = ( 90, 138, 170)
GREEN    = ( 50, 210, 120)

FUEL_COL = ( 80, 180, 255)
GAS_COL  = (  0, 220, 140)
RES_COL  = (180, 120, 255)
SAL_COL  = (255, 140,  60)

# ── Layout ────────────────────────────────────────────────────────────────────
W        = 1200
PAD      = 22
GAP      = 12
HDR_H    = 96
FOOTER_H = 46
PANEL_H  = 280
PANEL_W  = (W - 2 * PAD - 3 * GAP) // 4
H        = HDR_H + PAD + PANEL_H + PAD + FOOTER_H

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_font(name, size):
    try:    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except: return ImageFont.load_default()

def tw(d, text, font):
    bb = d.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def center_x(d, text, font, panel_x, panel_w, y, fill):
    x = panel_x + (panel_w - tw(d, text, font)) // 2
    d.text((x, y), text, font=font, fill=fill)


def draw_panel(d, px, py, colour, title, subcategories, in_stock, total, fonts):
    """
    subcategories: list of strings — one per line in the panel body
    """
    f_title, f_sub_line, f_stock = fonts

    STRIPE   = 52
    STOCK_H  = 30
    LINE_H   = 22
    DOT_R    = 3

    # Panel background
    d.rectangle([px, py, px + PANEL_W, py + PANEL_H], fill=BG_PANEL)

    # Coloured top stripe
    d.rectangle([px, py, px + PANEL_W, py + STRIPE], fill=colour)

    # Darken stripe for text legibility
    overlay = Image.new('RGBA', (PANEL_W, STRIPE), (0, 0, 0, 60))
    d._image.paste(overlay, (px, py), overlay)

    # Category title centred on stripe
    ty = py + (STRIPE - (f_title.size if hasattr(f_title, 'size') else 16)) // 2
    center_x(d, title, f_title, px, PANEL_W, ty, BG)

    # Subcategory lines — centred with a coloured dot
    y = py + STRIPE + 18
    for label in subcategories:
        text_w = tw(d, label, f_sub_line)
        total_w = DOT_R * 2 + 8 + text_w
        lx = px + (PANEL_W - total_w) // 2
        mid_y = y + (LINE_H // 2)
        d.ellipse([lx, mid_y - DOT_R, lx + DOT_R * 2, mid_y + DOT_R], fill=colour)
        d.text((lx + DOT_R * 2 + 8, y + (LINE_H - (f_sub_line.size if hasattr(f_sub_line, 'size') else 11)) // 2),
               label, font=f_sub_line, fill=WHITE)
        y += LINE_H

    # Stock strip at bottom
    stock_y = py + PANEL_H - STOCK_H
    d.rectangle([px, stock_y, px + PANEL_W, py + PANEL_H], fill=(14, 24, 38))
    stock_str = f'{in_stock} of {total} lines currently in stock'
    center_x(d, stock_str, f_stock, px, PANEL_W, stock_y + 9, GREEN)


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    def get_stock(cat):
        c.execute('''
            SELECT COUNT(*), SUM(CASE WHEN i.quantity > 0 THEN 1 ELSE 0 END)
            FROM tracked_market_items t
            JOIN lx_zoj_current_inventory i ON t.type_id = i.type_id
            WHERE t.category = ?
        ''', (cat,))
        total, stocked = c.fetchone()
        return total or 0, stocked or 0

    # Fuel blocks = ice_products with display_order <= 8
    c.execute('''
        SELECT COUNT(*), SUM(CASE WHEN i.quantity > 0 THEN 1 ELSE 0 END)
        FROM tracked_market_items t
        JOIN lx_zoj_current_inventory i ON t.type_id = i.type_id
        WHERE t.category = 'ice_products' AND t.display_order <= 8
    ''')
    fuel_row = c.fetchone()
    fuel_total, fuel_in = fuel_row[0] or 0, fuel_row[1] or 0

    gas_total, gas_in = get_stock('gas_cloud_materials')
    res_total, res_in = get_stock('research_equipment')
    sal_total, sal_in = get_stock('salvaged_materials')

    snap_ts = c.execute(
        'SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory'
    ).fetchone()[0] or ''
    conn.close()

    try:
        ts_str = datetime.fromisoformat(snap_ts).strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = datetime.now(timezone.utc).strftime('%d %b %Y  %H:%M UTC')

    # ── Fonts ─────────────────────────────────────────────────────────────────
    f_hero   = load_font('segoeuib.ttf', 26)   # main header title
    f_badge  = load_font('segoeuib.ttf', 12)   # "now stocking" badge
    f_sub    = load_font('segoeui.ttf',  11)   # header subtitle + footer
    f_ptitle = load_font('segoeuib.ttf', 16)   # panel category title
    f_line   = load_font('segoeui.ttf',  12)   # subcategory lines
    f_stock  = load_font('segoeuib.ttf',  9)   # stock strip text
    panel_fonts = (f_ptitle, f_line, f_stock)

    # ── Canvas ─────────────────────────────────────────────────────────────────
    img = Image.new('RGB', (W, H), BG)
    d   = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    d.rectangle([0, 0, W, HDR_H], fill=BG2)

    # Quad-colour top stripe
    seg = W // 4
    d.rectangle([0,       0, seg,     5], fill=FUEL_COL)
    d.rectangle([seg,     0, seg * 2, 5], fill=GAS_COL)
    d.rectangle([seg * 2, 0, seg * 3, 5], fill=RES_COL)
    d.rectangle([seg * 3, 0, W,       5], fill=SAL_COL)

    # "NOW STOCKING" badge
    badge = '★  NOW STOCKING'
    bw = tw(d, badge, f_badge) + 20
    bx = (W - bw) // 2
    d.rectangle([bx, 12, bx + bw, 30], fill=(18, 55, 28))
    d.rectangle([bx, 12, bx + bw, 30], outline=(50, 210, 120), width=1)
    d.text((bx + 10, 13), badge, font=f_badge, fill=GREEN)

    # Title
    title = 'LX-ZOJ  ·  INFINITE SOLUTIONS'
    d.text(((W - tw(d, title, f_hero)) // 2, 36), title, font=f_hero, fill=WHITE)

    # Subtitle
    sub = 'New market offerings — visit the Materials & Resources Market tab'
    d.text(((W - tw(d, sub, f_sub)) // 2, 70), sub, font=f_sub, fill=SUBTEXT)

    # ── Panels ────────────────────────────────────────────────────────────────
    py = HDR_H + PAD
    px_fuel = PAD
    px_gas  = PAD + PANEL_W + GAP
    px_res  = PAD + 2 * (PANEL_W + GAP)
    px_sal  = PAD + 3 * (PANEL_W + GAP)

    draw_panel(d, px_fuel, py, FUEL_COL,
               'FUEL BLOCKS',
               ['Amarr Fuel Block', 'Caldari Fuel Block',
                'Gallente Fuel Block', 'Minmatar Fuel Block'],
               fuel_in, fuel_total, panel_fonts)

    draw_panel(d, px_gas, py, GAS_COL,
               'GAS CLOUD MATERIALS',
               ['Compressed Fullerenes', 'Compressed Booster Gas',
                'Uncompressed Fullerenes', 'Uncompressed Booster Gas'],
               gas_in, gas_total, panel_fonts)

    draw_panel(d, px_res, py, RES_COL,
               'RESEARCH EQUIPMENT',
               ['Datacores', 'Decryptors'],
               res_in, res_total, panel_fonts)

    draw_panel(d, px_sal, py, SAL_COL,
               'SALVAGED MATERIALS',
               ['Common', 'Uncommon', 'Rare', 'Very Rare', 'Rogue Drone'],
               sal_in, sal_total, panel_fonts)

    # ── Footer ────────────────────────────────────────────────────────────────
    fy = H - FOOTER_H
    d.line([0, fy, W, fy], fill=(18, 30, 46), width=1)
    contact = '@ or DM  Hamektok Hakaari  on Discord to purchase  ·  corp members only'
    d.text(((W - tw(d, contact, f_sub)) // 2, fy + 8),  contact, font=f_sub, fill=SUBTEXT)
    updated = f'Stock as of  {ts_str}'
    d.text(((W - tw(d, updated, f_sub)) // 2, fy + 24), updated, font=f_sub, fill=DIM)

    img.save(OUT_PATH, optimize=True)
    print(f'Saved: {OUT_PATH}  ({W}×{H}px)')


if __name__ == '__main__':
    main()
