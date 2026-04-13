"""
Build ore_price_table.html + PNG images (one per category) showing the true
price miners receive from Take The Bait buyback vs the advertised 92% JBV.

Columns: Ore | 92% JBV (Advertised) | True % of JBV
All values: refine value at 90.63% efficiency × Jita buy price.
Stack sizes: 100 units for standard & moon ore, 1 unit for ice.
PNG output: ore_price_std.png, ore_price_moon.png, ore_price_ice.png
"""
import json, sqlite3, os, math
from datetime import datetime, timezone

REFINING_EFF     = 0.9063
TTB_RATE         = 0.92
HAUL_FEE_PER_M3  = 125.0
STACK_SIZES      = {'standard_ore': 100, 'moon_ore': 100, 'ice_ore': 1}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mydatabase.db')
SDE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sde')

# ── Moon ore tier + grade tables ──────────────────────────────────────────────
MOON_BASE_TO_TIER = {
    'Zeolites':'R4',  'Sylvite':'R4',    'Bitumens':'R4',  'Coesite':'R4',
    'Cobaltite':'R8', 'Euxenite':'R8',   'Titanite':'R8',  'Scheelite':'R8',
    'Otavite':'R16',  'Sperrylite':'R16','Vanadinite':'R16','Chromite':'R16',
    'Carnotite':'R32','Zircon':'R32',    'Pollucite':'R32','Cinnabar':'R32',
    'Xenotime':'R64', 'Monazite':'R64',  'Loparite':'R64', 'Ytterbite':'R64',
}
TIER_ORDER  = ['R4','R8','R16','R32','R64']
TIER_LABELS = {'R4':'R4 — Ubiquitous','R8':'R8 — Common','R16':'R16 — Uncommon',
               'R32':'R32 — Rare','R64':'R64 — Exceptional'}

MOON_GRADE_PREFIX = {
    'Brimful':(1,'+5%'),'Copious':(1,'+5%'),'Lavish':(1,'+5%'),
    'Replete':(1,'+5%'),'Bountiful':(1,'+5%'),
    'Glistening':(2,'+10%'),'Twinkling':(2,'+10%'),'Shimmering':(2,'+10%'),
    'Glowing':(2,'+10%'),'Shining':(2,'+10%'),
}

# ── Name helpers ──────────────────────────────────────────────────────────────
def base_name_standard(name):
    n = name.replace('Compressed ', '')
    for s in (' IV-Grade',' III-Grade',' II-Grade'):
        n = n.replace(s, '')
    return n.strip()

def grade_label_standard(name):
    for s, lbl in ((' IV-Grade','IV'),(' III-Grade','III'),(' II-Grade','II')):
        if s in name: return lbl
    return 'Base'

def base_name_moon(name):
    n = name.replace('Compressed ', '')
    for word in MOON_GRADE_PREFIX:
        n = n.replace(word + ' ', '')
    return n.strip()

def grade_label_moon(name):
    for word,(rank,lbl) in MOON_GRADE_PREFIX.items():
        if word + ' ' in name: return lbl
    return 'Base'

def grade_sort_moon(name):
    for word,(rank,_) in MOON_GRADE_PREFIX.items():
        if word + ' ' in name: return rank + 1
    return 0

def base_name_ice(name):
    n = name.replace('Compressed ', '')
    for s in (' IV-Grade',' III-Grade',' II-Grade'):
        n = n.replace(s, '')
    return n.strip()

def grade_label_ice(name):
    return 'IV' if 'IV-Grade' in name else 'Base'

# ── Load DB + SDE ─────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)

ore_rows = conn.execute("""
    SELECT tmi.type_id, tmi.type_name, tmi.category, tmi.display_order,
           COALESCE(it.volume, 0)
    FROM tracked_market_items tmi
    LEFT JOIN inv_types it ON it.type_id = tmi.type_id
    WHERE (
        (tmi.category IN ('standard_ore','moon_ore') AND lower(tmi.type_name) LIKE 'compressed%')
        OR (tmi.category = 'ice_ore' AND lower(tmi.type_name) LIKE 'compressed%')
    )
    ORDER BY tmi.category, tmi.display_order
""").fetchall()

ore_ids = set(r[0] for r in ore_rows)

portion_sizes  = {}
type_materials = {}

