"""
generate_slots_image.py

Creates a Discord-ready PNG showing market slot availability at LX-ZOJ.

Which items appear and their status is controlled by slots_config.json.
Only items listed in that file show up in the image.

Usage:
    python generate_slots_image.py           -- generate slots_image.png
    python generate_slots_image.py --init    -- create/reset slots_config.json
                                               with every tracked item listed
                                               (all marked open, none as lessee)
                                               Edit that file to configure slots.

slots_config.json format:
    [
      {"type_id": 2393, "category": "pi_materials",   "name": "Bacteria",  "status": "open",   "lessee": null},
      {"type_id": 2396, "category": "pi_materials",   "name": "Biofuels",  "status": "closed", "lessee": "Character Name"},
      ...
    ]

    status : "open"   -- slot is available for lease
             "closed" -- slot is taken; lessee name is shown on the image
    Remove an entry entirely to hide that item from the image.
"""
import json
import math
import sqlite3
import os
import sys
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(PROJECT_DIR, 'mydatabase.db')
OUT_PATH     = os.path.join(PROJECT_DIR, 'slots_image.png')
CONFIG_PATH  = os.path.join(PROJECT_DIR, 'slots_config.json')
FONT_DIR     = r'C:\Windows\Fonts'

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
SEC_H   = 28
SUB_H   = 22

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


# ── Drawing helpers ───────────────────────────────────────────────────────────
PRICE_COL = ( 80, 180, 220)   # cyan-ish for price


def _fmt_price(raw):
    """Format a stored price value for display on the image."""
    if not raw:
        return ''
    try:
        v = float(str(raw).replace(',', ''))
        if v >= 1e9: return f'{v/1e9:.2f}B/mo'
        if v >= 1e6: return f'{v/1e6:.1f}M/mo'
        if v >= 1e3: return f'{v/1e3:.0f}K/mo'
        return f'{int(v):,}/mo'
    except Exception:
        return str(raw)


def draw_slot_row(draw, x, y, col_w, name, status, lessee, price, row_i):
    row_bg = BG_ROW_B if row_i % 2 else BG_ROW_A
    draw.rectangle([(x, y), (x + col_w, y + ROW_H - 1)], fill=row_bg)

    closed   = status == 'closed'
    bar_col  = CLOSE_BAR if closed else OPEN_BAR
    draw.rectangle([(x, y), (x + BAR_W, y + ROW_H - 1)], fill=bar_col)

    if closed and lessee:
        tag     = lessee
        tag_col = AMBER
    elif closed:
        tag     = 'CLOSED'
        tag_col = AMBER
    else:
        tag     = 'OPEN'
        tag_col = GREEN

    # Right side: price (rightmost), then status/lessee tag to its left
    price_str = _fmt_price(price)
    pw        = tw(draw, price_str, F_STATUS) if price_str else 0
    sw        = tw(draw, tag, F_STATUS)
    gap       = 10 if price_str else 0

    # price at far right, tag to the left of it
    price_x   = x + col_w - pw - 4
    tag_x     = price_x - sw - gap

    name_budget = tag_x - (x + BAR_W + 6) - 6
    disp = name
    if tw(draw, disp, F_ITEM) > name_budget:
        while disp and tw(draw, disp + '\u2026', F_ITEM) > name_budget:
            disp = disp[:-1]
        disp += '\u2026'

    draw.text((x + BAR_W + 6, y + 6), disp,      font=F_ITEM,   fill=WHITE)
    draw.text((tag_x,          y + 6), tag,       font=F_STATUS, fill=tag_col)
    if price_str:
        draw.text((price_x,    y + 6), price_str, font=F_STATUS, fill=PRICE_COL)


def draw_sec_header(draw, x, y, w, label, count, hidden):
    draw.text((x, y + 2), label, font=F_HDR, fill=ACCENT)
    if hidden:
        tag = '  [hidden on site]'
        draw.text((x + tw(draw, label, F_HDR) + 4, y + 3),
                  tag, font=F_SMALL, fill=GRAY)
    cs = f'{count} slots'
    draw.text((x + w - tw(draw, cs, F_SMALL), y + 3),
              cs, font=F_SMALL, fill=SUBTEXT)
    line_y = y + SEC_H - 4
    draw.line([(x, line_y), (x + w, line_y)], fill=DIM, width=1)
    return y + SEC_H


