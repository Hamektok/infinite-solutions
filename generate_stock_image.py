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

def truncate(draw, text, font, max_px):
    if tw(draw, text, font) <= max_px:
        return text
    while text and tw(draw, text + '…', font) > max_px:
        text = text[:-1]
    return text + '…'

# ── Fonts ────────────────────────────────────────────────────────────────────
F_TITLE = load_font('segoeuib.ttf', 24)
F_HDR   = load_font('segoeuib.ttf', 13)
F_ITEM  = load_font('segoeui.ttf',  13)
F_QTY   = load_font('segoeuib.ttf', 13)
F_SUB   = load_font('segoeui.ttf',  12)
F_TAG   = load_font('segoeuib.ttf', 10)


def draw_item_row(draw, x, y, col_w, name, qty, buyback, row_bg,
                  price_pct=None, alliance_disc=0):
    """Draw a single item row."""
    in_stock   = qty > 0
    GAP        = 14
    pct_col_w  = tw(draw, '100%',   F_QTY)
    qty_col_w  = tw(draw, '999.9M', F_QTY)

    draw.rectangle([(x, y), (x + col_w, y + ROW_H - 1)], fill=row_bg)

    # Buyback indicator — gold vertical bar on left edge
    if buyback:
        draw.rectangle([(x, y), (x + BB_BAR, y + ROW_H - 1)], fill=GOLD)

    # Right-to-left column anchors
    right      = x + col_w
    corp_right = right
    ally_right = corp_right - pct_col_w - GAP
    qty_right  = ally_right - pct_col_w - GAP

    # Qty / OUT
    qty_str   = fmt_qty(qty) if in_stock else 'OUT'
    qty_color = GREEN        if in_stock else RED
    draw.text((qty_right, y + 4), qty_str, font=F_QTY, fill=qty_color, anchor='ra')

    # Price columns
    if price_pct is not None:
        draw.text((ally_right, y + 4), f'{price_pct:.0f}%',
                  font=F_QTY, fill=ACCENT, anchor='ra')
        draw.text((corp_right, y + 4), f'{price_pct - alliance_disc:.0f}%',
                  font=F_QTY, fill=GOLD,   anchor='ra')

    # Name — truncated to fit remaining space
    name_color = WHITE if in_stock else GRAY
    name_x     = x + BB_BAR + 5
    name_w     = qty_right - qty_col_w - GAP - name_x
    draw.text((name_x, y + 4), truncate(draw, name, F_ITEM, name_w),
              font=F_ITEM, fill=name_color)


def draw_section(draw, label, items, x, y, col_w):
    """Draw a labelled section. items = [(name, qty, buyback, price_pct, alliance_disc), ...]"""
    draw.text((x, y), label, font=F_HDR, fill=ACCENT)
    line_y = y + 18
    draw.line([(x, line_y), (x + col_w, line_y)], fill=DIM, width=1)
    y = line_y + 5

    for i, (name, qty, buyback, price_pct, alliance_disc) in enumerate(items):
        row_bg = BG_ROW_B if i % 2 == 1 else BG_ROW_A
        draw_item_row(draw, x, y, col_w, name, qty, buyback, row_bg,
                      price_pct, alliance_disc)
        y += ROW_H

    return y


