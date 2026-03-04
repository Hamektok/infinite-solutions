"""
generate_slots_image.py

Creates a Discord-ready PNG listing every market slot at LX-ZOJ with its
current OPEN / CLOSED status.  Covers all categories (hidden tabs included).

Run any time to regenerate:  python generate_slots_image.py
Output: slots_image.png
"""
import math
import sqlite3
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
OUT_PATH    = os.path.join(PROJECT_DIR, 'slots_image.png')
FONT_DIR    = r'C:\Windows\Fonts'

# ── Palette ───────────────────────────────────────────────────────────────────
BG        = ( 10,  21,  32)
BG_HDR    = (  6,  14,  24)
BG_ROW_A  = ( 10,  21,  32)
BG_ROW_B  = ( 13,  26,  42)
ACCENT    = (  0, 170, 255)
SEC_COL   = (  0, 210, 230)
WHITE     = (232, 244, 255)
SUBTEXT   = ( 90, 138, 170)
GREEN     = ( 68, 221, 136)
AMBER     = (255, 185,  40)
GRAY      = ( 90, 110, 130)
DIM       = ( 40,  68,  90)
OPEN_BAR  = (  0, 160,  80)
CLOSE_BAR = (200, 140,   0)
BAR_W     = 4

# ── Layout ────────────────────────────────────────────────────────────────────
W       = 1400
PAD     = 24
ROW_H   = 24
COL_GAP = 16
SEC_H   = 28    # section header + divider
SUB_H   = 22   # tier / grade sub-header + divider

# ── Fonts ─────────────────────────────────────────────────────────────────────
def load_font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except Exception:
        return ImageFont.load_default()

F_TITLE  = load_font('segoeuib.ttf', 26)
F_HDR    = load_font('segoeuib.ttf', 13)
F_SUB    = load_font('segoeuib.ttf', 11)
F_ITEM   = load_font('segoeui.ttf',  12)
F_STATUS = load_font('segoeuib.ttf', 11)
F_SMALL  = load_font('segoeui.ttf',  11)
F_TS     = load_font('segoeui.ttf',  12)


def tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


# ── Row drawing ───────────────────────────────────────────────────────────────
def draw_slot_row(draw, x, y, col_w, name, consignor, row_i):
    """Draw one slot row.  consignor=None means the slot is OPEN."""
    row_bg = BG_ROW_B if row_i % 2 else BG_ROW_A
    draw.rectangle([(x, y), (x + col_w, y + ROW_H - 1)], fill=row_bg)

    bar_color = CLOSE_BAR if consignor else OPEN_BAR
    draw.rectangle([(x, y), (x + BAR_W, y + ROW_H - 1)], fill=bar_color)

    name_x = x + BAR_W + 6

    # Status label: consignor name or "OPEN"
    if consignor:
        status_str = consignor
        status_col = AMBER
    else:
        status_str = 'OPEN'
        status_col = GREEN

    # Reserve space for status tag then truncate item name if needed
    sw          = tw(draw, status_str, F_STATUS)
    name_budget = col_w - BAR_W - 6 - sw - 10
    disp_name   = name
    if tw(draw, disp_name, F_ITEM) > name_budget:
        while disp_name and tw(draw, disp_name + '\u2026', F_ITEM) > name_budget:
            disp_name = disp_name[:-1]
        disp_name += '\u2026'

    draw.text((name_x,              y + 6), disp_name,  font=F_ITEM,   fill=WHITE)
    draw.text((x + col_w - sw - 4,  y + 6), status_str, font=F_STATUS, fill=status_col)


# ── Section / sub-section headers ────────────────────────────────────────────
def draw_sec_header(draw, x, y, w, label, count, hidden):
    """Full-width section header.  Returns y of first content row."""
    draw.text((x, y + 2), label, font=F_HDR, fill=ACCENT)
    tag = '  [hidden on site]' if hidden else ''
    tag_w = tw(draw, tag, F_SMALL)
    if tag:
        draw.text((x + tw(draw, label, F_HDR) + 4, y + 3), tag,
                  font=F_SMALL, fill=GRAY)
    count_str = f'{count} slots'
    draw.text((x + w - tw(draw, count_str, F_SMALL), y + 3),
              count_str, font=F_SMALL, fill=SUBTEXT)
    line_y = y + SEC_H - 4
    draw.line([(x, line_y), (x + w, line_y)], fill=DIM, width=1)
    return y + SEC_H


def draw_sub_header(draw, x, y, col_w, label):
    """Tier / grade sub-header within a column.  Returns y of first item row."""
    draw.text((x + BAR_W + 6, y + 3), label, font=F_SUB, fill=SEC_COL)
    line_y = y + SUB_H - 2
    draw.line([(x, line_y), (x + col_w, line_y)], fill=DIM, width=1)
    return y + SUB_H


