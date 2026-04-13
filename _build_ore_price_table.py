"""
Build ore_price_table.html — Compressed ore pricing transparency table.
Shows true cost of selling to Take The Bait buyback at 92% JBV - 125 ISK/m³.

Stack sizes:  Standard & Moon ore = 100 units   |   Ice = 1 unit
Refining eff: 90.63% (Tatara max)
Columns:      100% JBV | 92% JBV (advertised) | 125/m³ Deduction | True Price | Effective %
"""
import json, sqlite3, os, math
from datetime import datetime, timezone

REFINING_EFF    = 0.9063
TTB_RATE        = 0.92
HAUL_FEE_PER_M3 = 125.0
STACK_SIZES     = {'standard_ore': 100, 'moon_ore': 100, 'ice_ore': 1}

DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mydatabase.db')
SDE_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sde')

# ── Moon ore tier lookup ──────────────────────────────────────────────────────
# Derived from display_order blocks in tracked_market_items
MOON_BASE_TO_TIER = {
    'Zeolites': 'R4',  'Sylvite': 'R4',    'Bitumens': 'R4',  'Coesite': 'R4',
    'Cobaltite':'R8',  'Euxenite': 'R8',   'Titanite': 'R8',  'Scheelite': 'R8',
    'Otavite':  'R16', 'Sperrylite': 'R16','Vanadinite':'R16','Chromite': 'R16',
    'Carnotite':'R32', 'Zircon': 'R32',    'Pollucite':'R32', 'Cinnabar': 'R32',
    'Xenotime': 'R64', 'Monazite': 'R64',  'Loparite': 'R64', 'Ytterbite': 'R64',
}
TIER_ORDER  = ['R4', 'R8', 'R16', 'R32', 'R64']
TIER_LABELS = {'R4':'R4 — Ubiquitous','R8':'R8 — Common','R16':'R16 — Uncommon',
               'R32':'R32 — Rare','R64':'R64 — Exceptional'}

# Grade prefix words for moon ores (word → (grade_rank, label))
MOON_GRADE = {
    'Brimful':(1,'+5%'),'Copious':(1,'+5%'),'Lavish':(1,'+5%'),
    'Replete':(1,'+5%'),'Bountiful':(1,'+5%'),
    'Glistening':(2,'+10%'),'Twinkling':(2,'+10%'),'Shimmering':(2,'+10%'),
    'Glowing':(2,'+10%'),'Shining':(2,'+10%'),
}

# Mineral category colour classes (for pills in table)
MINERAL_COLOUR = {
    # Basic minerals
    'Tritanium':'min','Pyerite':'min','Mexallon':'min','Isogen':'min',
    'Nocxium':'min','Zydrine':'min','Megacyte':'min','Morphite':'min',
    # Raw ores-as-minerals (atmospheric etc)
    'Atmospheric Gases':'raw','Evaporite Deposits':'raw','Silicates':'raw',
    'Hydrocarbons':'raw','Cadmium':'raw','Caesium':'raw','Chromium':'raw',
    'Cobalt':'raw','Dysprosium':'raw','Hafnium':'raw','Mercury':'raw',
    'Neodymium':'raw','Promethium':'raw','Technetium':'raw','Thulium':'raw',
    'Titanium':'raw','Tungsten':'raw','Vanadium':'raw',
    # Ice products
    'Heavy Water':'ice','Liquid Ozone':'ice','Strontium Clathrates':'ice',
    'Nitrogen Isotopes':'iso','Helium Isotopes':'iso',
    'Oxygen Isotopes':'iso','Hydrogen Isotopes':'iso',
    # Moon materials
    'Atmospheric Gases':'raw','Evaporite Deposits':'raw',
}

def base_name_standard(name):
    """'Compressed Veldspar III-Grade' → 'Veldspar'"""
    n = name.replace('Compressed ', '')
    for sfx in (' IV-Grade', ' III-Grade', ' II-Grade'):
        n = n.replace(sfx, '')
    return n.strip()

def grade_label_standard(name):
    for sfx, lbl in ((' IV-Grade','IV'), (' III-Grade','III'), (' II-Grade','II')):
        if sfx in name:
            return lbl
    return 'Base'

