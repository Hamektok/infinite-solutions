"""
generate_anniversary_image.py

One-month anniversary graphic for Infinite Solutions at LX-ZOJ.
Output: anniversary_image.png
"""
import os
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH    = os.path.join(PROJECT_DIR, 'anniversary_image.png')
FONT_DIR    = r'C:\Windows\Fonts'

# ── Palette ───────────────────────────────────────────────────────────────────
BG          = ( 10,  21,  32)
BG_CARD     = ( 13,  28,  46)
BG_CARD_ALT = ( 10,  22,  38)
ACCENT      = (  0, 170, 255)
ACCENT_DIM  = (  0,  80, 130)
WHITE       = (232, 244, 255)
SUBTEXT     = ( 90, 138, 170)
GREEN       = ( 68, 221, 136)
GOLD        = (255, 200,  50)
GOLD_DIM    = (120,  90,  10)
DIM         = ( 30,  55,  80)
BORDER      = ( 20,  55,  90)

# ── Layout ────────────────────────────────────────────────────────────────────
W    = 900
PAD  = 32

# ── Fonts ─────────────────────────────────────────────────────────────────────
def load_font(name, size):
    for fname in ([name] if isinstance(name, str) else name):
        try:
            return ImageFont.truetype(os.path.join(FONT_DIR, fname), size)
        except Exception:
            pass
    return ImageFont.load_default()

F_HERO_LABEL = load_font('segoeuib.ttf',  13)
F_HERO_VAL   = load_font('segoeuib.ttf',  44)
F_HERO_UNIT  = load_font('segoeuib.ttf',  18)
F_TITLE      = load_font('segoeuib.ttf',  28)
F_SUBTITLE   = load_font('segoeui.ttf',   15)
F_SECTION    = load_font('segoeuib.ttf',  12)
F_ITEM_NAME  = load_font('segoeui.ttf',   13)
F_ITEM_VAL   = load_font('segoeuib.ttf',  13)
F_FOOTER     = load_font('segoeui.ttf',   11)

# ── Helpers ───────────────────────────────────────────────────────────────────
def tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]

def fmt_isk(n):
    if n >= 1_000_000_000: return f'{n / 1_000_000_000:.2f}B'
    if n >= 1_000_000:     return f'{n / 1_000_000:.1f}M'
    return f'{n:,.0f}'

def fmt_qty(n):
    if n >= 1_000_000_000: return f'{n / 1_000_000_000:.2f}B'
    if n >= 1_000_000:     return f'{n / 1_000_000:.1f}M'
    if n >= 1_000:         return f'{n / 1_000:.1f}K'
    return f'{n:,}'

def rounded_rect(draw, xy, radius, fill, outline=None, outline_w=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                            outline=outline, width=outline_w)

# ── Data ──────────────────────────────────────────────────────────────────────
CONTRACT_ISK   = 21_473_786_722
CONTRACTS      = 80
PAID_CONTRACTS = 45
INV_ISK        = 18_448_896_663
DISTINCT_ITEMS = 31  # non-ore distinct items in paid Rax contracts

TOP_ITEMS = [
    ('Pyerite',            356_387_780,  6_187_548_365),
    ('Tritanium',          857_154_018,  3_313_464_197),
    ('Helium Isotopes',      1_315_824,  1_036_286_898),
    ('Mexallon',            14_142_209,    979_649_426),
    ('Nitrogen Isotopes',    1_298_573,    882_855_078),
    ('Strontium Clathrates',   253_658,    878_912_495),
    ('Zydrine',                875_076,    791_358_062),
    ('Megacyte',               268_816,    656_091_430),
    ('Oxygen Isotopes',        840_624,    618_464_992),
    ('Nocxium',                722_136,    490_679_060),
]

# ── Build image ───────────────────────────────────────────────────────────────
# First pass: measure height
HEADER_H      = 120
HERO_H        = 110
DIVIDER_H     = 18
SECTION_HDR_H = 28
TABLE_ROW_H   = 26
TABLE_ROWS    = len(TOP_ITEMS)
FOOTER_H      = 40

H = (PAD
     + HEADER_H
     + PAD
     + HERO_H
     + DIVIDER_H
     + SECTION_HDR_H + 8
     + TABLE_ROWS * TABLE_ROW_H
     + PAD
     + FOOTER_H
     + PAD)

img  = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

y = 0

# ── Header band ───────────────────────────────────────────────────────────────
draw.rectangle([(0, 0), (W, HEADER_H)], fill=(6, 14, 24))

# Gold accent line top
draw.rectangle([(0, 0), (W, 3)], fill=GOLD)

# Accent bar left side
draw.rectangle([(0, 0), (5, HEADER_H)], fill=ACCENT)

# Corp name
corp_text = 'INFINITE SOLUTIONS'
cx = PAD + 18
cy_corp = 22
draw.text((cx, cy_corp), corp_text, font=F_TITLE, fill=WHITE)

# Tagline
tag_text = 'LX-ZOJ  ·  Established YC127  ·  Geminate'
draw.text((cx, cy_corp + 38), tag_text, font=F_SUBTITLE, fill=SUBTEXT)

# Anniversary badge — right side
badge_text  = '1 MONTH'
badge_text2 = 'ANNIVERSARY'
bw = 160
bh = 70
bx = W - PAD - bw
by = (HEADER_H - bh) // 2
rounded_rect(draw, (bx, by, bx+bw, by+bh), radius=6,
             fill=(30, 55, 10), outline=GOLD, outline_w=2)
