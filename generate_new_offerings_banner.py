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
BG        = (  8,  14,  24)
BG2       = ( 12,  20,  34)
BG_PANEL  = ( 11,  19,  31)
BG_STRIPE = ( 16,  26,  42)
WHITE     = (220, 238, 255)
DIM       = ( 70, 100, 128)
SUBTEXT   = ( 90, 138, 170)
ACCENT    = (  0, 175, 255)
GOLD      = (255, 200,  50)
GREEN     = ( 50, 210, 120)

GAS_COL   = (  0, 220, 140)
RES_COL   = (180, 120, 255)
SAL_COL   = (255, 140,  60)

# ── Layout ────────────────────────────────────────────────────────────────────
W        = 940
PAD      = 22
GAP      = 14     # gap between panels
HDR_H    = 90
FOOTER_H = 46
PANEL_W  = (W - 2 * PAD - 2 * GAP) // 3
PANEL_Y  = HDR_H + PAD
STRIPE_H = 30     # coloured top stripe of each panel
H        = HDR_H + PAD + 330 + PAD + FOOTER_H   # = 90+22+330+22+46 = 510

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_font(name, size):
    try:    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except: return ImageFont.load_default()

def tw(d, text, font):
    bb = d.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def center_text(d, text, font, x, panel_w, y, fill):
    d.text((x + (panel_w - tw(d, text, font)) // 2, y), text, font=font, fill=fill)

def bullet(d, text, font, x, y, dot_col, text_col, max_w):
    """Draw a bullet row, return next y."""
    DOT_R = 3
    dy = (font.size if hasattr(font, 'size') else 11) // 2
    d.ellipse([x + 4, y + dy - DOT_R, x + 4 + DOT_R * 2, y + dy + DOT_R], fill=dot_col)
    # Truncate if needed
    txt = text
    while txt and tw(d, txt, font) > max_w - 16:
        txt = txt[:-1]
    if txt != text:
        txt = txt[:-1] + '…'
    d.text((x + 14, y), txt, font=font, fill=text_col)
    return y + font.size + 5 if hasattr(font, 'size') else y + 16

def draw_panel(d, px, colour, title, tagline, bullets, stock_str, fonts):
    """Draw a single category panel."""
    f_cat, f_tag, f_bul, f_stock = fonts

    panel_h = H - PANEL_Y - PAD - FOOTER_H

    # Panel background
    d.rectangle([px, PANEL_Y, px + PANEL_W, PANEL_Y + panel_h], fill=BG_PANEL)

    # Coloured top stripe
    d.rectangle([px, PANEL_Y, px + PANEL_W, PANEL_Y + STRIPE_H], fill=colour)

    # Category title centred on stripe
    ty = PANEL_Y + (STRIPE_H - (f_cat.size if hasattr(f_cat,'size') else 14)) // 2
    center_text(d, title, f_cat, px, PANEL_W, ty, BG)

    y = PANEL_Y + STRIPE_H + 10

    # Tagline
    center_text(d, tagline, f_tag, px, PANEL_W, y, SUBTEXT)
    y += (f_tag.size if hasattr(f_tag,'size') else 10) + 12

    # Thin divider
    d.line([px + 10, y, px + PANEL_W - 10, y], fill=BG_STRIPE, width=1)
    y += 8

    # Bullet list
    bul_max_w = PANEL_W - 24
    for bul_text, bul_col in bullets:
        y = bullet(d, bul_text, f_bul, px + 10, y, bul_col, WHITE, bul_max_w)

    # Stock strip at bottom of panel
    stock_y = PANEL_Y + panel_h - 28
    d.rectangle([px, stock_y, px + PANEL_W, PANEL_Y + panel_h], fill=BG_STRIPE)
    center_text(d, stock_str, f_stock, px, PANEL_W, stock_y + 7, GREEN)


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Stock counts per category
    def get_stock(cat):
        c.execute('''
            SELECT COUNT(*), SUM(CASE WHEN i.quantity > 0 THEN 1 ELSE 0 END)
            FROM tracked_market_items t
            JOIN lx_zoj_current_inventory i ON t.type_id = i.type_id
            WHERE t.category = ?
        ''', (cat,))
        total, stocked = c.fetchone()
        return stocked or 0, total or 0

    gas_in, gas_total   = get_stock('gas_cloud_materials')
    res_in, res_total   = get_stock('research_equipment')
    sal_in, sal_total   = get_stock('salvaged_materials')

    snap_ts = c.execute('SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory').fetchone()[0] or ''
    conn.close()

    try:
        ts_str = datetime.fromisoformat(snap_ts).strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = datetime.now(timezone.utc).strftime('%d %b %Y  %H:%M UTC')

    # ── Fonts ─────────────────────────────────────────────────────────────────
    f_title  = load_font('segoeuib.ttf', 22)
    f_sub    = load_font('segoeui.ttf',  11)
    f_new    = load_font('segoeuib.ttf', 13)   # "NEW" badge
    f_cat    = load_font('segoeuib.ttf', 13)   # panel category title
    f_tag    = load_font('segoeui.ttf',  10)   # tagline
    f_bul    = load_font('segoeui.ttf',  11)   # bullet items
    f_stock  = load_font('segoeuib.ttf', 10)   # stock strip
    panel_fonts = (f_cat, f_tag, f_bul, f_stock)

    # ── Canvas ─────────────────────────────────────────────────────────────────
    img = Image.new('RGB', (W, H), BG)
    d   = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    d.rectangle([0, 0, W, HDR_H], fill=BG2)
    # Top accent line — three-colour gradient using three rectangles
    seg = W // 3
    d.rectangle([0,       0, seg,     4], fill=GAS_COL)
    d.rectangle([seg,     0, seg * 2, 4], fill=RES_COL)
    d.rectangle([seg * 2, 0, W,       4], fill=SAL_COL)

    # "NEW ADDITIONS" badge
    badge_text = '★  NEW ADDITIONS'
    badge_w    = tw(d, badge_text, f_new) + 18
    badge_x    = (W - badge_w) // 2
    d.rectangle([badge_x, 10, badge_x + badge_w, 28], fill=(20, 60, 30))
    d.rectangle([badge_x, 10, badge_x + badge_w, 28],
                outline=(50, 210, 120), width=1)
    d.text((badge_x + 9, 12), badge_text, font=f_new, fill=GREEN)

    # Main title
    title = 'LX-ZOJ  ·  INFINITE SOLUTIONS'
    d.text(((W - tw(d, title, f_title)) // 2, 34), title, font=f_title, fill=WHITE)

    # Subtitle
    sub = 'Three new market categories now available in the Materials & Resources Market'
    d.text(((W - tw(d, sub, f_sub)) // 2, 64), sub, font=f_sub, fill=SUBTEXT)

    # ── Panels ────────────────────────────────────────────────────────────────
    px_gas = PAD
    px_res = PAD + PANEL_W + GAP
    px_sal = PAD + 2 * (PANEL_W + GAP)

    gas_bullets = [
        ('Fullerites  C28 · C32 · C50 · C60', GAS_COL),
        ('Fullerites  C70 · C72 · C84 · C320 · C540', GAS_COL),
        ('Cytoserocin Gas  — 8 variants', (150, 230, 200)),
        ('Mykoserocin Gas  — 8 variants', (150, 230, 200)),
        ('Compressed variants available', DIM),
    ]
    draw_panel(d, px_gas, GAS_COL,
               'GAS CLOUD MATERIALS',
               'Fullerenes & Booster Gas',
               gas_bullets,
               f'{gas_in} of {gas_total} lines in stock',
               panel_fonts)

    res_bullets = [
        ('Datacores  — 23 types', RES_COL),
        ('  Amarrian · Caldari · Gallentean', (200, 180, 255)),
        ('  Minmatar · Triglavian · Upwell', (200, 180, 255)),
        ('  Subsystem · Physics · Engineering', (200, 180, 255)),
        ('Decryptors  — 8 types', RES_COL),
        ('  Accelerant · Attainment · Parity', (200, 180, 255)),
        ('  Process · Symmetry · Augmentation', (200, 180, 255)),
    ]
    draw_panel(d, px_res, RES_COL,
               'RESEARCH EQUIPMENT',
               'Datacores & Decryptors',
               res_bullets,
               f'{res_in} of {res_total} lines in stock',
               panel_fonts)

    sal_bullets = [
        ('Common  — 8 items', SAL_COL),
        ('Uncommon  — 11 items', SAL_COL),
        ('Rare  — 10 items', SAL_COL),
        ('Very Rare  — 9 items', SAL_COL),
        ('Rogue Drone  — 8 items', SAL_COL),
        ('Full stock across all tiers', DIM),
    ]
    draw_panel(d, px_sal, SAL_COL,
               'SALVAGED MATERIALS',
               'All tiers · Common to Rogue Drone',
               sal_bullets,
               f'{sal_in} of {sal_total} lines in stock',
               panel_fonts)

    # ── Footer ────────────────────────────────────────────────────────────────
    fy = H - FOOTER_H
    d.line([0, fy, W, fy], fill=(18, 30, 46), width=1)

    contact = '@ or DM  Hamektok Hakaari  on Discord to purchase  ·  corp members only'
    d.text(((W - tw(d, contact, f_sub)) // 2, fy + 8), contact, font=f_sub, fill=SUBTEXT)

    updated = f'Stock as of  {ts_str}'
    d.text(((W - tw(d, updated, f_sub)) // 2, fy + 24), updated, font=f_sub, fill=DIM)

    img.save(OUT_PATH, optimize=True)
    print(f'Saved: {OUT_PATH}  ({W}×{H}px)')


if __name__ == '__main__':
    main()