def base_name_moon(name):
    """'Compressed Brimful Zeolites' → 'Zeolites'"""
    n = name.replace('Compressed ', '')
    for word in MOON_GRADE:
        n = n.replace(word + ' ', '')
    return n.strip()

def grade_label_moon(name):
    for word, (rank, _) in MOON_GRADE.items():
        if word + ' ' in name:
            return '+5%' if rank == 1 else '+10%'
    return 'Base'

def grade_sort_moon(name):
    for word, (rank, _) in MOON_GRADE.items():
        if word + ' ' in name:
            return rank + 1
    return 0

def base_name_ice(name):
    """'Compressed Blue Ice IV-Grade' → 'Blue Ice'"""
    n = name.replace('Compressed ', '')
    for sfx in (' IV-Grade', ' III-Grade', ' II-Grade'):
        n = n.replace(sfx, '')
    return n.strip()

def grade_label_ice(name):
    if 'IV-Grade' in name:
        return 'IV'
    return 'Base'

# ── Load data ─────────────────────────────────────────────────────────────────
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

# SDE: portionSize + typeMaterials
portion_sizes = {}
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
    for mid, _ in mats:
        mat_ids.add(mid)

# Load mineral names from SDE
mat_names = {}
with open(os.path.join(SDE_DIR, 'types.jsonl'), encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('_key') in mat_ids:
            nm = obj.get('name', {})
            mat_names[obj['_key']] = (nm.get('en') or obj.get('typeName', '')) if isinstance(nm, dict) else str(nm)

# Fetch latest Jita buy prices for materials
ids_str = ','.join(str(i) for i in mat_ids)
mat_price_rows = conn.execute(f"""
    SELECT type_id, best_buy FROM market_price_snapshots
    WHERE type_id IN ({ids_str})
      AND (type_id, timestamp) IN (
          SELECT type_id, MAX(timestamp) FROM market_price_snapshots
          WHERE type_id IN ({ids_str})
          GROUP BY type_id
      )
""").fetchall()
mat_prices = {r[0]: r[1] or 0 for r in mat_price_rows}

snap_row = conn.execute(f"""
    SELECT MAX(timestamp) FROM market_price_snapshots WHERE type_id IN ({ids_str})
""").fetchone()
snap_date = 'unknown'
if snap_row and snap_row[0]:
    from datetime import datetime as _dt
    snap_date = _dt.strptime(snap_row[0][:16].replace('T', ' '), '%Y-%m-%d %H:%M').strftime('%d %b %Y %H:%M UTC')

conn.close()

# ── Compute per-ore values ────────────────────────────────────────────────────
def compute_ore(type_id, vol, category):
    stack = STACK_SIZES[category]
    mats  = type_materials.get(type_id, [])
    # Refine value for one full "portionSize" batch = sum(qty × eff × price)
    # Then scale by stack / portionSize to get stack value
    portion = portion_sizes.get(type_id, 1)
    val_per_portion = sum(qty * REFINING_EFF * mat_prices.get(mid, 0) for mid, qty in mats)
    val_100 = val_per_portion * stack / portion
    val_92  = val_100 * TTB_RATE
    haul_fee = HAUL_FEE_PER_M3 * vol * stack
    ttb_actual = val_92 - haul_fee
    true_pct = (ttb_actual / val_100 * 100) if val_100 > 0 else 0
    mineral_names = [mat_names.get(mid, str(mid)) for mid, _ in mats]
    return {
        'val_100':    round(val_100, 2),
        'val_92':     round(val_92, 2),
        'haul_fee':   round(haul_fee, 2),
        'ttb_actual': round(ttb_actual, 2),
        'true_pct':   round(true_pct, 2),
        'stack_m3':   round(vol * stack, 4),
        'minerals':   mineral_names,
    }

ore_data = {}
for type_id, type_name, category, display_order, vol in ore_rows:
    ore_data[type_id] = compute_ore(type_id, vol, category)
    ore_data[type_id].update({'name': type_name, 'category': category, 'display_order': display_order})

# ── Build grouped structure ───────────────────────────────────────────────────
def group_ores(category, base_fn, grade_fn, sort_fn=None):
    rows = [ore_data[r[0]] for r in ore_rows if r[2] == category]
    groups = {}
    for r in rows:
        base = base_fn(r['name'])
        groups.setdefault(base, []).append(r)
    # Sort within each group
    for base in groups:
        groups[base].sort(key=lambda r: sort_fn(r['name']) if sort_fn else r['display_order'])
    # Sort group order by min display_order
    sorted_groups = sorted(groups.items(), key=lambda kv: min(r['display_order'] for r in kv[1]))
    return sorted_groups

std_groups  = group_ores('standard_ore', base_name_standard, grade_label_standard)
moon_groups = group_ores('moon_ore', base_name_moon, grade_label_moon, sort_fn=grade_sort_moon)
ice_groups  = group_ores('ice_ore', base_name_ice, grade_label_ice)

# Organise moon by tier
moon_by_tier = {t: [] for t in TIER_ORDER}
for base, rows in moon_groups:
    tier = MOON_BASE_TO_TIER.get(base, 'R4')
    moon_by_tier[tier].append((base, rows))

# ── HTML helpers ──────────────────────────────────────────────────────────────
def fmt_isk(n):
    if n == 0:
        return '—'
    if abs(n) >= 1e9:
        return f'{n/1e9:.3f}B'
    if abs(n) >= 1e6:
        return f'{n/1e6:.2f}M'
    if abs(n) >= 1e3:
        return f'{n/1e3:.1f}k'
    return f'{n:,.0f}'

def pct_class(pct):
    if pct >= 89: return 'pct-ok'
    if pct >= 83: return 'pct-warn'
    return 'pct-bad'

def mineral_pills(mineral_names):
    pills = []
    for nm in mineral_names:
        cls = MINERAL_COLOUR.get(nm, 'min')
        pills.append(f'<span class="pill-{cls}">{nm}</span>')
    return ' '.join(pills)

def grade_badge_std(name):
    g = grade_label_standard(name)
    if g == 'Base':
        return '<span class="gb gb-base">Base</span>'
    return f'<span class="gb gb-grade">{g}</span>'

def grade_badge_moon(name):
    g = grade_label_moon(name)
    if g == 'Base':
        return '<span class="gb gb-base">Base</span>'
    return f'<span class="gb gb-grade">{g}</span>'

def grade_badge_ice(name):
    g = grade_label_ice(name)
    if g == 'Base':
        return '<span class="gb gb-base">Base</span>'
    return f'<span class="gb gb-grade">{g}</span>'

def ore_row(r, badge_fn):
    pct = r['true_pct']
    pc  = pct_class(pct)
    nm  = r['name'].replace('Compressed ', '')
    badge = badge_fn(r['name'])
    mins  = mineral_pills(r['minerals'])
    return (
        f'<tr>'
        f'<td class="td-name">{nm} {badge}</td>'
        f'<td class="td-stack">{fmt_isk(r["stack_m3"])} m³</td>'
        f'<td class="td-min">{mins}</td>'
        f'<td class="td-v100">{fmt_isk(r["val_100"])}</td>'
        f'<td class="td-v92">{fmt_isk(r["val_92"])}</td>'
        f'<td class="td-fee">−{fmt_isk(r["haul_fee"])}</td>'
        f'<td class="td-ttb">{fmt_isk(r["ttb_actual"])}</td>'
        f'<td class="td-pct {pc}">{pct:.1f}%</td>'
        f'</tr>'
    )

def section_header(label, icon=''):
    return f'<tr class="sec-hdr"><td colspan="8">{icon} {label}</td></tr>'

def col_headers():
    return (
        '<tr class="col-hdr">'
        '<th>Ore</th>'
        '<th>Stack m³</th>'
        '<th>Refines To</th>'
        '<th class="th-v100">100% JBV</th>'
        '<th class="th-v92">92% JBV<br><small>Advertised</small></th>'
        '<th class="th-fee">125/m³ Fee</th>'
        '<th class="th-ttb">True Price<br><small>What you get</small></th>'
        '<th class="th-pct">True %<br><small>of JBV</small></th>'
        '</tr>'
    )

build_date = datetime.now(timezone.utc).strftime('%d %b %Y')

# ── Assemble rows ─────────────────────────────────────────────────────────────
std_rows_html = ''
for base, rows in std_groups:
    std_rows_html += section_header(base)
    for r in rows:
        std_rows_html += ore_row(r, grade_badge_std)

moon_rows_html = ''
for tier in TIER_ORDER:
    tier_groups = moon_by_tier[tier]
    if not tier_groups:
        continue
    moon_rows_html += f'<tr class="tier-hdr"><td colspan="8">{TIER_LABELS[tier]}</td></tr>'
    for base, rows in tier_groups:
        moon_rows_html += section_header(base)
        for r in rows:
            moon_rows_html += ore_row(r, grade_badge_moon)

ice_rows_html = ''
for base, rows in ice_groups:
    ice_rows_html += section_header(base)
    for r in rows:
        ice_rows_html += ore_row(r, grade_badge_ice)

# ── HTML ──────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ore Price Transparency &mdash; Take The Bait Analysis</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;600;700&display=swap');
:root{{
  --accent:#ff8833;--accent2:#ffcc44;--bg:#09090d;--panel:#0d1018;
  --panel2:#111520;--border:#1e2535;--border-o:rgba(255,140,50,.2);
  --text:#d8e0f0;--dim:#5a6880;--green:#33dd88;--red:#ff5555;--gold:#ffd700;
  --blue:#44aaff;--purple:#cc88ff;--cyan:#33ddcc;--orange:#ff9944;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;padding:20px 14px 60px;}}
.page{{max-width:1400px;margin:0 auto;}}

/* Header */
.hdr{{text-align:center;margin-bottom:24px;padding:24px;background:var(--panel);
  border:1px solid var(--border);border-radius:10px;}}
.hdr h1{{font-family:'Orbitron',sans-serif;font-size:1.4em;font-weight:900;letter-spacing:4px;
  background:linear-gradient(135deg,#ff9944,#ffcc44);-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;background-clip:text;}}
.hdr .sub{{color:var(--dim);font-size:.85em;letter-spacing:2px;text-transform:uppercase;margin-top:5px;}}
.hdr .desc{{margin-top:14px;font-size:.9em;color:var(--text);max-width:820px;margin-left:auto;margin-right:auto;line-height:1.6;}}
.hdr .desc strong{{color:var(--accent2);}}
.hdr .desc .red{{color:var(--red);font-weight:700;}}

/* Formula callout */
.formula-bar{{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:14px;}}
.f-cell{{background:var(--panel2);border:1px solid var(--border);border-radius:6px;
  padding:8px 16px;text-align:center;}}
.f-lbl{{font-size:.68em;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;}}
.f-val{{font-family:'Orbitron',sans-serif;font-size:.82em;font-weight:700;}}
.f-cell.fc-100 .f-val{{color:var(--gold);}}
.f-cell.fc-92  .f-val{{color:var(--blue);}}
.f-cell.fc-fee .f-val{{color:var(--red);}}
.f-cell.fc-ttb .f-val{{color:var(--red);}}
.f-cell.fc-eff .f-val{{color:var(--dim);}}

/* Snap note */
.snap{{text-align:center;font-size:.76em;color:var(--dim);margin-bottom:18px;}}

/* Section panels */
.sec-panel{{background:var(--panel);border:1px solid var(--border);border-radius:8px;
  margin-bottom:16px;overflow:hidden;}}
.sec-title{{font-family:'Orbitron',sans-serif;font-size:.72em;font-weight:700;letter-spacing:2px;
  text-transform:uppercase;padding:12px 18px;border-bottom:1px solid var(--border);}}
.sec-title.std{{color:#33dd88;background:rgba(51,221,136,.04);}}
.sec-title.moon{{color:#cc88ff;background:rgba(204,136,255,.04);}}
.sec-title.ice{{color:#33ddcc;background:rgba(51,221,204,.04);}}

/* Table */
.tbl-wrap{{overflow-x:auto;}}
table{{width:100%;border-collapse:collapse;font-size:.83em;}}
th,td{{padding:6px 10px;border-bottom:1px solid var(--border);white-space:nowrap;}}

/* Column header */
.col-hdr th{{background:#0a0d14;color:var(--dim);font-size:.68em;letter-spacing:.8px;
  text-transform:uppercase;text-align:right;border-bottom:2px solid var(--border);}}
.col-hdr th:first-child{{text-align:left;}}
.col-hdr th:nth-child(3){{text-align:left;}}
.th-v100{{color:var(--gold) !important;}}
.th-v92{{color:var(--blue) !important;}}
.th-fee{{color:var(--red) !important;}}
.th-ttb{{color:var(--red) !important;opacity:.9;}}
.th-pct{{color:var(--dim) !important;}}

/* Ore group section header */
.sec-hdr td{{background:rgba(255,255,255,.025);color:var(--dim);
  font-size:.72em;letter-spacing:1px;text-transform:uppercase;
  padding:5px 10px;border-bottom:1px solid var(--border);border-top:1px solid var(--border);}}

/* Tier header (moon ore) */
.tier-hdr td{{background:rgba(204,136,255,.08);color:#cc88ff;
  font-family:'Orbitron',sans-serif;font-size:.62em;font-weight:700;letter-spacing:2px;
  text-transform:uppercase;padding:8px 10px;border-top:2px solid rgba(204,136,255,.2);}}

/* Data cells */
td{{text-align:right;}}
.td-name{{text-align:left;font-weight:600;font-size:.9em;color:var(--text);}}
.td-stack{{color:var(--dim);font-size:.82em;}}
.td-min{{text-align:left;}}
.td-v100{{font-family:'Orbitron',sans-serif;font-size:.78em;font-weight:700;color:var(--gold);}}
.td-v92{{font-family:'Orbitron',sans-serif;font-size:.78em;font-weight:700;color:var(--blue);}}
.td-fee{{font-family:'Orbitron',sans-serif;font-size:.78em;font-weight:700;color:#ff7777;}}
.td-ttb{{font-family:'Orbitron',sans-serif;font-size:.82em;font-weight:700;color:#ff5555;}}
.td-pct{{font-family:'Orbitron',sans-serif;font-size:.82em;font-weight:700;}}
.pct-ok{{color:#33dd88;}}.pct-warn{{color:var(--accent2);}}.pct-bad{{color:var(--red);}}

/* Grade badges */
.gb{{display:inline-block;font-family:'Orbitron',sans-serif;font-size:.55em;font-weight:700;
  letter-spacing:.5px;padding:1px 5px;border-radius:3px;margin-left:4px;vertical-align:middle;}}
.gb-base{{background:rgba(90,104,128,.2);border:1px solid rgba(90,104,128,.3);color:var(--dim);}}
.gb-grade{{background:rgba(255,204,68,.12);border:1px solid rgba(255,204,68,.3);color:var(--accent2);}}

/* Mineral pills */
.pill-min{{display:inline-block;background:rgba(68,170,255,.1);border:1px solid rgba(68,170,255,.25);
  border-radius:3px;color:#88ccff;font-size:.72em;padding:1px 5px;margin:1px 2px;white-space:nowrap;}}
.pill-raw{{display:inline-block;background:rgba(204,136,255,.1);border:1px solid rgba(204,136,255,.25);
  border-radius:3px;color:#cc88ff;font-size:.72em;padding:1px 5px;margin:1px 2px;white-space:nowrap;}}
.pill-ice{{display:inline-block;background:rgba(51,221,204,.1);border:1px solid rgba(51,221,204,.25);
  border-radius:3px;color:#33ddcc;font-size:.72em;padding:1px 5px;margin:1px 2px;white-space:nowrap;}}
.pill-iso{{display:inline-block;background:rgba(51,221,136,.1);border:1px solid rgba(51,221,136,.25);
  border-radius:3px;color:#33dd88;font-size:.72em;padding:1px 5px;margin:1px 2px;white-space:nowrap;}}

/* Legend */
.legend{{display:flex;gap:20px;flex-wrap:wrap;padding:10px 16px;border-top:1px solid var(--border);
  font-size:.77em;color:var(--dim);}}
.leg-item{{display:flex;align-items:center;gap:6px;}}
.leg-dot{{width:10px;height:10px;border-radius:2px;}}

.footer{{text-align:center;color:var(--dim);font-size:.76em;margin-top:24px;
  padding-top:12px;border-top:1px solid var(--border);}}
</style>
</head>
<body>
<div class="page">

<div class="hdr">
  <h1>ORE PRICING TRANSPARENCY</h1>
  <div class="sub">Take The Bait Buyback &middot; Tenal &middot; True Cost Analysis</div>
  <div class="desc">
    Take The Bait advertises <strong>92% JBV</strong> for ore buyback &mdash; but applies an additional
    <strong class="red">125 ISK/m³ haul charge</strong> on top.
    This table shows the <strong>true effective price</strong> you receive after that deduction.
    Mineral values based on <strong>90.63% refining efficiency</strong> (Tatara max) &times; current Jita buy prices.
    Stack sizes: <strong>100 units</strong> for standard &amp; moon ore &middot; <strong>1 unit</strong> for ice.
  </div>
  <div class="formula-bar">
    <div class="f-cell fc-100"><div class="f-lbl">100% JBV</div><div class="f-val">Full mineral value at 90.63%</div></div>
    <div class="f-cell" style="align-self:center;color:var(--dim);font-size:1.2em;">&times;</div>
    <div class="f-cell fc-92"><div class="f-lbl">Advertised rate</div><div class="f-val">92% JBV</div></div>
    <div class="f-cell" style="align-self:center;color:var(--red);font-size:1.2em;">&minus;</div>
    <div class="f-cell fc-fee"><div class="f-lbl">Haul charge</div><div class="f-val">125 ISK/m³ × stack m³</div></div>
    <div class="f-cell" style="align-self:center;color:var(--dim);font-size:1.2em;">=</div>
    <div class="f-cell fc-ttb"><div class="f-lbl">What you actually receive</div><div class="f-val">True Price</div></div>
  </div>
</div>

<div class="snap">Jita buy prices as of {snap_date} &middot; Refining efficiency: 90.63%</div>

<!-- Standard Ore -->
<div class="sec-panel">
  <div class="sec-title std">&#9632; Standard Ore &mdash; Stack of 100 compressed units</div>
  <div class="tbl-wrap">
  <table>
    {col_headers()}
    {std_rows_html}
  </table>
  </div>
  <div class="legend">
    <div class="leg-item"><div class="leg-dot" style="background:#88ccff;"></div> Basic Minerals (Tritanium, Pyerite, etc.)</div>
    <div class="leg-item"><div class="leg-dot" style="background:#cc88ff;"></div> Auxiliary Minerals (Atmospheric Gases, etc.)</div>
  </div>
</div>

<!-- Moon Ore -->
<div class="sec-panel">
  <div class="sec-title moon">&#9670; Moon Ore &mdash; Stack of 100 compressed units</div>
  <div class="tbl-wrap">
  <table>
    {col_headers()}
    {moon_rows_html}
  </table>
  </div>
  <div class="legend">
    <div class="leg-item"><div class="leg-dot" style="background:#cc88ff;"></div> Moon Materials (R4/R8/R16/R32/R64 goo)</div>
    <div class="leg-item"><div class="leg-dot" style="background:#88ccff;"></div> Basic Minerals</div>
  </div>
</div>

<!-- Ice Ore -->
<div class="sec-panel">
  <div class="sec-title ice">&#10052; Ice Ore &mdash; Stack of 1 compressed unit</div>
  <div class="tbl-wrap">
  <table>
    {col_headers()}
    {ice_rows_html}
  </table>
  </div>
  <div class="legend">
    <div class="leg-item"><div class="leg-dot" style="background:#33ddcc;"></div> Ice Products (Heavy Water, Liquid Ozone, Strontium)</div>
    <div class="leg-item"><div class="leg-dot" style="background:#33dd88;"></div> Isotopes (Nitrogen, Helium, Oxygen, Hydrogen)</div>
  </div>
</div>

<div class="footer">
  Infinite Solutions &middot; Hamektok Hakaari &middot;
  Built {build_date} &middot; Data: Jita buy prices at 90.63% refining efficiency
</div>
</div>
</body>
</html>"""

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ore_price_table.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

# Stats
total = len(ore_rows)
std_c = sum(1 for r in ore_rows if r[2] == 'standard_ore')
moon_c = sum(1 for r in ore_rows if r[2] == 'moon_ore')
ice_c  = sum(1 for r in ore_rows if r[2] == 'ice_ore')
print(f"Done. Written to ore_price_table.html")
print(f"  Ores: {total} total ({std_c} standard, {moon_c} moon, {ice_c} ice)")
print(f"  Minerals: {len(mat_ids)} types, all priced")
print(f"  Jita snapshot: {snap_date}")
print(f"  Settings: {REFINING_EFF*100:.2f}% refining, {TTB_RATE*100:.0f}% TTB rate, {HAUL_FEE_PER_M3:.0f} ISK/m³ fee")
