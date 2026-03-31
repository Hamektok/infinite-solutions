"""
generate_ore_mining_image.py

Creates a Discord-ready PNG showing nullsec anomaly ore ISK/m³ profitability.
Run any time to regenerate:  python generate_ore_mining_image.py
Output: ore_mining_image.png
"""
import sqlite3
import os
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
OUT_PATH    = os.path.join(PROJECT_DIR, 'ore_mining_image.png')
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
ORANGE   = (255, 160,  40)

# ── Ore definitions ───────────────────────────────────────────────────────────
CLASSIC_IDS = [62568, 62564, 62560, 62556, 62552, 62572, 62586]
NEWER_IDS   = [75275, 75279, 75283, 75287]
NEWEST_IDS  = [82300, 82304, 82308, 82312, 82316]

TIER_CLASSIC = 'classic'
TIER_NEWER   = 'newer'
TIER_NEWEST  = 'newest'

TIER_COLOR = {
    TIER_CLASSIC: ACCENT,
    TIER_NEWER:   GOLD,
    TIER_NEWEST:  GREEN,
}

TIER_LABEL = {
    TIER_CLASSIC: 'Classic Null',
    TIER_NEWER:   'New Null (Uprising)',
    TIER_NEWEST:  'Newest Null',
}

# ── Layout ────────────────────────────────────────────────────────────────────
W        = 480
PAD      = 16
ROW_H    = 22
TIER_BAR = 4   # left edge tier color bar width

# Column x positions (right edges, computed relative to W)
COL_ISKM3_W   = 88
COL_TREND_W   = 58
COL_PRIMARY_W = 130

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except Exception:
        return ImageFont.load_default()

def fmt_isk(n):
    """Format ISK value with full decimals and commas."""
    return f'{n:,.0f}'

def tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def truncate(draw, text, font, max_px):
    if tw(draw, text, font) <= max_px:
        return text
    while text and tw(draw, text + '…', font) > max_px:
        text = text[:-1]
    return text + '…'

# ── Fonts ─────────────────────────────────────────────────────────────────────
F_TITLE  = load_font('segoeuib.ttf', 22)
F_SUBTITLE = load_font('segoeui.ttf', 13)
F_HDR    = load_font('segoeuib.ttf', 11)
F_ITEM   = load_font('segoeui.ttf',  13)
F_ITEM_B = load_font('segoeuib.ttf', 13)
F_QTY    = load_font('segoeuib.ttf', 13)
F_SUB    = load_font('segoeui.ttf',  12)
F_TAG    = load_font('segoeuib.ttf', 10)
F_SEP    = load_font('segoeuib.ttf', 10)


def isk_color(isk_per_m3):
    if   isk_per_m3 >= 50_000: return GREEN
    elif isk_per_m3 >= 25_000: return GOLD
    elif isk_per_m3 >= 15_000: return ORANGE
    else:                       return GRAY