def draw_column(draw, x, y_start, col_w, items, row_offset=0):
    """Draw a list of (name, consignor) tuples as a single column."""
    y = y_start
    for i, (name, consignor) in enumerate(items):
        draw_slot_row(draw, x, y, col_w, name, consignor, row_offset + i)
        y += ROW_H
    return y


# ── Data helpers ─────────────────────────────────────────────────────────────
PI_TIER_MAP = {1334: 'P1', 1335: 'P2', 1336: 'P3', 1337: 'P4'}

def get_pi_tier(grp_id):
    return PI_TIER_MAP.get(grp_id, 'P2')   # Data Sheets (grp 20) treated as P2

def get_salvage_grade(disp_ord):
    if disp_ord is None:  return 'Other'
    if disp_ord <= 9:     return 'Common'
    if disp_ord <= 21:    return 'Uncommon'
    if disp_ord <= 32:    return 'Rare'
    if disp_ord <= 42:    return 'Very Rare'
    return 'Rogue Drone'


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # All slots with active consignor if one exists
    c.execute('''
        SELECT tmi.category, it.type_name, tmi.display_order,
               it.market_group_id, con.character_name
        FROM tracked_market_items tmi
        JOIN inv_types it ON tmi.type_id = it.type_id
        LEFT JOIN consignors con ON (
            (con.item_type_id = tmi.type_id
             OR (con.item_type_id IS NULL
                 AND LOWER(con.item_name) = LOWER(it.type_name)))
            AND con.active = 1
        )
        WHERE tmi.category NOT IN ("standard_ore","ice_ore","moon_ore")
        ORDER BY tmi.category, tmi.display_order
    ''')
    all_rows = c.fetchall()

    # Market tab visibility from site_config
    vis_cfg = dict(c.execute(
        "SELECT key, value FROM site_config WHERE key LIKE 'market_tab_%'"
    ).fetchall())
    def tab_hidden(cat):
        val = vis_cfg.get(f'market_tab_{cat}')
        if val is None:
            return True   # no entry → hidden by default
        return val != '1'

    c.execute('SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory')
    snap_ts = (c.fetchone()[0] or '')
    conn.close()

    try:
        ts_str = datetime.fromisoformat(snap_ts).strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = datetime.now().strftime('%d %b %Y  %H:%M')

    # Bucket items by category
    by_cat = {}
    for cat, name, disp, grp, consignor in all_rows:
        by_cat.setdefault(cat, []).append((name, disp, grp, consignor))

    def slots(cat):
        return [(n, cs) for n, d, g, cs in by_cat.get(cat, [])]

    minerals = slots('minerals')
    ice      = slots('ice_products')
    moon     = slots('moon_materials')

    pi_by_tier = {}
    for n, d, g, cs in by_cat.get('pi_materials', []):
        pi_by_tier.setdefault(get_pi_tier(g), []).append((n, cs))

    sal_by_grade = {}
    for n, d, g, cs in by_cat.get('salvaged_materials', []):
        sal_by_grade.setdefault(get_salvage_grade(d), []).append((n, cs))

    PI_TIERS  = ['P1', 'P2', 'P3', 'P4']
    SAL_GRADES = ['Common', 'Uncommon', 'Rare', 'Very Rare', 'Rogue Drone']

    # ── Dimension calculations ─────────────────────────────────────────────
    CONTENT_W = W - PAD * 2
    HDR_H     = 84
    FOOTER_H  = 48
    GAP       = 18

    col2_w = (CONTENT_W - COL_GAP) // 2
    col3_w = (CONTENT_W - COL_GAP * 2) // 3
    col4_w = (CONTENT_W - COL_GAP * 3) // 4
    col5_w = (CONTENT_W - COL_GAP * 4) // 5

    # Section 1: Minerals + Ice (two independent side-by-side sections)
    sec1_rows = max(len(minerals), len(ice), 1)
    sec1_h    = SEC_H + sec1_rows * ROW_H

    # Section 2: Moon Materials — 3 columns
    moon_n    = math.ceil(len(moon) / 3) if moon else 1
    sec2_h    = SEC_H + moon_n * ROW_H

    # Section 3: PI — 4 columns (one per tier)
    pi_col_h  = [SUB_H + len(pi_by_tier.get(t, [])) * ROW_H for t in PI_TIERS]
    sec3_h    = SEC_H + max(pi_col_h) if pi_col_h else SEC_H

    # Section 4: Salvaged — 5 columns (one per grade)
    sal_col_h = [SUB_H + len(sal_by_grade.get(g, [])) * ROW_H for g in SAL_GRADES]
    sec4_h    = SEC_H + max(sal_col_h) if sal_col_h else SEC_H

    total_h = (HDR_H + PAD
               + sec1_h + GAP
               + sec2_h + GAP
               + sec3_h + GAP
               + sec4_h + GAP
               + FOOTER_H)

    # ── Render ────────────────────────────────────────────────────────────
    img  = Image.new('RGB', (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([(0, 0), (W, HDR_H)], fill=BG_HDR)
    draw.line([(0, HDR_H), (W, HDR_H)], fill=ACCENT, width=2)
    draw.text((PAD, 14), 'LX-ZOJ  \u00b7  MARKET SLOT AVAILABILITY', font=F_TITLE, fill=WHITE)
    draw.text((PAD, 56), f'Updated  {ts_str}', font=F_TS, fill=SUBTEXT)

    # Legend (header, right side)
    lx = W - PAD
    ly = 56
    for label, col in [('Open', GREEN), ('Closed / Leased', AMBER)]:
        lw = tw(draw, label, F_SMALL)
        lx -= lw
        draw.text((lx, ly), label, font=F_SMALL, fill=col)
        lx -= BAR_W + 6
        draw.rectangle([(lx, ly + 2), (lx + BAR_W, ly + 14)], fill=col)
        lx -= 20

    y   = HDR_H + PAD
    x_l = PAD
    x_r = PAD + col2_w + COL_GAP

    # ── Sec 1: Minerals + Ice ──────────────────────────────────────────────
    draw_sec_header(draw, x_l, y, col2_w,
                    'MINERALS', len(minerals), tab_hidden('minerals'))
    draw_sec_header(draw, x_r, y, col2_w,
                    'ICE PRODUCTS', len(ice), tab_hidden('ice_products'))
    y += SEC_H
    draw_column(draw, x_l, y, col2_w, minerals)
    draw_column(draw, x_r, y, col2_w, ice)
    y += sec1_rows * ROW_H + GAP

    # ── Sec 2: Moon Materials ──────────────────────────────────────────────
    draw_sec_header(draw, x_l, y, CONTENT_W,
                    'MOON MATERIALS', len(moon), tab_hidden('moon_materials'))
    y += SEC_H
    for col_i in range(3):
        chunk = moon[col_i * moon_n : (col_i + 1) * moon_n]
        cx    = PAD + col_i * (col3_w + COL_GAP)
        draw_column(draw, cx, y, col3_w, chunk, row_offset=col_i * moon_n)
    y += moon_n * ROW_H + GAP

    # ── Sec 3: Planetary Materials ─────────────────────────────────────────
    pi_total = sum(len(v) for v in pi_by_tier.values())
    draw_sec_header(draw, x_l, y, CONTENT_W,
                    'PLANETARY MATERIALS', pi_total, tab_hidden('pi_materials'))
    y += SEC_H
    for col_i, tier in enumerate(PI_TIERS):
        cx    = PAD + col_i * (col4_w + COL_GAP)
        items = pi_by_tier.get(tier, [])
        ty    = draw_sub_header(draw, cx, y, col4_w, tier)
        draw_column(draw, cx, ty, col4_w, items)
    y += max(pi_col_h) + GAP

    # ── Sec 4: Salvaged Materials ──────────────────────────────────────────
    sal_total = sum(len(v) for v in sal_by_grade.values())
    draw_sec_header(draw, x_l, y, CONTENT_W,
                    'SALVAGED MATERIALS', sal_total, tab_hidden('salvaged_materials'))
    y += SEC_H
    for col_i, grade in enumerate(SAL_GRADES):
        cx    = PAD + col_i * (col5_w + COL_GAP)
        items = sal_by_grade.get(grade, [])
        gy    = draw_sub_header(draw, cx, y, col5_w, grade)
        draw_column(draw, cx, gy, col5_w, items)
    y += max(sal_col_h) + GAP

    # ── Footer ─────────────────────────────────────────────────────────────
    footer_y = total_h - FOOTER_H
    draw.line([(0, footer_y), (W, footer_y)], fill=DIM, width=1)
    total_slots  = len(all_rows)
    open_slots   = sum(1 for *_, cs in all_rows if cs is None)
    closed_slots = total_slots - open_slots
    summary = (f'{total_slots} total slots  \u00b7  '
               f'{open_slots} open  \u00b7  '
               f'{closed_slots} leased')
    sw = tw(draw, summary, F_SMALL)
    draw.text(((W - sw) // 2, footer_y + 10), summary, font=F_SMALL, fill=SUBTEXT)
    note = '@ or DM Hamektok Hakaari on Discord to lease a slot'
    nw   = tw(draw, note, F_SMALL)
    draw.text(((W - nw) // 2, footer_y + 28), note, font=F_SMALL, fill=SUBTEXT)

    img.save(OUT_PATH, optimize=True)
    print(f'Saved:  {OUT_PATH}')
    print(f'Size:   {W} x {total_h} px')
    print(f'Slots:  {total_slots} total  |  {open_slots} open  |  {closed_slots} leased')


if __name__ == '__main__':
    main()