with open(os.path.join(SDE_DIR, 'types.jsonl'), encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('_key') in ore_ids:
            portion_sizes[obj['_key']] = obj.get('portionSize', 1)

with open(os.path.join(SDE_DIR, 'typeMaterials.jsonl'), encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('_key') in ore_ids:
            type_materials[obj['_key']] = [
                (m['materialTypeID'], m['quantity']) for m in obj.get('materials', [])
            ]

mat_ids = set()
for mats in type_materials.values():
    for mid, _ in mats: mat_ids.add(mid)

ids_str = ','.join(str(i) for i in mat_ids)
mat_prices = {r[0]: r[1] or 0 for r in conn.execute(f"""
    SELECT type_id, best_buy FROM market_price_snapshots
    WHERE type_id IN ({ids_str})
      AND (type_id, timestamp) IN (
          SELECT type_id, MAX(timestamp) FROM market_price_snapshots
          WHERE type_id IN ({ids_str}) GROUP BY type_id
      )
""").fetchall()}

snap_row = conn.execute(f"""
    SELECT MAX(timestamp) FROM market_price_snapshots WHERE type_id IN ({ids_str})
""").fetchone()
snap_date = 'unknown'
if snap_row and snap_row[0]:
    from datetime import datetime as _dt
    snap_date = _dt.strptime(snap_row[0][:16].replace('T',' '), '%Y-%m-%d %H:%M').strftime('%d %b %Y %H:%M UTC')

conn.close()

# ── Compute values ────────────────────────────────────────────────────────────
def compute_ore(type_id, vol, category):
    stack   = STACK_SIZES[category]
    mats    = type_materials.get(type_id, [])
    portion = portion_sizes.get(type_id, 1)
    val_per_portion = sum(qty * REFINING_EFF * mat_prices.get(mid, 0) for mid, qty in mats)
    val_100  = val_per_portion * stack / portion
    val_92   = val_100 * TTB_RATE
    haul_fee = HAUL_FEE_PER_M3 * vol * stack
    ttb_actual = val_92 - haul_fee
    true_pct   = (ttb_actual / val_100 * 100) if val_100 > 0 else 0
    return {
        'val_92':     round(val_92, 2),
        'true_pct':   round(true_pct, 2),
    }

ore_data = {}
for type_id, type_name, category, display_order, vol in ore_rows:
    ore_data[type_id] = compute_ore(type_id, vol, category)
    ore_data[type_id].update({'name': type_name, 'category': category,
                              'display_order': display_order, 'vol': vol})

# ── Group ─────────────────────────────────────────────────────────────────────
def group_ores(category, base_fn, sort_fn=None):
    rows = [ore_data[r[0]] for r in ore_rows if r[2] == category]
    groups = {}
    for r in rows:
        groups.setdefault(base_fn(r['name']), []).append(r)
    for base in groups:
        groups[base].sort(key=lambda r: sort_fn(r['name']) if sort_fn else r['display_order'])
    return sorted(groups.items(), key=lambda kv: min(r['display_order'] for r in kv[1]))

std_groups  = group_ores('standard_ore', base_name_standard)
moon_groups = group_ores('moon_ore', base_name_moon, sort_fn=grade_sort_moon)
ice_groups  = group_ores('ice_ore', base_name_ice)

moon_by_tier = {t: [] for t in TIER_ORDER}
for base, rows in moon_groups:
    moon_by_tier[MOON_BASE_TO_TIER.get(base, 'R4')].append((base, rows))

# ── Shared helpers ────────────────────────────────────────────────────────────
def fmt_isk(n):
    if n == 0: return '—'
    if abs(n) >= 1e9: return f'{n/1e9:.3f}B'
    if abs(n) >= 1e6: return f'{n/1e6:.2f}M'
    if abs(n) >= 1e3: return f'{n/1e3:.1f}k'
    return f'{n:,.0f}'

def pct_class(pct):
    if pct >= 89: return 'pct-ok'
    if pct >= 83: return 'pct-warn'
    return 'pct-bad'

build_date = datetime.now(timezone.utc).strftime('%d %b %Y')

# ── Grade display ─────────────────────────────────────────────────────────────
def grade_std(name):
    g = grade_label_standard(name)
    return '' if g == 'Base' else f'<span class="gb">{g}</span>'

def grade_moon(name):
    g = grade_label_moon(name)
    return '' if g == 'Base' else f'<span class="gb">{g}</span>'

def grade_ice(name):
    g = grade_label_ice(name)
    return '' if g == 'Base' else f'<span class="gb">{g}</span>'

# ── HTML row builder ──────────────────────────────────────────────────────────
COL_SPAN = 3

def ore_row_html(r, badge_fn):
    pct  = r['true_pct']
    pc   = pct_class(pct)
    nm   = r['name'].replace('Compressed ', '')
    badge = badge_fn(r['name'])
    return (
        f'<tr>'
        f'<td class="td-name">{nm}{badge}</td>'
        f'<td class="td-v92">{fmt_isk(r["val_92"])}</td>'
        f'<td class="td-pct {pc}">{pct:.1f}%</td>'
        f'</tr>'
    )

def section_hdr(label):
    return f'<tr class="sec-hdr"><td colspan="{COL_SPAN}">{label}</td></tr>'

def tier_hdr(label):
    return f'<tr class="tier-hdr"><td colspan="{COL_SPAN}">{label}</td></tr>'

def col_headers():
    return (
        '<tr class="col-hdr">'
        '<th>Ore</th>'
        '<th class="th-v92">92% JBV<br><small>Advertised</small></th>'
        '<th class="th-pct">True %<br><small>of JBV</small></th>'
        '</tr>'
    )

# ── Assemble HTML rows ────────────────────────────────────────────────────────
std_rows_html = ''
for base, rows in std_groups:
    std_rows_html += section_hdr(base)
    for r in rows: std_rows_html += ore_row_html(r, grade_std)

moon_rows_html = ''
for tier in TIER_ORDER:
    tier_grps = moon_by_tier[tier]
    if not tier_grps: continue
    moon_rows_html += tier_hdr(TIER_LABELS[tier])
    for base, rows in tier_grps:
        moon_rows_html += section_hdr(base)
        for r in rows: moon_rows_html += ore_row_html(r, grade_moon)

ice_rows_html = ''
for base, rows in ice_groups:
    ice_rows_html += section_hdr(base)
    for r in rows: ice_rows_html += ore_row_html(r, grade_ice)

# ── HTML ──────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ore Price Table &mdash; Take The Bait Analysis</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;600;700&display=swap');
:root{{
  --bg:#09090d;--panel:#0d1018;--panel2:#111520;--border:#1e2535;
  --text:#d8e0f0;--dim:#5a6880;--green:#33dd88;--gold:#ffd700;--blue:#44aaff;
  --red:#ff5555;--yellow:#ffcc44;--purple:#cc88ff;--cyan:#33ddcc;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;padding:16px 14px 40px;}}
.page{{max-width:600px;margin:0 auto;}}
.snap{{text-align:center;font-size:.74em;color:var(--dim);margin-bottom:14px;}}

.sec-panel{{background:var(--panel);border:1px solid var(--border);border-radius:7px;
  margin-bottom:12px;overflow:hidden;}}
.sec-title{{font-family:'Orbitron',sans-serif;font-size:.68em;font-weight:700;letter-spacing:2px;
  text-transform:uppercase;padding:9px 14px;border-bottom:1px solid var(--border);}}
.sec-title.std{{color:#33dd88;}} .sec-title.moon{{color:#cc88ff;}} .sec-title.ice{{color:#33ddcc;}}

table{{width:100%;border-collapse:collapse;font-size:.82em;}}
th,td{{padding:4px 10px;border-bottom:1px solid var(--border);white-space:nowrap;}}
.col-hdr th{{background:#080b11;color:var(--dim);font-size:.65em;letter-spacing:.8px;
  text-transform:uppercase;text-align:right;border-bottom:2px solid var(--border);}}
.col-hdr th:first-child{{text-align:left;}}
.th-v92{{color:var(--blue) !important;}} .th-pct{{color:var(--dim) !important;}}

.sec-hdr td{{background:rgba(255,255,255,.02);color:var(--dim);font-size:.68em;
  letter-spacing:1px;text-transform:uppercase;padding:4px 10px;
  border-top:1px solid var(--border);}}
.tier-hdr td{{background:rgba(204,136,255,.07);color:#cc88ff;
  font-family:'Orbitron',sans-serif;font-size:.58em;font-weight:700;
  letter-spacing:2px;text-transform:uppercase;padding:6px 10px;
  border-top:2px solid rgba(204,136,255,.2);}}

td{{text-align:right;}}
.td-name{{text-align:left;font-weight:600;font-size:.88em;color:var(--text);}}
.td-v92{{font-family:'Orbitron',sans-serif;font-size:.75em;font-weight:700;color:var(--blue);}}
.td-pct{{font-family:'Orbitron',sans-serif;font-size:.78em;font-weight:700;}}
.pct-ok{{color:#33dd88;}}.pct-warn{{color:var(--yellow);}}.pct-bad{{color:var(--red);}}

.gb{{display:inline-block;font-family:'Orbitron',sans-serif;font-size:.52em;font-weight:700;
  letter-spacing:.5px;padding:1px 4px;border-radius:2px;margin-left:4px;vertical-align:middle;
  background:rgba(255,204,68,.12);border:1px solid rgba(255,204,68,.3);color:var(--yellow);}}

.footer{{text-align:center;color:var(--dim);font-size:.72em;margin-top:14px;
  padding-top:10px;border-top:1px solid var(--border);}}
</style>
</head>
<body>
<div class="page">
<div class="snap">Jita buy · 90.63% refine · {snap_date}</div>

<div class="sec-panel">
  <div class="sec-title std">Standard Ore</div>
  <table>{col_headers()}{std_rows_html}</table>
</div>

<div class="sec-panel">
  <div class="sec-title moon">Moon Ore</div>
  <table>{col_headers()}{moon_rows_html}</table>
</div>

<div class="sec-panel">
  <div class="sec-title ice">Ice Ore</div>
  <table>{col_headers()}{ice_rows_html}</table>
</div>

<div class="footer">Take The Bait Analysis &middot; 92% JBV &minus; 125 ISK/m&sup3; &middot; {build_date}</div>
</div>
</body>
</html>"""

out_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ore_price_table.html')
with open(out_html, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML written: ore_price_table.html")

# ══════════════════════════════════════════════════════════════════════════════
# PNG generation — multi-column layout for tall categories
# ══════════════════════════════════════════════════════════════════════════════
try:
    from PIL import Image, ImageDraw, ImageFont

    FONT_DIR = r'C:\Windows\Fonts'
    def lf(name, size):
        try: return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
        except: return ImageFont.load_default()

    F_SEC   = lf('segoeuib.ttf', 12)
    F_HDR   = lf('segoeuib.ttf', 10)
    F_NAME  = lf('segoeui.ttf',  12)
    F_GRADE = lf('segoeuib.ttf',  9)
    F_VAL   = lf('segoeuib.ttf', 12)
    F_SNAP  = lf('segoeui.ttf',   9)

    BG       = ( 9,  9, 13)
    BG_PANEL = (13, 16, 24)
    BG_SEC   = (16, 20, 30)
    BG_TIER  = (22, 14, 36)
    BG_ROW_A = (13, 16, 24)
    BG_ROW_B = (17, 21, 33)
    C_BORDER = (30, 37, 53)
    C_TEXT   = (216, 224, 240)
    C_DIM    = ( 90, 104, 128)
    C_GOLD   = (255, 204,  68)
    C_BLUE   = ( 68, 170, 255)
    C_GREEN  = ( 51, 221, 136)
    C_YELLOW = (255, 204,  68)
    C_RED    = (255,  85,  85)
    C_STD    = ( 51, 221, 136)
    C_MOON   = (204, 136, 255)
    C_ICE    = ( 51, 221, 204)

    PAD      = 14
    ROW_H    = 19
    SEC_H    = 17
    TIER_H   = 20
    TITLE_H  = 20
    COLHDR_H = 18
    SNAP_H   = 14
    FOOTER_H = 14
    TOP_PAD  = 8
    BOT_PAD  = 8
    COL_GAP  = 10   # gap between columns

    def tw(draw, text, font):
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]

    def pct_color(pct):
        if pct >= 89: return C_GREEN
        if pct >= 83: return C_YELLOW
        return C_RED

    def build_png_rows(grouped, badge_fn, tier_fn=None):
        result = []
        if tier_fn:
            for tier in TIER_ORDER:
                tier_grps = tier_fn(tier)
                if not tier_grps: continue
                result.append(('tier', TIER_LABELS[tier]))
                for base, rows in tier_grps:
                    result.append(('sec', base))
                    for r in rows:
                        result.append(('ore', r, badge_fn(r['name'])))
        else:
            for base, rows in grouped:
                result.append(('sec', base))
                for r in rows:
                    result.append(('ore', r, badge_fn(r['name'])))
        return result

    def row_h(row):
        if row[0] == 'tier': return TIER_H
        if row[0] == 'sec':  return SEC_H
        return ROW_H

    def col_height(rows):
        return sum(row_h(r) for r in rows)

    def split_cols(rows, ncols):
        """Split rows into ncols roughly equal height groups, only at group boundaries."""
        if ncols == 1:
            return [rows]
        total_h = col_height(rows)
        target  = total_h / ncols
        cols    = []
        remaining = list(rows)
        for c in range(ncols - 1):
            cumul = 0
            split_at = 0
            for i, row in enumerate(remaining):
                cumul += row_h(row)
                # only split at the start of a new group (sec or tier row)
                if cumul >= target and i + 1 < len(remaining):
                    next_type = remaining[i + 1][0]
                    if next_type in ('sec', 'tier'):
                        split_at = i + 1
                        break
            if split_at == 0:
                split_at = len(remaining) // 2
            cols.append(remaining[:split_at])
            remaining = remaining[split_at:]
            target = col_height(remaining) / max(1, ncols - c - 1)
        cols.append(remaining)
        return cols

    def draw_image(rows, title, accent_color, out_path, ncols=1):
        cols = split_cols(rows, ncols)
        max_col_h = max(col_height(c) for c in cols)

        # Per-column pixel widths
        # Single col: 640px wide.  Two cols: 920px.  Three cols: same per-col width.
        if ncols == 1:
            img_w    = 640
            col_w    = img_w - PAD * 2
            name_w   = 300
            v92_w    = 140
            pct_w    = col_w - name_w - v92_w
        else:
            col_w    = 420
            name_w   = 230
            v92_w    = 110
            pct_w    = col_w - name_w - v92_w
            img_w    = PAD + ncols * col_w + (ncols - 1) * COL_GAP + PAD

        H = TOP_PAD + SNAP_H + 4 + TITLE_H + COLHDR_H + max_col_h + BOT_PAD + FOOTER_H + 4
        img  = Image.new('RGB', (img_w, H), BG)
        draw = ImageDraw.Draw(img)

        y = TOP_PAD

        # Snap note
        draw.text((PAD, y), f'Jita buy · 90.63% refine · {snap_date}',
                  font=F_SNAP, fill=C_DIM)
        y += SNAP_H + 4

        # Title bar (full width)
        draw.rectangle([(PAD, y), (img_w - PAD, y + TITLE_H - 1)], fill=BG_PANEL)
        draw.rectangle([(PAD, y), (PAD + 3, y + TITLE_H - 1)], fill=accent_color)
        draw.text((PAD + 8, y + 3), title.upper(), font=F_SEC, fill=accent_color)
        y += TITLE_H

        # Column headers — one set per column
        for ci in range(ncols):
            x0 = PAD + ci * (col_w + COL_GAP)
            x1 = x0 + col_w
            draw.rectangle([(x0, y), (x1, y + COLHDR_H - 1)], fill=(8, 11, 17))
            draw.text((x0 + 4, y + 3), 'ORE', font=F_HDR, fill=C_DIM)
            v92_lbl = '92% JBV (ADVERTISED)'
            draw.text((x0 + name_w + v92_w - tw(draw, v92_lbl, F_HDR) - 4, y + 3),
                      v92_lbl, font=F_HDR, fill=C_BLUE)
            pct_lbl = 'TRUE %'
            draw.text((x0 + name_w + v92_w + pct_w - tw(draw, pct_lbl, F_HDR) - 4, y + 3),
                      pct_lbl, font=F_HDR, fill=C_DIM)
            draw.line([(x0, y + COLHDR_H), (x1, y + COLHDR_H)], fill=C_BORDER, width=2)
        y += COLHDR_H

        data_y = y

        # Draw each column
        for ci, col_rows in enumerate(cols):
            x0  = PAD + ci * (col_w + COL_GAP)
            x1  = x0 + col_w
            cy  = data_y
            ri  = 0
            for row in col_rows:
                if row[0] == 'tier':
                    draw.rectangle([(x0, cy), (x1, cy + TIER_H - 1)], fill=BG_TIER)
                    draw.line([(x0, cy), (x1, cy)], fill=(80, 40, 120), width=1)
                    draw.text((x0 + 6, cy + 3), row[1].upper(), font=F_SEC, fill=C_MOON)
                    cy += TIER_H
                elif row[0] == 'sec':
                    draw.rectangle([(x0, cy), (x1, cy + SEC_H - 1)], fill=BG_SEC)
                    draw.text((x0 + 6, cy + 2), row[1].upper(), font=F_HDR, fill=C_DIM)
                    cy += SEC_H
                else:
                    _, r, grade = row
                    draw.rectangle([(x0, cy), (x1, cy + ROW_H - 1)],
                                   fill=BG_ROW_A if ri % 2 == 0 else BG_ROW_B)
                    nm = r['name'].replace('Compressed ', '')
                    draw.text((x0 + 6, cy + 3), nm, font=F_NAME, fill=C_TEXT)
                    if grade:
                        nm_w = tw(draw, nm, F_NAME)
                        bx = x0 + 6 + nm_w + 4
                        bw = tw(draw, grade, F_GRADE) + 6
                        draw.rectangle([(bx, cy + 4), (bx + bw, cy + 14)],
                                       fill=(40, 35, 10), outline=(120, 100, 30))
                        draw.text((bx + 3, cy + 4), grade, font=F_GRADE, fill=C_GOLD)
                    # 92% JBV
                    v92s = fmt_isk(r['val_92'])
                    draw.text((x0 + name_w + v92_w - tw(draw, v92s, F_VAL) - 6, cy + 3),
                              v92s, font=F_VAL, fill=C_BLUE)
                    # True %
                    pcts = f"{r['true_pct']:.1f}%"
                    draw.text((x0 + name_w + v92_w + pct_w - tw(draw, pcts, F_VAL) - 6, cy + 3),
                              pcts, font=F_VAL, fill=pct_color(r['true_pct']))
                    draw.line([(x0, cy + ROW_H - 1), (x1, cy + ROW_H - 1)], fill=C_BORDER)
                    cy += ROW_H
                    ri += 1

        # Footer
        fy = data_y + max_col_h + 4
        draw.text((PAD, fy),
                  f'Take The Bait · 92% JBV - 125 ISK/m3 · {build_date}',
                  font=F_SNAP, fill=C_DIM)

        img.save(out_path)
        print(f"PNG written: {os.path.basename(out_path)}  ({img_w}x{H}px)")

    def gl_std(name):  return grade_label_standard(name) if grade_label_standard(name) != 'Base' else ''
    def gl_moon(name): return grade_label_moon(name) if grade_label_moon(name) != 'Base' else ''
    def gl_ice(name):  return grade_label_ice(name) if grade_label_ice(name) != 'Base' else ''

    base_dir = os.path.dirname(os.path.abspath(__file__))

    std_rows  = build_png_rows(std_groups, gl_std)
    moon_rows = build_png_rows(moon_groups, gl_moon, tier_fn=lambda t: moon_by_tier[t])
    ice_rows  = build_png_rows(ice_groups, gl_ice)

    draw_image(std_rows,  'Standard Ore', C_STD,  os.path.join(base_dir, 'ore_price_std.png'),  ncols=3)
    draw_image(moon_rows, 'Moon Ore',     C_MOON, os.path.join(base_dir, 'ore_price_moon.png'), ncols=2)
    draw_image(ice_rows,  'Ice Ore',      C_ICE,  os.path.join(base_dir, 'ore_price_ice.png'),  ncols=1)

except ImportError:
    print("Pillow not installed — skipping PNG generation (pip install Pillow)")
except Exception as e:
    import traceback
    print(f"PNG generation error: {e}")
    traceback.print_exc()

print(f"\nJita snapshot: {snap_date}")
print(f"Settings: {REFINING_EFF*100:.2f}% refining | {TTB_RATE*100:.0f}% TTB | {HAUL_FEE_PER_M3:.0f} ISK/m3 fee")