def main():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # ── Load refine efficiency ────────────────────────────────────────────────
    row = c.execute("SELECT value FROM site_config WHERE key='ore_param_refine_eff'").fetchone()
    refine_eff = float(row[0]) / 100.0 if row else 0.906

    # ── Load 7-day average mineral JBV prices (current window) ───────────────
    c.execute("""
        SELECT type_id, AVG(best_buy) as jbv
        FROM market_price_snapshots
        WHERE DATE(timestamp) >= DATE('now', '-7 days')
        GROUP BY type_id
    """)
    mineral_jbv = {r[0]: r[1] for r in c.fetchall()}

    # ── Load prior 7-day avg (days 8–14 ago) for trend ───────────────────────
    c.execute("""
        SELECT type_id, AVG(best_buy) as jbv
        FROM market_price_snapshots
        WHERE DATE(timestamp) >= DATE('now', '-14 days')
          AND DATE(timestamp) <  DATE('now', '-7 days')
        GROUP BY type_id
    """)
    mineral_jbv_prior = {r[0]: r[1] for r in c.fetchall()}

    # ── Load mineral names ────────────────────────────────────────────────────
    c.execute("SELECT type_id, type_name FROM inv_types")
    type_names = {r[0]: r[1] for r in c.fetchall()}

    # ── Load ore base data ────────────────────────────────────────────────────
    all_ore_ids = CLASSIC_IDS + NEWER_IDS + NEWEST_IDS
    placeholders = ','.join('?' * len(all_ore_ids))
    c.execute(
        f"SELECT type_id, type_name, volume, portion_size FROM inv_types WHERE type_id IN ({placeholders})",
        all_ore_ids
    )
    ore_base = {r[0]: {'name': r[1], 'volume': r[2], 'portion_size': r[3]} for r in c.fetchall()}

    # ── Load ore yields (type_materials) ────────────────────────────────────
    c.execute(
        f"SELECT type_id, materials_json FROM type_materials WHERE type_id IN ({placeholders})",
        all_ore_ids
    )
    ore_materials = {r[0]: json.loads(r[1]) for r in c.fetchall()}

    # ── Load ore own JBV ─────────────────────────────────────────────────────
    # Use mineral_jbv dict which covers everything from market_price_snapshots
    ore_jbv = {tid: mineral_jbv.get(tid) for tid in all_ore_ids}

    conn.close()

    # ── Calculate ISK/m³ for each ore ────────────────────────────────────────
    results = []  # list of dicts

    def ore_tier(type_id):
        if type_id in CLASSIC_IDS: return TIER_CLASSIC
        if type_id in NEWER_IDS:   return TIER_NEWER
        return TIER_NEWEST

    for tid in all_ore_ids:
        if tid not in ore_base:
            continue
        if tid not in ore_materials:
            continue
        base    = ore_base[tid]
        mats    = ore_materials[tid]
        volume  = base['volume']
        portion = base['portion_size']

        if volume <= 0 or portion <= 0:
            continue

        # Compute refine value and find primary mineral
        refine_value   = 0.0
        primary_mat_id = None
        primary_isk    = 0.0
        mat_contributions = {}

        for mat in mats:
            mat_id  = mat['materialTypeID']
            qty     = mat['quantity']
            jbv     = mineral_jbv.get(mat_id)
            if jbv is None:
                continue
            contrib = qty * refine_eff * jbv
            refine_value += contrib
            mat_contributions[mat_id] = contrib

        if refine_value <= 0:
            continue  # no price data

        # Find primary contributing mineral
        if mat_contributions:
            primary_mat_id = max(mat_contributions, key=mat_contributions.get)
            primary_isk    = mat_contributions[primary_mat_id]

        # ISK per m³ = refine_value / (volume_per_unit * portion_size)
        total_volume = volume * portion
        isk_per_m3   = refine_value / total_volume

        # Primary mineral name
        primary_name = type_names.get(primary_mat_id, '?') if primary_mat_id else '?'

        # 7-day trend: compare current ISK/m³ vs prior 7-day window
        prior_value = 0.0
        for mat in mats:
            mat_id = mat['materialTypeID']
            qty    = mat['quantity']
            pjbv   = mineral_jbv_prior.get(mat_id)
            if pjbv:
                prior_value += qty * refine_eff * pjbv
        if prior_value > 0:
            isk_per_m3_prior = prior_value / total_volume
            trend_pct = (isk_per_m3 - isk_per_m3_prior) / isk_per_m3_prior * 100
        else:
            trend_pct = None

        results.append({
            'type_id':    tid,
            'name':       base['name'],
            'tier':       ore_tier(tid),
            'isk_per_m3': isk_per_m3,
            'trend_pct':  trend_pct,
            'primary_name': primary_name,
        })

    if not results:
        print('No ore data available — check market_price_snapshots and type_materials.')
        return

    # Sort by ISK/m³ descending
    results.sort(key=lambda x: x['isk_per_m3'], reverse=True)

    # ── Layout constants ──────────────────────────────────────────────────────
    HDR_H     = 82
    COL_HDR_H = 18
    FOOTER_H  = 40
    GAP       = 8
    DESC_PAD  = 8   # vertical padding inside description band

    DESC_LINES = [
        f'Your earnings per m³ mined, based on refining at {refine_eff * 100:.2f}%',
        'efficiency and selling minerals at Jita buy orders.',
        'Higher = more ISK per unit of laser time.',
    ]
    DESC_LINE_H = 15
    DESC_H = DESC_PAD * 2 + len(DESC_LINES) * DESC_LINE_H

    n_data_rows = len(results)
    total_h = (HDR_H
               + DESC_H
               + GAP
               + COL_HDR_H
               + n_data_rows * ROW_H
               + GAP
               + FOOTER_H)

    # ── Render ────────────────────────────────────────────────────────────────
    img  = Image.new('RGB', (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle([(0, 0), (W, HDR_H)], fill=BG_HDR)
    draw.line([(0, HDR_H), (W, HDR_H)], fill=ACCENT, width=2)

    draw.text((PAD, 14), 'Null Sec Ore Mining — ISK/m³ Profitability',
              font=F_TITLE, fill=WHITE)
    draw.text((PAD, 44),
              f'Based on 7-day avg Jita buy prices · Refine eff {refine_eff * 100:.2f}%',
              font=F_SUBTITLE, fill=SUBTEXT)
    today_str = datetime.now().strftime('%d %b %Y')
    draw.text((PAD, 64), f'Updated {today_str}', font=F_SUBTITLE, fill=SUBTEXT)

    # ── Description band ──────────────────────────────────────────────────────
    desc_y = HDR_H
    draw.rectangle([(0, desc_y), (W, desc_y + DESC_H)], fill=(8, 18, 28))
    draw.line([(0, desc_y + DESC_H), (W, desc_y + DESC_H)], fill=DIM, width=1)
    ty = desc_y + DESC_PAD
    for line in DESC_LINES:
        draw.text((PAD, ty), line, font=F_SUB, fill=SUBTEXT)
        ty += DESC_LINE_H

    # ── Column layout (right-anchored) ────────────────────────────────────────
    content_right  = W - PAD
    primary_right  = content_right
    trend_right    = primary_right - COL_PRIMARY_W - 10
    iskm3_right    = trend_right   - COL_TREND_W   - 10
    name_left      = PAD + TIER_BAR + 6
    name_right     = iskm3_right   - COL_ISKM3_W  - 10

    # ── Column header row ─────────────────────────────────────────────────────
    y = HDR_H + DESC_H + GAP
    draw.rectangle([(0, y), (W, y + COL_HDR_H - 1)], fill=BG_HDR)
    draw.text((name_left,     y + 3), 'ORE NAME',        font=F_HDR, fill=SUBTEXT)
    draw.text((iskm3_right,   y + 3), 'ISK/M³',          font=F_HDR, fill=SUBTEXT, anchor='ra')
    draw.text((trend_right,   y + 3), '7D',              font=F_HDR, fill=SUBTEXT, anchor='ra')
    draw.text((primary_right, y + 3), 'PRIMARY MINERAL', font=F_HDR, fill=SUBTEXT, anchor='ra')
    y += COL_HDR_H

    # ── Data rows ─────────────────────────────────────────────────────────────
    for row_idx, dr in enumerate(results):
        row_bg = BG_ROW_B if row_idx % 2 == 1 else BG_ROW_A
        draw.rectangle([(0, y), (W, y + ROW_H - 1)], fill=row_bg)

        # Left bar color driven by ISK/m³ tier
        draw.rectangle([(0, y), (TIER_BAR - 1, y + ROW_H - 1)], fill=isk_color(dr['isk_per_m3']))

        # Ore name (strip "Compressed " prefix)
        display_name = dr['name'].replace('Compressed ', '')
        name_max_w = name_right - name_left - 4
        draw.text((name_left, y + 4),
                  truncate(draw, display_name, F_ITEM_B, name_max_w),
                  font=F_ITEM_B, fill=WHITE)

        # ISK/m³ — full number, color-coded
        draw.text((iskm3_right, y + 4), fmt_isk(dr['isk_per_m3']),
                  font=F_QTY, fill=isk_color(dr['isk_per_m3']), anchor='ra')

        # 7-day trend
        t = dr['trend_pct']
        if t is None:
            draw.text((trend_right, y + 4), '—', font=F_ITEM, fill=GRAY, anchor='ra')
        elif t >= 0:
            draw.text((trend_right, y + 4), f'▲ {t:.1f}%', font=F_ITEM, fill=GREEN, anchor='ra')
        else:
            draw.text((trend_right, y + 4), f'▼ {abs(t):.1f}%', font=F_ITEM, fill=RED, anchor='ra')

        # Primary mineral name
        draw.text((primary_right, y + 4), dr['primary_name'],
                  font=F_ITEM, fill=SUBTEXT, anchor='ra')

        y += ROW_H

    y += GAP

    # ── ISK/m³ color legend ───────────────────────────────────────────────────
    draw.line([(0, y), (W, y)], fill=DIM, width=1)
    y += 8
    sw = 10
    lx = PAD
    ly = y + 2
    for color, label in [(GREEN, '≥ 50,000'), (GOLD, '≥ 25,000'), (ORANGE, '≥ 15,000'), (GRAY, '< 15,000')]:
        draw.rectangle([(lx, ly), (lx + sw, ly + sw)], fill=color)
        lx += sw + 5
        draw.text((lx, ly - 1), label, font=F_SUB, fill=SUBTEXT)
        lx += tw(draw, label, F_SUB) + 20
    y += 22

    # ── Footer ────────────────────────────────────────────────────────────────
    draw.line([(0, y), (W, y)], fill=DIM, width=1)
    footer_note = 'Infinite Solutions  ·  Hamektok Hakaari  ·  LX-ZOJ  ·  #mining-ops'
    nw = tw(draw, footer_note, F_SUB)
    draw.text(((W - nw) // 2, y + 12), footer_note, font=F_SUB, fill=SUBTEXT)

    img.save(OUT_PATH, optimize=True)
    print(f'Saved:    {OUT_PATH}')
    print(f'Size:     {W} x {total_h} px')
    print(f'Ores:     {n_data_rows} displayed')
    print(f'Refine:   {refine_eff * 100:.2f}%')


if __name__ == '__main__':
    main()
