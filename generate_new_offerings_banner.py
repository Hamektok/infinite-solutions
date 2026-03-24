"""
generate_new_offerings_banner.py

Discord announcement banner for LX-ZOJ's new market categories:
  Gas Cloud Materials, Research Equipment, Salvaged Materials

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

GAS_COL  = (  0, 220, 140)
RES_COL  = (180, 120, 255)
SAL_COL  = (255, 140,  60)

# ── Layout ────────────────────────────────────────────────────────────────────
W        = 940
PAD      = 22
GAP      = 14
HDR_H    = 96
FOOTER_H = 46
PANEL_H  = 280
PANEL_W  = (W - 2 * PAD - 2 * GAP) // 3
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


def draw_panel(d, px, py, colour, title, tagline, item_count, in_stock, fonts):
    f_title, f_tag, f_count, f_stock = fonts

    # Panel background
    d.rectangle([px, py, px + PANEL_W, py + PANEL_H], fill=BG_PANEL)

    # Thick coloured left-edge bar
    d.rectangle([px, py, px + 5, py + PANEL_H], fill=colour)

    # Coloured top stripe
    STRIPE = 52
    d.rectangle([px, py, px + PANEL_W, py + STRIPE], fill=colour)

    # Darken the stripe slightly for text readability
    overlay = Image.new('RGBA', (PANEL_W, STRIPE), (0, 0, 0, 60))
    d._image.paste(overlay, (px, py), overlay)

    # Category title on stripe — large, bold, dark
    ty = py + (STRIPE - (f_title.size if hasattr(f_title, 'size') else 18)) // 2
    center_x(d, title, f_title, px, PANEL_W, ty, BG)

    # Tagline below stripe
    y = py + STRIPE + 14
    center_x(d, tagline, f_tag, px, PANEL_W, y, SUBTEXT)

    # Divider
    y += (f_tag.size if hasattr(f_tag, 'size') else 10) + 12
    d.line([px + 20, y, px + PANEL_W - 20, y], fill=(20, 35, 55), width=1)
    y += 10

    # Item count — large centred
    count_str = f'{item_count}'
    d.text(
        (px + (PANEL_W - tw(d, count_str, f_count)) // 2, y),
        count_str, font=f_count, fill=colour
    )
    y += (f_count.size if hasattr(f_count, 'size') else 36) + 4

    label_str = 'items available'
    center_x(d, label_str, f_tag, px, PANEL_W, y, DIM)

    # Stock strip at bottom
    stock_y = py + PANEL_H - 30
    d.rectangle([px, stock_y, px + PANEL_W, py + PANEL_H], fill=(14, 24, 38))
    stock_str = f'{in_stock} of {item_count} lines currently in stock'
    center_x(d, stock_str, f_stock, px, PANEL_W, stock_y + 8, GREEN)


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
    f_badge  = load_font('segoeuib.ttf', 12)   # "new additions" badge
    f_sub    = load_font('segoeui.ttf',  11)   # header subtitle + footer
    f_ptitle = load_font('segoeuib.ttf', 16)   # panel category title
    f_tag    = load_font('segoeui.ttf',  10)   # panel tagline / labels
    f_count  = load_font('segoeuib.ttf', 48)   # big item count number
    f_stock  = load_font('segoeuib.ttf',  9)   # stock strip text
    panel_fonts = (f_ptitle, f_tag, f_count, f_stock)

    # ── Canvas ─────────────────────────────────────────────────────────────────
    img = Image.new('RGB', (W, H), BG)
    d   = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    d.rectangle([0, 0, W, HDR_H], fill=BG2)

    # Tri-colour top stripe
    seg = W // 3
    d.rectangle([0,       0, seg,     5], fill=GAS_COL)
    d.rectangle([seg,     0, seg * 2, 5], fill=RES_COL)
    d.rectangle([seg * 2, 0, W,       5], fill=SAL_COL)

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
    sub = 'Three new market categories now open — visit the Materials & Resources Market tab'
    d.text(((W - tw(d, sub, f_sub)) // 2, 70), sub, font=f_sub, fill=SUBTEXT)

    # ── Panels ────────────────────────────────────────────────────────────────
    py = HDR_H + PAD
    px_gas = PAD
    px_res = PAD + PANEL_W + GAP
    px_sal = PAD + 2 * (PANEL_W + GAP)

    draw_panel(d, px_gas, py, GAS_COL,
               'GAS CLOUD MATERIALS',
               'Fullerenes  ·  Cytoserocin  ·  Mykoserocin',
               gas_total, gas_in, panel_fonts)

    draw_panel(d, px_res, py, RES_COL,
               'RESEARCH EQUIPMENT',
               'Datacores  ·  Decryptors',
               res_total, res_in, panel_fonts)

    draw_panel(d, px_sal, py, SAL_COL,
               'SALVAGED MATERIALS',
               'Common  ·  Uncommon  ·  Rare  ·  Very Rare  ·  Rogue Drone',
               sal_total, sal_in, panel_fonts)

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