draw.text((bx + bw//2 - tw(draw, badge_text, F_HERO_UNIT)//2,  by + 10),
          badge_text, font=F_HERO_UNIT, fill=GOLD)
draw.text((bx + bw//2 - tw(draw, badge_text2, F_HERO_LABEL)//2, by + 38),
          badge_text2, font=F_HERO_LABEL, fill=GOLD)
draw.text((bx + bw//2 - tw(draw, 'Feb 5 \u2013 Mar 5, 2026', F_FOOTER)//2, by + 54),
          'Feb 5 \u2013 Mar 5, 2026', font=F_FOOTER, fill=(160, 130, 40))

y = HEADER_H + PAD

# ── Hero stats row ────────────────────────────────────────────────────────────
STATS = [
    ('CONTRACTS COMPLETED', str(CONTRACTS),         ''),
    ('CONTRACT VALUE',       fmt_isk(CONTRACT_ISK),  'ISK'),
    ('INVENTORY MOVED',      fmt_isk(INV_ISK),       'ISK'),
    ('ITEMS TRADED',         str(DISTINCT_ITEMS),    'types'),
]

card_w = (W - 2*PAD - 3*12) // 4
cx = PAD
for label, value, unit in STATS:
    rounded_rect(draw, (cx, y, cx+card_w, y+HERO_H), radius=6,
                 fill=BG_CARD, outline=BORDER, outline_w=1)
    # Label
    lx = cx + (card_w - tw(draw, label, F_HERO_LABEL)) // 2
    draw.text((lx, y + 10), label, font=F_HERO_LABEL, fill=SUBTEXT)
    # Value
    vx = cx + (card_w - tw(draw, value, F_HERO_VAL)) // 2
    vy = y + 28
    draw.text((vx, vy), value, font=F_HERO_VAL, fill=GREEN)
    # Unit
    if unit:
        ux = cx + (card_w - tw(draw, unit, F_HERO_UNIT)) // 2
        draw.text((ux, vy + 48), unit, font=F_HERO_UNIT, fill=ACCENT)
    cx += card_w + 12

y += HERO_H + DIVIDER_H

# Divider
draw.rectangle([(PAD, y - 8), (W - PAD, y - 7)], fill=DIM)

# ── Top items table ───────────────────────────────────────────────────────────
section_label = 'TOP ITEMS BY VALUE  (paid contracts · Rax Hakaari · excluding ore)'
draw.text((PAD, y), section_label, font=F_SECTION, fill=SUBTEXT)
y += SECTION_HDR_H

col_rank  = PAD
col_name  = PAD + 30
col_qty   = W - PAD - 220
col_isk   = W - PAD - 100

# Column headers
draw.text((col_name, y - 2),  'ITEM',      font=F_SECTION, fill=SUBTEXT)
draw.text((col_qty - tw(draw, 'QTY', F_SECTION), y - 2),   'QTY',   font=F_SECTION, fill=SUBTEXT)
draw.text((col_isk - tw(draw, 'ISK VALUE', F_SECTION) + 90, y - 2), 'ISK VALUE', font=F_SECTION, fill=SUBTEXT)
y += 14

max_isk = TOP_ITEMS[0][2]
for i, (name, qty, isk) in enumerate(TOP_ITEMS):
    row_bg = BG_CARD if i % 2 == 0 else BG_CARD_ALT
    draw.rectangle([(PAD, y), (W - PAD, y + TABLE_ROW_H - 1)], fill=row_bg)

    # Rank
    rank_str = f'{i+1}'
    draw.text((col_rank + (22 - tw(draw, rank_str, F_ITEM_VAL))//2, y + 5),
              rank_str, font=F_ITEM_VAL, fill=GOLD if i == 0 else SUBTEXT)

    # ISK bar (subtle background bar)
    bar_max_w = col_qty - col_name - 10
    bar_w = int(bar_max_w * isk / max_isk)
    draw.rectangle([(col_name, y + TABLE_ROW_H - 3),
                    (col_name + bar_w, y + TABLE_ROW_H - 2)], fill=ACCENT_DIM)

    # Name
    draw.text((col_name, y + 5), name, font=F_ITEM_NAME, fill=WHITE)

    # Qty
    qty_str = fmt_qty(qty)
    draw.text((col_qty - tw(draw, qty_str, F_ITEM_VAL), y + 5),
              qty_str, font=F_ITEM_VAL, fill=SUBTEXT)

    # ISK
    isk_str = fmt_isk(isk)
    draw.text((W - PAD - tw(draw, isk_str, F_ITEM_VAL), y + 5),
              isk_str, font=F_ITEM_VAL, fill=GREEN)

    y += TABLE_ROW_H

y += PAD

# ── Footer ────────────────────────────────────────────────────────────────────
draw.rectangle([(0, y), (W, y + FOOTER_H + PAD)], fill=(6, 14, 24))
draw.rectangle([(0, y), (W, y + 1)], fill=ACCENT_DIM)

footer_text = 'Thank you to everyone who has used Infinite Solutions this past month.  \u2014 Hamektok Hakaari'
fx = (W - tw(draw, footer_text, F_FOOTER)) // 2
draw.text((fx, y + 12), footer_text, font=F_FOOTER, fill=SUBTEXT)

# Bottom gold line
draw.rectangle([(0, H - 3), (W, H)], fill=GOLD)

img.save(OUT_PATH)
print(f'Saved to {OUT_PATH}')