def draw_sub_header(draw, x, y, col_w, label):
    draw.text((x + BAR_W + 6, y + 3), label, font=F_SUB, fill=SEC_COL)
    draw.line([(x, y + SUB_H - 2), (x + col_w, y + SUB_H - 2)], fill=DIM, width=1)
    return y + SUB_H


def draw_column(draw, x, y_start, col_w, items, row_offset=0):
    """items = list of (name, status, lessee, price)"""
    y = y_start
    for i, (name, status, lessee, price) in enumerate(items):
        draw_slot_row(draw, x, y, col_w, name, status, lessee, price, row_offset + i)
        y += ROW_H
    return y


# ── Config helpers ────────────────────────────────────────────────────────────
PI_TIER_MAP = {1334: 'P1', 1335: 'P2', 1336: 'P3', 1337: 'P4'}

def get_pi_tier(grp_id):
    return PI_TIER_MAP.get(grp_id, 'P2')

def get_salvage_grade(disp_ord):
    if disp_ord is None: return 'Other'
    if disp_ord <= 9:    return 'Common'
    if disp_ord <= 21:   return 'Uncommon'
    if disp_ord <= 32:   return 'Rare'
    if disp_ord <= 42:   return 'Very Rare'
    return 'Rogue Drone'


def build_template_from_db():
    """Return a list of slot dicts for every tracked market item (all open)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('''
        SELECT tmi.type_id, tmi.category, it.type_name,
               tmi.display_order, it.market_group_id
        FROM tracked_market_items tmi
        JOIN inv_types it ON tmi.type_id = it.type_id
        WHERE tmi.category NOT IN ("standard_ore","ice_ore","moon_ore")
        ORDER BY tmi.category, tmi.display_order
    ''').fetchall()
    conn.close()

    entries = []
    for type_id, cat, name, disp, grp in rows:
        entries.append({
            'type_id':  type_id,
            'category': cat,
            'name':     name,
            'status':   'open',
            'lessee':   None,
        })
    return entries


def load_config():
    """Load slots_config.json.  Aborts with a helpful message if missing."""
    if not os.path.exists(CONFIG_PATH):
        print('slots_config.json not found.')
        print('Run:  python generate_slots_image.py --init')
        print('to create it, then edit it to select which items are slots.')
        sys.exit(1)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


# ── Sub-category classifiers ──────────────────────────────────────────────────
CAT_ORDER = ['minerals', 'ice_products', 'moon_materials',
             'pi_materials', 'salvaged_materials']

CAT_LABELS = {
    'minerals':          'MINERALS',
    'ice_products':      'ICE PRODUCTS',
    'moon_materials':    'MOON MATERIALS',
    'pi_materials':      'PLANETARY MATERIALS',
    'salvaged_materials':'SALVAGED MATERIALS',
}

# How many columns each category uses
CAT_COLS = {
    'minerals':           2,
    'ice_products':       2,
    'moon_materials':     3,
    'pi_materials':       4,
    'salvaged_materials': 5,
}


def sub_key(cat, entry):
    """Return the sub-section key for an entry (tier / grade / None)."""
    if cat == 'pi_materials':
        # look up market_group from DB on demand — we stored it as-is from template
        # type_id is available; use the name-based fallback via cached map
        return None   # handled separately via _pi_tier field
    if cat == 'salvaged_materials':
        return None   # handled via _sal_grade field
    return None


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if '--init' in sys.argv:
        entries = build_template_from_db()
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        print(f'Created {CONFIG_PATH}  ({len(entries)} items)')
        print('Edit this file to choose which items are slots and set their status.')
        print('Then run:  python generate_slots_image.py')
        return

    config = load_config()

    # Pull extra metadata from DB for tier/grade classification
    conn = sqlite3.connect(DB_PATH)
    meta = {}   # type_id -> (display_order, market_group_id)
    for type_id, disp, grp in conn.execute(
        'SELECT tmi.type_id, tmi.display_order, it.market_group_id '
        'FROM tracked_market_items tmi JOIN inv_types it ON tmi.type_id = it.type_id'
    ).fetchall():
        meta[type_id] = (disp, grp)

    vis_cfg = dict(conn.execute(
        "SELECT key, value FROM site_config WHERE key LIKE 'market_tab_%'"
    ).fetchall())

    snap_ts = (conn.execute(
        'SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory'
    ).fetchone()[0] or '')
    conn.close()

    def tab_hidden(cat):
        return vis_cfg.get(f'market_tab_{cat}', '0') != '1'

    try:
        ts_str = datetime.fromisoformat(snap_ts).strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = datetime.now().strftime('%d %b %Y  %H:%M')

    # Organise config entries into category buckets with sub-group keys
    by_cat = {c: {} for c in CAT_ORDER}   # cat -> {sub_key: [(name, status, lessee, price)]}

    PI_TIERS   = ['P1', 'P2', 'P3', 'P4']
    SAL_GRADES = ['Common', 'Uncommon', 'Rare', 'Very Rare', 'Rogue Drone']

    for entry in config:
        cat     = entry.get('category', '')
        if cat not in by_cat:
            continue
        tid     = entry.get('type_id')
        name    = entry.get('name', f'Item {tid}')
        status  = entry.get('status', 'open')
        lessee  = entry.get('lessee') or None
        price   = entry.get('price')  or None

        disp, grp = meta.get(tid, (None, None))

        if cat == 'pi_materials':
            sub = get_pi_tier(grp)
        elif cat == 'salvaged_materials':
            sub = get_salvage_grade(disp)
        else:
            sub = '__all__'

        by_cat[cat].setdefault(sub, []).append((name, status, lessee, price))

    # ── Compute dimensions ─────────────────────────────────────────────────
    CONTENT_W = W - PAD * 2
    HDR_H     = 84
    FOOTER_H  = 48
    GAP       = 18

    def col_width(n_cols):
        return (CONTENT_W - COL_GAP * (n_cols - 1)) // n_cols

    # Active categories (have at least one slot configured)
    active_cats = [c for c in CAT_ORDER if any(by_cat[c].values())]

    # Per-category section height
    def sec_height(cat):
        n_cols = CAT_COLS[cat]
        if cat in ('pi_materials', 'salvaged_materials'):
            # One column per sub-group
            sub_order = PI_TIERS if cat == 'pi_materials' else SAL_GRADES
            col_h = [SUB_H + len(by_cat[cat].get(s, [])) * ROW_H for s in sub_order]
            return SEC_H + (max(col_h) if col_h else 0)
        elif cat in ('minerals', 'ice_products'):
            # Both share one row — handled together
            return 0   # special case
        else:
            items = by_cat[cat].get('__all__', [])
            rows  = math.ceil(len(items) / n_cols) if items else 0
            return SEC_H + rows * ROW_H

    # Minerals + Ice share a single horizontal band
    mins_items = by_cat['minerals'].get('__all__', [])
    ice_items  = by_cat['ice_products'].get('__all__', [])
    band1_h = SEC_H + max(len(mins_items), len(ice_items), 0) * ROW_H if (mins_items or ice_items) else 0

    section_heights = {}
    for cat in active_cats:
        if cat in ('minerals', 'ice_products'):
            section_heights[cat] = band1_h
        else:
            section_heights[cat] = sec_height(cat)

    # Deduplicate band (minerals + ice drawn together once)
    band_drawn = False
    body_h = 0
    drawn_cats = []
    for cat in active_cats:
        if cat in ('minerals', 'ice_products'):
            if not band_drawn:
                body_h += band1_h + GAP
                band_drawn = True
                drawn_cats.append('minerals+ice')
        else:
            body_h += section_heights[cat] + GAP
            drawn_cats.append(cat)

    total_h = HDR_H + PAD + body_h + FOOTER_H

    # ── Render ─────────────────────────────────────────────────────────────
    img  = Image.new('RGB', (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([(0, 0), (W, HDR_H)], fill=BG_HDR)
    draw.line([(0, HDR_H), (W, HDR_H)], fill=ACCENT, width=2)
    draw.text((PAD, 14), 'LX-ZOJ  \u00b7  MARKET SLOT AVAILABILITY', font=F_TITLE, fill=WHITE)
    draw.text((PAD, 56), f'Updated  {ts_str}', font=F_TS, fill=SUBTEXT)

    # Legend
    lx = W - PAD
    ly = 56
    for label, col in [('Open', GREEN), ('Closed / Leased', AMBER)]:
        lw = tw(draw, label, F_SMALL)
        lx -= lw
        draw.text((lx, ly), label, font=F_SMALL, fill=col)
        lx -= BAR_W + 6
        draw.rectangle([(lx, ly + 2), (lx + BAR_W, ly + 14)], fill=col)
        lx -= 20

    y = HDR_H + PAD

    col2_w = col_width(2)
    col3_w = col_width(3)
    col4_w = col_width(4)
    col5_w = col_width(5)
    x_l    = PAD
    x_r    = PAD + col2_w + COL_GAP

    for block in drawn_cats:
        # ── Minerals + Ice ─────────────────────────────────────────────────
        if block == 'minerals+ice':
            has_mins = bool(mins_items)
            has_ice  = bool(ice_items)

            if has_mins:
                draw_sec_header(draw, x_l, y, col2_w,
                                'MINERALS', len(mins_items),
                                tab_hidden('minerals'))
            if has_ice:
                draw_sec_header(draw, x_r, y, col2_w,
                                'ICE PRODUCTS', len(ice_items),
                                tab_hidden('ice_products'))
            y += SEC_H

            draw_column(draw, x_l, y, col2_w, mins_items)
            draw_column(draw, x_r, y, col2_w, ice_items)
            y += max(len(mins_items), len(ice_items)) * ROW_H + GAP

        # ── Moon Materials ──────────────────────────────────────────────────
        elif block == 'moon_materials':
            items  = by_cat['moon_materials'].get('__all__', [])
            n_cols = 3
            moon_n = math.ceil(len(items) / n_cols) if items else 1
            draw_sec_header(draw, x_l, y, CONTENT_W,
                            'MOON MATERIALS', len(items),
                            tab_hidden('moon_materials'))
            y += SEC_H
            for col_i in range(n_cols):
                chunk = items[col_i * moon_n : (col_i + 1) * moon_n]
                cx    = PAD + col_i * (col3_w + COL_GAP)
                draw_column(draw, cx, y, col3_w, chunk,
                            row_offset=col_i * moon_n)
            y += moon_n * ROW_H + GAP

        # ── Planetary Materials ─────────────────────────────────────────────
        elif block == 'pi_materials':
            pi_total = sum(len(v) for v in by_cat['pi_materials'].values())
            draw_sec_header(draw, x_l, y, CONTENT_W,
                            'PLANETARY MATERIALS', pi_total,
                            tab_hidden('pi_materials'))
            y += SEC_H
            col_heights = []
            for col_i, tier in enumerate(PI_TIERS):
                items = by_cat['pi_materials'].get(tier, [])
                cx    = PAD + col_i * (col4_w + COL_GAP)
                ty    = draw_sub_header(draw, cx, y, col4_w, tier)
                draw_column(draw, cx, ty, col4_w, items)
                col_heights.append(SUB_H + len(items) * ROW_H)
            y += max(col_heights, default=0) + GAP

        # ── Salvaged Materials ──────────────────────────────────────────────
        elif block == 'salvaged_materials':
            sal_total = sum(len(v) for v in by_cat['salvaged_materials'].values())
            draw_sec_header(draw, x_l, y, CONTENT_W,
                            'SALVAGED MATERIALS', sal_total,
                            tab_hidden('salvaged_materials'))
            y += SEC_H
            col_heights = []
            for col_i, grade in enumerate(SAL_GRADES):
                items = by_cat['salvaged_materials'].get(grade, [])
                cx    = PAD + col_i * (col5_w + COL_GAP)
                gy    = draw_sub_header(draw, cx, y, col5_w, grade)
                draw_column(draw, cx, gy, col5_w, items)
                col_heights.append(SUB_H + len(items) * ROW_H)
            y += max(col_heights, default=0) + GAP

    # Footer
    footer_y = total_h - FOOTER_H
    draw.line([(0, footer_y), (W, footer_y)], fill=DIM, width=1)
    total_slots  = len(config)
    open_slots   = sum(1 for e in config if e.get('status', 'open') == 'open')
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