def main():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # Load visibility flags from site_config
    vis_rows = c.execute(
        "SELECT key, value FROM site_config WHERE key LIKE 'market_tab_%' OR key LIKE 'market_sub_%'"
    ).fetchall()
    vis = {k: (str(v) == '1') for k, v in vis_rows}
    show_minerals      = vis.get('market_tab_minerals',                                  True)
    show_ice           = vis.get('market_tab_ice_products',                              True)
    show_moon          = vis.get('market_tab_moon_materials',                            True)
    show_gas           = vis.get('market_tab_gas_cloud_materials',                       True)
    show_ice_fuel      = vis.get('market_sub_ice_products_fuel_blocks',                  True)
    show_ice_refined   = vis.get('market_sub_ice_products_refined_ice',                  True)
    show_ice_isotopes  = vis.get('market_sub_ice_products_isotopes',                     True)
    show_moon_raw      = vis.get('market_sub_moon_materials_raw',                        True)
    show_moon_proc     = vis.get('market_sub_moon_materials_processed',                  True)
    show_moon_adv      = vis.get('market_sub_moon_materials_advanced',                   True)
    show_gas_cf        = vis.get('market_sub_gas_cloud_materials_compressed_fullerene',  True)
    show_gas_cb        = vis.get('market_sub_gas_cloud_materials_compressed_booster',    True)
    show_gas_uf        = vis.get('market_sub_gas_cloud_materials_uncompressed_fullerene',True)
    show_gas_ub        = vis.get('market_sub_gas_cloud_materials_uncompressed_booster',  True)
    show_research      = vis.get('market_tab_research_equipment',                        True)
    show_res_dc        = vis.get('market_sub_research_equipment_datacores',              True)
    show_res_dec       = vis.get('market_sub_research_equipment_decryptors',             True)
    show_salvage       = vis.get('market_tab_salvaged_materials',                        True)

    # Fetch items only for visible categories
    visible_cats = [c_name for c_name, flag in [
        ('minerals',            show_minerals),
        ('ice_products',        show_ice),
        ('moon_materials',      show_moon),
        ('gas_cloud_materials', show_gas),
        ('research_equipment',  show_research),
        ('salvaged_materials',  show_salvage),
    ] if flag]

    if not visible_cats:
        print('No visible categories — nothing to render.')
        conn.close()
        return

    placeholders = ','.join('?' * len(visible_cats))
    c.execute(f'''
        SELECT tm.category, t.type_name, i.quantity, tm.buyback_accepted,
               tm.display_order, tm.price_percentage,
               COALESCE(tm.alliance_discount, 0)
        FROM lx_zoj_current_inventory i
        JOIN tracked_market_items tm ON i.type_id = tm.type_id
        JOIN inv_types t             ON i.type_id = t.type_id
        WHERE tm.category IN ({placeholders})
        ORDER BY tm.category, tm.display_order
    ''', visible_cats)
    rows = c.fetchall()

    c.execute('SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory')
    snap_ts = c.fetchone()[0] or ''
    conn.close()

    def ice_sub_visible(display_order):
        if display_order <= 8:   return show_ice_fuel
        if display_order <= 11:  return show_ice_refined
        return show_ice_isotopes

    def moon_sub_visible(display_order):
        if display_order < 100:  return show_moon_raw
        if display_order < 200:  return show_moon_proc
        return show_moon_adv

    def gas_sub_visible(display_order):
        if display_order < 100:  return show_gas_cf
        if display_order < 200:  return show_gas_cb
        if display_order < 300:  return show_gas_uf
        return show_gas_ub

    def research_sub_visible(display_order):
        if display_order < 100:  return show_res_dc
        return show_res_dec

    by_cat = {}
    for cat, name, qty, buyback, disp_ord, price_pct, alliance_disc in rows:
        if cat == 'ice_products'        and not ice_sub_visible(disp_ord):
            continue
        if cat == 'moon_materials'      and not moon_sub_visible(disp_ord):
            continue
        if cat == 'gas_cloud_materials' and not gas_sub_visible(disp_ord):
            continue
        if cat == 'research_equipment'  and not research_sub_visible(disp_ord):
            continue
        by_cat.setdefault(cat, []).append((name, qty, buyback, price_pct, alliance_disc))

    minerals       = by_cat.get('minerals',            []) if show_minerals else []
    ice            = by_cat.get('ice_products',        []) if show_ice      else []
    moon_mats      = by_cat.get('moon_materials',      []) if show_moon     else []
    gas_mats       = by_cat.get('gas_cloud_materials', []) if show_gas      else []
    research_items = by_cat.get('research_equipment',  []) if show_research else []
    salvage_items  = by_cat.get('salvaged_materials',  []) if show_salvage  else []

    try:
        dt     = datetime.fromisoformat(snap_ts)
        ts_str = dt.strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = snap_ts

    # ── Calculate heights ─────────────────────────────────────────────────
    HDR_H   = 72
    SEC_HDR = 24
    FOOTER  = 46
    GAP     = 16

    col_w     = (W - PAD * 2 - COL_GAP) // 2
    full_w    = W - PAD * 2
    half_moon     = (len(moon_mats)      + 1) // 2
    half_gas      = (len(gas_mats)       + 1) // 2
    half_research = (len(research_items) + 1) // 2
    half_salvage  = (len(salvage_items)  + 1) // 2

    # Top pair: minerals and/or ice
    show_top = show_minerals or show_ice
    if show_minerals and show_ice:
        top_rows = max(len(minerals), len(ice))
    elif show_minerals:
        top_rows = len(minerals)
    elif show_ice:
        top_rows = len(ice)
    else:
        top_rows = 0

    total_h = HDR_H + PAD
    if show_top:
        total_h += SEC_HDR + top_rows * ROW_H + GAP
    if show_moon:
        total_h += SEC_HDR + half_moon * ROW_H + GAP
    if show_gas and gas_mats:
        total_h += SEC_HDR + half_gas * ROW_H + GAP
    if show_research and research_items:
        total_h += SEC_HDR + half_research * ROW_H + GAP
    if show_salvage and salvage_items:
        total_h += SEC_HDR + half_salvage * ROW_H + GAP
    total_h += FOOTER

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

    # Top section: minerals and/or ice
    if show_minerals and show_ice:
        # Side by side
        y_after_l = draw_section(draw, 'MINERALS',     minerals, x_l, y, col_w)
        y_after_r = draw_section(draw, 'ICE PRODUCTS', ice,      x_r, y, col_w)
        y = max(y_after_l, y_after_r) + GAP
    elif show_minerals:
        y = draw_section(draw, 'MINERALS', minerals, x_l, y, full_w) + GAP
    elif show_ice:
        y = draw_section(draw, 'ICE PRODUCTS', ice, x_l, y, full_w) + GAP

    # Moon materials — full-width, two columns
    if show_moon:
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
                name, qty, buyback, price_pct, alliance_disc = left_moon[i]
                draw_item_row(draw, x_l, yr, col_w, name, qty, buyback, row_bg,
                              price_pct, alliance_disc)
            if i < len(right_moon):
                name, qty, buyback, price_pct, alliance_disc = right_moon[i]
                draw_item_row(draw, x_r, yr, col_w, name, qty, buyback, row_bg,
                              price_pct, alliance_disc)
            yr += ROW_H
        y = yr + GAP

    # Gas cloud materials — full-width, two columns
    if show_gas and gas_mats:
        draw.text((x_l, y), 'GAS CLOUD MATERIALS', font=F_HDR, fill=ACCENT)
        line_y = y + 18
        draw.line([(x_l, line_y), (x_l + full_w, line_y)], fill=DIM, width=1)
        yr = line_y + 5

        left_gas  = gas_mats[:half_gas]
        right_gas = gas_mats[half_gas:]

        for i in range(half_gas):
            row_bg = BG_ROW_B if i % 2 == 1 else BG_ROW_A
            draw.rectangle([(x_l, yr), (x_l + full_w, yr + ROW_H - 1)], fill=row_bg)
            if i < len(left_gas):
                name, qty, buyback, price_pct, alliance_disc = left_gas[i]
                draw_item_row(draw, x_l, yr, col_w, name, qty, buyback, row_bg,
                              price_pct, alliance_disc)
            if i < len(right_gas):
                name, qty, buyback, price_pct, alliance_disc = right_gas[i]
                draw_item_row(draw, x_r, yr, col_w, name, qty, buyback, row_bg,
                              price_pct, alliance_disc)
            yr += ROW_H
        y = yr + GAP

    # Research equipment — full-width, two columns
    if show_research and research_items:
        draw.text((x_l, y), 'RESEARCH EQUIPMENT', font=F_HDR, fill=ACCENT)
        line_y = y + 18
        draw.line([(x_l, line_y), (x_l + full_w, line_y)], fill=DIM, width=1)
        yr = line_y + 5

        left_res  = research_items[:half_research]
        right_res = research_items[half_research:]

        for i in range(half_research):
            row_bg = BG_ROW_B if i % 2 == 1 else BG_ROW_A
            draw.rectangle([(x_l, yr), (x_l + full_w, yr + ROW_H - 1)], fill=row_bg)
            if i < len(left_res):
                name, qty, buyback, price_pct, alliance_disc = left_res[i]
                draw_item_row(draw, x_l, yr, col_w, name, qty, buyback, row_bg,
                              price_pct, alliance_disc)
            if i < len(right_res):
                name, qty, buyback, price_pct, alliance_disc = right_res[i]
                draw_item_row(draw, x_r, yr, col_w, name, qty, buyback, row_bg,
                              price_pct, alliance_disc)
            yr += ROW_H
        y = yr + GAP

    # Salvaged materials — full-width, two columns
    if show_salvage and salvage_items:
        draw.text((x_l, y), 'SALVAGED MATERIALS', font=F_HDR, fill=ACCENT)
        line_y = y + 18
        draw.line([(x_l, line_y), (x_l + full_w, line_y)], fill=DIM, width=1)
        yr = line_y + 5

        left_salv  = salvage_items[:half_salvage]
        right_salv = salvage_items[half_salvage:]

        for i in range(half_salvage):
            row_bg = BG_ROW_B if i % 2 == 1 else BG_ROW_A
            draw.rectangle([(x_l, yr), (x_l + full_w, yr + ROW_H - 1)], fill=row_bg)
            if i < len(left_salv):
                name, qty, buyback, price_pct, alliance_disc = left_salv[i]
                draw_item_row(draw, x_l, yr, col_w, name, qty, buyback, row_bg,
                              price_pct, alliance_disc)
            if i < len(right_salv):
                name, qty, buyback, price_pct, alliance_disc = right_salv[i]
                draw_item_row(draw, x_r, yr, col_w, name, qty, buyback, row_bg,
                              price_pct, alliance_disc)
            yr += ROW_H
        y = yr + GAP

    # Footer with legend
    footer_y = total_h - FOOTER
    draw.line([(0, footer_y), (W, footer_y)], fill=DIM, width=1)

    lx = PAD
    ly = footer_y + 10
    draw.rectangle([(lx, ly + 1), (lx + BB_BAR, ly + 13)], fill=GOLD)
    draw.text((lx + BB_BAR + 5, ly), 'Buyback accepted', font=F_SUB, fill=SUBTEXT)

    dot_x = lx + BB_BAR + 5 + tw(draw, 'Buyback accepted', F_SUB) + 20
    out_w = tw(draw, 'OUT', F_TAG)
    draw.rectangle([(dot_x, ly + 1), (dot_x + out_w + 6, ly + 13)], fill=(40, 15, 15))
    draw.text((dot_x + 3, ly), 'OUT', font=F_TAG, fill=RED)
    draw.text((dot_x + out_w + 10, ly), '= Out of stock', font=F_SUB, fill=SUBTEXT)

    # Price legend (right side of footer)
    sw, gap = 8, 4
    rx = W - PAD
    draw.text((rx, ly), '% of Jita Buy', font=F_SUB, fill=DIM, anchor='ra')
    rx -= tw(draw, '% of Jita Buy', F_SUB) + 16
    corp_lbl = 'Corp'
    draw.text((rx, ly), corp_lbl, font=F_SUB, fill=GOLD, anchor='ra')
    rx -= tw(draw, corp_lbl, F_SUB) + gap
    draw.rectangle([rx - sw, ly + 2, rx, ly + 2 + sw], fill=GOLD)
    rx -= sw + 12
    ally_lbl = 'Alliance'
    draw.text((rx, ly), ally_lbl, font=F_SUB, fill=ACCENT, anchor='ra')
    rx -= tw(draw, ally_lbl, F_SUB) + gap
    draw.rectangle([rx - sw, ly + 2, rx, ly + 2 + sw], fill=ACCENT)

    note = '@ or DM Hamektok Hakaari on Discord to purchase  ·  corp members only'
    nw   = tw(draw, note, F_SUB)
    draw.text(((W - nw) // 2, footer_y + 28), note, font=F_SUB, fill=SUBTEXT)

    img.save(OUT_PATH, optimize=True)
    print(f'Saved:  {OUT_PATH}')
    print(f'Size      {W} x {total_h} px')
    shown = ', '.join(c.title().replace('_', ' ') for c in visible_cats)
    print(f'Shown:    {shown}')


if __name__ == '__main__':
    main()
