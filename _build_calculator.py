import sqlite3, json

conn = sqlite3.connect('mydatabase.db')
cur = conn.cursor()

rows = cur.execute("""
    WITH latest_mps AS (
        SELECT type_id, best_buy
        FROM market_price_snapshots
        WHERE (type_id, timestamp) IN (
            SELECT type_id, MAX(timestamp) FROM market_price_snapshots GROUP BY type_id
        )
    )
    SELECT tmi.type_id, tmi.type_name, tmi.category, tmi.display_order,
           it.volume, it.portion_size, tm.materials_json, ms.best_buy
    FROM tracked_market_items tmi
    JOIN inv_types it ON it.type_id = tmi.type_id
    LEFT JOIN type_materials tm ON tm.type_id = tmi.type_id
    LEFT JOIN latest_mps ms ON ms.type_id = tmi.type_id
    WHERE tmi.category IN ('standard_ore','moon_ore','ice_ore')
      AND tmi.type_name LIKE 'Compressed %'
    ORDER BY tmi.category, tmi.display_order
""").fetchall()

all_mat_ids = set()
ore_rows_raw = []
for type_id, name, cat, disp, vol, ps, mats_json, buy in rows:
    mats = {}
    if mats_json:
        for m in json.loads(mats_json):
            mats[m['materialTypeID']] = m['quantity']
            all_mat_ids.add(m['materialTypeID'])
    ore_rows_raw.append((type_id, name, cat, disp, vol, ps, mats, buy or 0))

mat_ids_str = ','.join(str(x) for x in sorted(all_mat_ids))

# ── N-day averages for all ores and materials ─────────────────────────────
all_type_ids = set(r[0] for r in ore_rows_raw) | all_mat_ids
all_ids_str  = ','.join(str(x) for x in sorted(all_type_ids))
avg_rows = cur.execute(f"""
    SELECT type_id,
        AVG(CASE WHEN timestamp >= datetime('now','-7 days')  THEN best_buy END),
        AVG(CASE WHEN timestamp >= datetime('now','-14 days') THEN best_buy END),
        AVG(CASE WHEN timestamp >= datetime('now','-30 days') THEN best_buy END),
        AVG(CASE WHEN timestamp >= datetime('now','-60 days') THEN best_buy END)
    FROM market_price_snapshots
    WHERE type_id IN ({all_ids_str})
    GROUP BY type_id
""").fetchall()
avg_map = {r[0]: {'a7': r[1] or 0, 'a14': r[2] or 0, 'a30': r[3] or 0, 'a60': r[4] or 0} for r in avg_rows}

ores = []
for type_id, name, cat, disp, vol, ps, mats, buy in ore_rows_raw:
    short = name.replace('Compressed ', '')
    av = avg_map.get(type_id, {})
    ores.append({'id': type_id, 'name': short, 'cat': cat, 'vol': vol, 'ps': ps,
                 'mats': mats, 'mkt': buy,
                 'a7': av.get('a7',0), 'a14': av.get('a14',0),
                 'a30': av.get('a30',0), 'a60': av.get('a60',0)})

mat_rows = cur.execute(f"""
    WITH latest_mps AS (
        SELECT type_id, best_buy
        FROM market_price_snapshots
        WHERE type_id IN ({mat_ids_str})
          AND (type_id, timestamp) IN (
              SELECT type_id, MAX(timestamp) FROM market_price_snapshots
              WHERE type_id IN ({mat_ids_str}) GROUP BY type_id
          )
    )
    SELECT it.type_id, it.type_name, ms.best_buy
    FROM inv_types it
    LEFT JOIN latest_mps ms ON ms.type_id = it.type_id
    WHERE it.type_id IN ({mat_ids_str})
""").fetchall()
materials = {}
for r in mat_rows:
    av = avg_map.get(r[0], {})
    materials[r[0]] = {'name': r[1], 'jbv': r[2] or 0,
                       'a7': av.get('a7',0), 'a14': av.get('a14',0),
                       'a30': av.get('a30',0), 'a60': av.get('a60',0)}

snap_row = conn.execute("""
    SELECT MAX(timestamp) FROM market_price_snapshots ms
    JOIN tracked_market_items tmi ON tmi.type_id = ms.type_id
    WHERE tmi.category IN ('standard_ore','moon_ore','ice_ore')
      AND tmi.type_name LIKE 'Compressed %'
""").fetchone()
from datetime import datetime, timezone
snap_dt = datetime.fromisoformat(snap_row[0].replace('Z','+00:00')) if snap_row[0] else datetime.now(timezone.utc)
snap_label = snap_dt.strftime('%d %b %Y')

conn.close()

# ── Ore sub-group classification ─────────────────────────────────────────────
R4_MATS  = {16633, 16634, 16635, 16636}
R8_MATS  = {16637, 16638, 16639, 16640}
R16_MATS = {16641, 16642, 16643, 16644}
R32_MATS = {16646, 16647, 16648, 16649}
R64_MATS = {16650, 16651, 16652, 16653}

COMMON_ORE_NAMES    = ['Veldspar','Scordite','Pyroxeres','Plagioclase','Omber']
UNCOMMON_ORE_NAMES  = ['Kernite','Hedbergite','Hemorphite','Jaspet']
NULL_ORE_NAMES      = ['Gneiss','Dark Ochre','Spodumain','Arkonor','Bistot','Crokite','Mercoxit']

def std_subgroup(name):
    nl = name.lower()
    for o in COMMON_ORE_NAMES:
        if o.lower() in nl: return 'Common'
    for o in UNCOMMON_ORE_NAMES:
        if o.lower() in nl: return 'Uncommon'
    for o in NULL_ORE_NAMES:
        if o.lower() in nl: return 'Nullsec'
    return 'Pochven'

def moon_tier(ore):
    ids = set(int(k) for k in ore['mats'])
    if ids & R64_MATS: return 'R64'
    if ids & R32_MATS: return 'R32'
    if ids & R16_MATS: return 'R16'
    if ids & R8_MATS:  return 'R8'
    return 'R4'

# Assign sub-group to each ore entry
for ore in ores:
    if ore['cat'] == 'standard_ore':
        ore['sg'] = std_subgroup(ore['name'])
    elif ore['cat'] == 'moon_ore':
        ore['sg'] = moon_tier(ore)
    else:
        ore['sg'] = 'Ice'

# ── Material groups for the sell-% panel ─────────────────────────────────────
MAT_GROUPS = [
    ('Minerals',     [34,35,36,37,38,39,40,11399]),
    ('R4 Moon Mat',  [16633,16634,16635,16636]),
    ('R8 Moon Mat',  [16639,16640,16637,16638]),
    ('R16 Moon Mat', [16641,16642,16643,16644]),
    ('R32 Moon Mat', [16646,16647,16648,16649]),
    ('R64 Moon Mat', [16650,16651,16652,16653]),
    ('Ice Products', [16272,16273,16274,17887,17888,17889,16275]),
]

def mat_rows_html():
    lines = []
    for grp, ids in MAT_GROUPS:
        lines.append(f'<div class="mat-group-title">{grp}</div>')
        for mid in ids:
            if mid not in materials:
                continue
            mname = materials[mid]['name']
            price = materials[mid]['jbv']
            lines.append(
                f'<div class="mat-row">'
                f'<span class="mat-name">{mname}</span>'
                f'<input type="number" id="mp_{mid}" value="100" min="0" max="200" step="0.01" '
                f'oninput="recalcAll()" style="width:72px"> %'
                f'<span class="mat-price">{price:,.2f} ISK JBV</span>'
                f'</div>'
            )
    return '\n'.join(lines)

ores_js  = json.dumps(ores,  separators=(',',':'))
mats_js  = json.dumps({str(k): v for k, v in materials.items()}, separators=(',',':'))
mat_html = mat_rows_html()

# ── Build JS ore-options function body ──────────────────────────────────────
# We embed sub-group labels so the JS can build clean optgroups.
# Order: Standard Common → Uncommon → Nullsec → Pochven → Moon R4→R64 → Ice

STD_SUBGROUPS  = ['Common','Uncommon','Nullsec','Pochven']
MOON_SUBGROUPS = ['R4','R8','R16','R32','R64']

# Collect entries per group key so JS receives them in order
# Encode group key into each ore entry: already done via ore['sg']

# ── HTML ─────────────────────────────────────────────────────────────────────
html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ore Haul Calculator &mdash; Infinite Solutions</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;600;700&display=swap');
:root{
  --accent:#ff8833;--accent2:#ffcc44;--bg:#09090d;--panel:#0d1018;
  --panel2:#111520;--border:#1e2535;--border-o:rgba(255,140,50,0.2);
  --text:#d8e0f0;--dim:#5a6880;--green:#33dd88;--red:#ff5555;
  --gold:#ffd700;--blue:#44aaff;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;
  padding:20px 14px 48px;display:flex;justify-content:center;}
.page{width:100%;max-width:1120px;}
.hdr{text-align:center;margin-bottom:18px;}
.hdr h1{font-family:'Orbitron',sans-serif;font-size:1.5em;font-weight:900;letter-spacing:4px;
  background:linear-gradient(135deg,#ff9944,#ffcc44);-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;background-clip:text;}
.hdr .sub{color:var(--dim);font-size:.85em;letter-spacing:2px;text-transform:uppercase;margin-top:4px;}
.snap-pill{display:inline-block;margin-top:6px;background:rgba(255,140,50,.1);border:1px solid var(--border-o);
  border-radius:4px;padding:2px 12px;font-size:.78em;color:var(--accent);letter-spacing:1px;}
.back-link{display:inline-block;margin-bottom:12px;color:var(--dim);font-size:.85em;text-decoration:none;letter-spacing:1px;}
.back-link:hover{color:var(--text);}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px 20px;margin-bottom:12px;}
.panel-title{font-family:'Orbitron',sans-serif;font-size:.67em;font-weight:700;letter-spacing:2px;
  text-transform:uppercase;color:var(--accent);margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid var(--border-o);}
.form-row{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap;}
.form-row:last-child{margin-bottom:0;}
label{color:var(--dim);font-size:.9em;font-weight:600;letter-spacing:.5px;min-width:170px;flex-shrink:0;}
select,input[type="number"]{background:var(--panel2);border:1px solid var(--border);border-radius:4px;
  color:var(--text);font-family:'Rajdhani',sans-serif;font-size:.97em;font-weight:600;
  padding:5px 9px;outline:none;transition:border-color .15s;}
select:focus,input[type="number"]:focus{border-color:var(--accent);}
.unit{color:var(--dim);font-size:.87em;}
.iv{color:var(--accent2);font-weight:700;font-size:.93em;}
.collapse-btn{background:rgba(255,140,50,.08);border:1px solid var(--border-o);border-radius:4px;
  color:var(--accent);font-family:'Rajdhani',sans-serif;font-size:.88em;font-weight:700;
  padding:6px 14px;cursor:pointer;transition:all .12s;letter-spacing:1px;display:block;width:100%;}
.collapse-btn:hover{background:rgba(255,140,50,.18);}
.mat-panel{margin-top:10px;display:none;}
.mat-panel.open{display:block;}
.mat-group-title{grid-column:1/-1;font-family:'Orbitron',sans-serif;font-size:.62em;letter-spacing:2px;text-transform:uppercase;
  color:var(--accent);margin:14px 0 5px;padding:6px 10px 6px;
  background:rgba(255,140,50,.07);border:1px solid var(--border-o);border-radius:3px;}
.mat-group-title:first-child{margin-top:4px;}
.mat-rows-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:3px 20px;}
.mat-row{display:flex;align-items:center;gap:8px;padding:3px 0;}
.mat-name{color:var(--dim);font-size:.87em;min-width:165px;}
.mat-price{color:var(--dim);font-size:.76em;margin-left:4px;}
.qb{background:rgba(255,140,50,.1);border:1px solid var(--border-o);border-radius:4px;color:var(--dim);
  font-family:'Rajdhani',sans-serif;font-size:.83em;font-weight:700;padding:3px 8px;cursor:pointer;transition:all .12s;}
.qb:hover{background:rgba(255,140,50,.2);color:var(--text);}
.tbl-wrap{overflow-x:auto;}
table{width:100%;border-collapse:collapse;font-size:.88em;min-width:760px;}
thead th{background:var(--panel2);color:var(--dim);font-size:.72em;letter-spacing:1px;text-transform:uppercase;
  padding:8px 9px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap;}
tbody td{padding:6px 9px;border-bottom:1px solid var(--border);vertical-align:middle;}
tbody tr:last-child td{border-bottom:none;}
tbody tr:hover{background:rgba(255,255,255,.02);}
.td-ore select{min-width:210px;font-size:.86em;padding:4px 6px;}
.td-num input{width:88px;font-size:.86em;padding:4px 6px;}
.td-c{font-family:'Orbitron',sans-serif;font-size:.8em;font-weight:700;white-space:nowrap;}
.td-dim{color:var(--dim);font-size:.8em;font-family:'Rajdhani',sans-serif;font-weight:600;white-space:nowrap;}
.del-btn{background:rgba(255,60,60,.12);border:1px solid rgba(255,60,60,.25);border-radius:4px;
  color:#ff7777;cursor:pointer;font-size:.82em;font-weight:700;padding:2px 7px;transition:all .12s;}
.del-btn:hover{background:rgba(255,60,60,.28);}
.add-row-btn{background:rgba(255,140,50,.07);border:1px dashed var(--border-o);border-radius:4px;
  color:var(--accent);font-family:'Rajdhani',sans-serif;font-size:.88em;font-weight:700;
  padding:8px 0;cursor:pointer;width:100%;margin-top:7px;transition:all .12s;}
.add-row-btn:hover{background:rgba(255,140,50,.15);}
.sum-bar{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:9px;margin-top:12px;}
.sb{background:var(--panel2);border:1px solid var(--border);border-radius:6px;padding:10px 12px;text-align:center;}
.sb.profit{border-color:var(--border-o);background:rgba(255,140,50,.06);}
.sb-lbl{font-size:.7em;color:var(--dim);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}
.sb-val{font-family:'Orbitron',sans-serif;font-size:.95em;font-weight:700;}
.sb-val.green{color:var(--green);}.sb-val.red{color:var(--red);}
.sb-val.gold{color:var(--gold);}.sb-val.lg{font-size:1.2em;}
.sb-sub{font-size:.78em;color:var(--dim);margin-top:2px;}
.be-card{background:rgba(68,170,255,.04);border:1px solid rgba(68,170,255,.2);
  border-radius:6px;padding:12px 16px;margin-top:10px;}
.be-title{font-family:'Orbitron',sans-serif;font-size:.65em;letter-spacing:2px;
  text-transform:uppercase;color:var(--blue);margin-bottom:8px;}
.be-row{display:flex;justify-content:space-between;align-items:center;font-size:.9em;margin-bottom:3px;}
.be-lbl{color:var(--dim);}.be-val{font-family:'Orbitron',sans-serif;font-size:.85em;font-weight:700;}
.be-val.hi{color:var(--blue);}
hr.div{border:none;border-top:1px solid var(--border);margin:10px 0;}
.footer{text-align:center;color:var(--dim);font-size:.76em;margin-top:20px;
  padding-top:12px;border-top:1px solid var(--border);}
</style>
</head>
<body>
<div class="page">
<a class="back-link" href="index.html">&#8592; Industrial Market</a>
<div class="hdr">
  <h1>ORE HAUL CALCULATOR</h1>
  <div class="sub">Jump Freight &middot; Compressed Ore &middot; Refine Value</div>
  <div class="snap-pill" id="snap_pill">Jita prices: SNAP_DATE_PLACEHOLDER &nbsp;&middot;&nbsp; All entries are compressed variants</div>
</div>

<div class="panel">
  <div class="panel-title">Trip &amp; Refine Parameters</div>

  <div class="form-row">
    <label>Isotope Type</label>
    <select id="iso_type" onchange="recalcAll()" style="min-width:240px">
      <option value="642.30" selected>Nitrogen Isotopes &mdash; 642 ISK/unit</option>
      <option value="512.90">Hydrogen Isotopes &mdash; 513 ISK/unit</option>
      <option value="705.20">Oxygen Isotopes &mdash; 705 ISK/unit</option>
      <option value="725.30">Helium Isotopes &mdash; 725 ISK/unit</option>
    </select>
  </div>
  <div class="form-row">
    <label>Isotopes (round trip)</label>
    <input type="number" id="iso_qty" value="200000" min="0" step="10000" oninput="recalcAll()" style="width:120px">
    <span class="unit">units</span>
    <span class="iv" id="ship_tag">&mdash;</span>
  </div>
  <div class="form-row">
    <label>Price Basis</label>
    <select id="price_basis" onchange="recalcAll()" style="min-width:180px">
      <option value="latest">Latest Snapshot</option>
      <option value="avg7">7-Day Avg</option>
      <option value="avg14" selected>14-Day Avg</option>
      <option value="avg30">30-Day Avg</option>
      <option value="avg60">60-Day Avg</option>
    </select>
    <span class="unit" id="basis_note">&mdash;</span>
  </div>

  <hr class="div">

  <div class="form-row">
    <label>Buy % (pay miners)</label>
    <input type="number" id="buy_pct" min="0" max="100" step="0.01" value="90.00" oninput="recalcAll()" style="width:90px">
    <span class="unit">% of theoretical refine value</span>
  </div>
  <div class="form-row">
    <label>Refine Efficiency</label>
    <input type="number" id="eff_pct" min="0" max="100" step="0.01" value="87.50" oninput="recalcAll()" style="width:90px">
    <span class="unit">%</span>
  </div>
  <div class="form-row">
    <label>Refine Tax</label>
    <input type="number" id="tax_pct" min="0" max="20"  step="0.01" value="5.00"  oninput="recalcAll()" style="width:90px">
    <span class="unit">% of ore Jita value &nbsp; <span class="iv" id="eff_note">&mdash;</span></span>
  </div>

  <hr class="div">

  <button class="collapse-btn" onclick="toggleMat()" id="mat_btn">&#9658;&nbsp; Mineral &amp; Material Sell % &nbsp;&mdash;&nbsp; click to expand</button>
  <div class="mat-panel" id="mat_panel">
    <div style="display:flex;gap:8px;margin:8px 0;flex-wrap:wrap">
      <button class="qb" onclick="setAllMat(100)">Set All 100%</button>
      <button class="qb" onclick="setAllMat(95)">Set All 95%</button>
      <button class="qb" onclick="setAllMat(90)">Set All 90%</button>
    </div>
    <div class="mat-rows-grid">
MAT_HTML_PLACEHOLDER
    </div>
  </div>
</div>

<div class="panel">
  <div class="panel-title">Load Builder &mdash; Mixed Compressed Ore (all grades)</div>
  <div class="tbl-wrap">
  <table>
    <thead><tr>
      <th style="min-width:215px">Ore (Compressed)</th>
      <th>Quantity (units)</th>
      <th>Refine Val/m&#179;<br><span style="font-size:.85em;opacity:.6">after efficiency</span></th>
      <th id="mkt_col_hdr">Mkt JBV/m&#179;</th>
      <th>Load Ref. Value<br><span style="font-size:.85em;opacity:.6">pricing basis</span></th>
      <th>You Pay</th>
      <th>Net Contrib.</th>
      <th></th>
    </tr></thead>
    <tbody id="load_body"></tbody>
  </table>
  </div>
  <button class="add-row-btn" onclick="addRow()">+ Add Ore</button>

  <div class="sum-bar">
    <div class="sb"><div class="sb-lbl">Total Volume</div><div class="sb-val" id="s_vol">&mdash;</div></div>
    <div class="sb"><div class="sb-lbl">Load Ref. Value</div><div class="sb-val gold" id="s_load">&mdash;</div></div>
    <div class="sb"><div class="sb-lbl">You Pay Miners</div><div class="sb-val" id="s_pay">&mdash;</div></div>
    <div class="sb"><div class="sb-lbl">Refine Tax (ISK)</div><div class="sb-val red" id="s_tax">&mdash;</div><div class="sb-sub">% of ore Jita value</div></div>
    <div class="sb"><div class="sb-lbl">Shipping Cost</div><div class="sb-val" id="s_ship">&mdash;</div></div>
    <div class="sb"><div class="sb-lbl">Mineral Revenue<br><span style="font-size:.75em;color:var(--dim)">at efficiency %</span></div><div class="sb-val" id="s_rev">&mdash;</div></div>
    <div class="sb profit"><div class="sb-lbl">Net Profit</div><div class="sb-val lg" id="s_profit">&mdash;</div><div class="sb-sub" id="s_psub"></div></div>
  </div>

  <div class="be-card">
    <div class="be-title">Break-Even Analysis</div>
    <div id="be_rows"><div class="be-row"><span class="be-lbl">Add ore rows above to see break-even</span></div></div>
  </div>
</div>

<div class="footer">
  Prices: Jita 4-4 buy orders &middot; SNAP_DATE_PLACEHOLDER &middot; Infinite Solutions &middot; Hamektok Hakaari
</div>
</div>
<script>
const ORES = ORES_DATA_PLACEHOLDER;
const MATERIALS = MATS_DATA_PLACEHOLDER;

// ── Build ore dropdown with clean sub-group optgroups ──────────────────────
const STD_SG  = ['Common','Uncommon','Nullsec','Pochven'];
const MOON_SG = ['R4','R8','R16','R32','R64'];

function buildOreOptions(selIdx) {
  var groups = {};
  ORES.forEach(function(o,i) {
    var key = o.cat + '_' + o.sg;
    if (!groups[key]) groups[key] = {label: groupLabel(o.cat, o.sg), items:[]};
    groups[key].items.push({i:i, name:o.name});
  });
  // Ordered group keys
  var order = [];
  STD_SG.forEach(function(sg){ order.push('standard_ore_'+sg); });
  MOON_SG.forEach(function(sg){ order.push('moon_ore_'+sg); });
  order.push('ice_ore_Ice');

  var html = '';
  order.forEach(function(key) {
    var g = groups[key]; if (!g || g.items.length===0) return;
    html += '<optgroup label="' + g.label + '">';
    g.items.forEach(function(it){
      html += '<option value="'+it.i+'"'+(it.i===selIdx?' selected':'')+'>' + it.name + '</option>';
    });
    html += '</optgroup>';
  });
  return html;
}

function groupLabel(cat, sg) {
  if (cat === 'standard_ore') return 'Standard Ore \u2014 ' + sg;
  if (cat === 'moon_ore')     return 'Moon Ore \u2014 ' + sg;
  return 'Ice';
}

// ── Material sell % ────────────────────────────────────────────────────────
function matPct(mid) { var e=document.getElementById('mp_'+mid); return e?(parseFloat(e.value)||100):100; }
function setAllMat(v) { document.querySelectorAll('[id^="mp_"]').forEach(function(e){e.value=v;}); recalcAll(); }
function toggleMat() {
  var p=document.getElementById('mat_panel'), b=document.getElementById('mat_btn');
  p.classList.toggle('open');
  b.innerHTML=(p.classList.contains('open')?'&#9660;':'&#9658;')+'&nbsp; Mineral &amp; Material Sell % &nbsp;&mdash;&nbsp; click to '+(p.classList.contains('open')?'collapse':'expand');
  saveState();
}

// ── Persistence ────────────────────────────────────────────────────────────
var MAT_IDS=[34,35,36,37,38,39,40,11399,16633,16634,16635,16636,16639,16640,16637,16638,16641,16642,16643,16644,16646,16647,16648,16649,16650,16651,16652,16653,16272,16273,16274,17887,17888,17889,16275];
function saveState() {
  var s={};
  ['iso_type','iso_qty','buy_pct','eff_pct','tax_pct','price_basis'].forEach(function(id){
    var el=document.getElementById(id); if(el) s[id]=el.value;
  });
  MAT_IDS.forEach(function(mid){
    var el=document.getElementById('mp_'+mid); if(el) s['mp_'+mid]=el.value;
  });
  s.mat_open=document.getElementById('mat_panel').classList.contains('open');
  var rows=[];
  document.querySelectorAll('#load_body tr').forEach(function(tr){
    var sel=tr.querySelector('select'), inp=tr.querySelector('input');
    if(sel&&inp) rows.push({o:sel.value, v:inp.value});
  });
  s.rows=rows;
  try{ localStorage.setItem('ore_calc_state', JSON.stringify(s)); }catch(e){}
}
function loadState() {
  var raw; try{ raw=localStorage.getItem('ore_calc_state'); }catch(e){}
  if(!raw){ addRow(0,400000); return; }
  var s; try{ s=JSON.parse(raw); }catch(e){ addRow(0,400000); return; }
  ['iso_type','iso_qty','buy_pct','eff_pct','tax_pct','price_basis'].forEach(function(id){
    var el=document.getElementById(id); if(el&&s[id]!=null) el.value=s[id];
  });
  MAT_IDS.forEach(function(mid){
    var el=document.getElementById('mp_'+mid); if(el&&s['mp_'+mid]!=null) el.value=s['mp_'+mid];
  });
  if(s.mat_open){
    var p=document.getElementById('mat_panel'), b=document.getElementById('mat_btn');
    p.classList.add('open');
    b.innerHTML='&#9660;&nbsp; Mineral &amp; Material Sell % &nbsp;&mdash;&nbsp; click to collapse';
  }
  var rows=s.rows&&s.rows.length?s.rows:[{o:0,v:100000}];
  rows.forEach(function(r){ addRow(parseInt(r.o), parseFloat(r.v)); });
}

// ── Price basis helpers ────────────────────────────────────────────────────
var SNAP_DATE = 'SNAP_DATE_PLACEHOLDER';
var BASIS_LABELS = {
  latest: 'Latest snapshot: '+SNAP_DATE,
  avg7:   '7-day avg',
  avg14:  '14-day avg',
  avg30:  '30-day avg',
  avg60:  '60-day avg'
};
function getBasis() { return document.getElementById('price_basis').value; }
function orePrice(ore) {
  var b=getBasis();
  if(b==='avg7')  return ore.a7  || ore.mkt;
  if(b==='avg14') return ore.a14 || ore.mkt;
  if(b==='avg30') return ore.a30 || ore.mkt;
  if(b==='avg60') return ore.a60 || ore.mkt;
  return ore.mkt;
}
function matPrice(mat) {
  var b=getBasis();
  if(b==='avg7')  return mat.a7  || mat.jbv;
  if(b==='avg14') return mat.a14 || mat.jbv;
  if(b==='avg30') return mat.a30 || mat.jbv;
  if(b==='avg60') return mat.a60 || mat.jbv;
  return mat.jbv;
}
function updateBasisLabels() {
  var b=getBasis();
  var lbl=BASIS_LABELS[b]||b;
  var hdr=b==='latest'?'Mkt JBV/m\u00B3':(lbl+'/m\u00B3');
  var hdrEl=document.getElementById('mkt_col_hdr'); if(hdrEl) hdrEl.textContent=hdr;
  var pillEl=document.getElementById('snap_pill');
  if(pillEl) pillEl.innerHTML='Jita prices: '+lbl+' &nbsp;&middot;&nbsp; All entries are compressed variants';
  var noteEl=document.getElementById('basis_note'); if(noteEl) noteEl.textContent=lbl;
}

// ── Refine value calculations ──────────────────────────────────────────────
function refineVal100(ore) {
  // theoretical value at 100% efficiency, using selected price basis and sell%
  var val=0;
  for (var mid in ore.mats) {
    var mat=MATERIALS[mid]; if(!mat) continue;
    val += (ore.mats[mid]/ore.ps)*matPrice(mat)*(matPct(parseInt(mid))/100);
  }
  return val; // per unit
}

// ── Helpers ────────────────────────────────────────────────────────────────
function fmt(n,d){ d=d||0; return isFinite(n)?n.toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d}):'--'; }
function fmtB(n) {
  var a=Math.abs(n),s=n<0?'-':'';
  if(a>=1e9) return s+(a/1e9).toFixed(3)+'B';
  if(a>=1e6) return s+(a/1e6).toFixed(1)+'M';
  if(a>=1e3) return s+(a/1e3).toFixed(0)+'k';
  return s+fmt(a);
}
function getShip(){ return (parseFloat(document.getElementById('iso_qty').value)||0)*(parseFloat(document.getElementById('iso_type').value)||0); }
function getEff() { return parseFloat(document.getElementById('eff_pct').value)||87.5; }
function getTax() { return parseFloat(document.getElementById('tax_pct').value)||0; }
function getBuy() { return parseFloat(document.getElementById('buy_pct').value)||90; }

// ── Load Builder ───────────────────────────────────────────────────────────
var rowId=0;
function addRow(oreIdx,qty) {
  oreIdx=oreIdx||0; qty=qty!=null?qty:100000;
  var id=++rowId;
  var tr=document.createElement('tr'); tr.id='r'+id;
  tr.innerHTML=
    '<td class="td-ore"><select onchange="recalcAll()">'+buildOreOptions(oreIdx)+'</select></td>'+
    '<td style="white-space:nowrap"><input type="number" class="td-num-in" value="'+qty+'" min="0" step="1000" oninput="recalcAll()" style="width:100px"> <span class="td-dim" id="vol_'+id+'" style="font-size:.82em"></span></td>'+
    '<td class="td-dim" id="rv_'+id+'">--</td>'+
    '<td class="td-dim" id="mkt_'+id+'">--</td>'+
    '<td class="td-c"   id="lv_'+id+'">--</td>'+
    '<td class="td-c"   id="pay_'+id+'">--</td>'+
    '<td class="td-c"   id="con_'+id+'">--</td>'+
    '<td><button class="del-btn" onclick="delRow('+id+')">&#x2715;</button></td>';
  document.getElementById('load_body').appendChild(tr);
  recalcAll();
}
function delRow(id){ var e=document.getElementById('r'+id); if(e)e.remove(); recalcAll(); saveState(); }

function recalcAll() {
  var ship=getShip(), eff=getEff(), tax=getTax(), buy=getBuy();
  document.getElementById('ship_tag').textContent=fmtB(ship)+' ISK';
  document.getElementById('eff_note').textContent='Efficiency: '+eff.toFixed(2)+'%  \u00B7  Tax on Jita value: '+tax.toFixed(2)+'%';
  updateBasisLabels();

  var totVol=0, totLoad=0, totPay=0, totRev=0, totTax=0, totMkt=0;
  document.querySelectorAll('#load_body tr').forEach(function(tr){
    var id=tr.id.replace('r','');
    var sel=tr.querySelector('select');
    var inp=tr.querySelector('input');
    if(!sel||!inp) return;
    var ore=ORES[parseInt(sel.value)];
    var qty=parseFloat(inp.value)||0;
    if(!ore||qty<=0) return;
    var vol = qty * ore.vol;                   // m³ derived from units × vol/unit

    var volEl=document.getElementById('vol_'+id);
    if(volEl) volEl.textContent=fmt(vol,0)+' m\u00B3';

    var rv100    = refineVal100(ore);          // theoretical refine value per unit (selected basis)
    var rvEff    = rv100 * eff/100;            // mineral proceeds per unit (after efficiency, no tax deduction)
    var rv100_m3 = rv100  / ore.vol;
    var rvEff_m3 = rvEff  / ore.vol;
    var mkt_m3   = orePrice(ore) / ore.vol;   // selected basis price per m³

    var loadRef = vol * rv100_m3;             // pricing basis total
    var pay     = loadRef * buy/100;          // ISK paid to miners
    var revenue = vol * rvEff_m3;             // mineral proceeds after efficiency
    var taxIsk  = vol * mkt_m3 * tax/100;     // ISK tax charged against ore price
    var contrib = revenue - pay - taxIsk;     // net row contribution (before shipping)

    document.getElementById('rv_' +id).textContent=fmt(rvEff_m3)+' ISK';
    document.getElementById('mkt_'+id).textContent=fmt(mkt_m3)+' ISK';
    document.getElementById('lv_' +id).textContent=fmtB(loadRef);
    document.getElementById('pay_'+id).textContent=fmtB(pay);
    var cEl=document.getElementById('con_'+id);
    cEl.textContent=(contrib>=0?'+':'')+fmtB(contrib);
    cEl.style.color=contrib>=0?'var(--green)':'var(--red)';

    totVol  += vol;
    totLoad += loadRef;
    totPay  += pay;
    totRev  += revenue;
    totTax  += taxIsk;
    totMkt  += vol * mkt_m3;
  });

  var profit = totRev - totPay - totTax - ship;
  var totalCost = totPay + totTax + ship;
  var roc = totalCost > 0 ? profit/totalCost*100 : 0;

  document.getElementById('s_vol').textContent  = fmt(totVol)+' m\u00B3';
  document.getElementById('s_load').textContent = fmtB(totLoad);
  document.getElementById('s_pay').textContent  = fmtB(totPay);
  document.getElementById('s_tax').textContent  = '\u2212'+fmtB(totTax);
  document.getElementById('s_ship').textContent = fmtB(ship);
  document.getElementById('s_rev').textContent  = fmtB(totRev);
  var pEl=document.getElementById('s_profit');
  pEl.textContent=(profit>=0?'+':'')+fmtB(profit);
  pEl.className='sb-val lg '+(profit>=0?'green':'red');
  document.getElementById('s_psub').textContent=
    profit>=0 ? roc.toFixed(1)+'% ROC  \u00B7  '+fmt(profit/Math.max(totVol,1))+' ISK/m\u00B3'
              : 'Loss at these parameters';

  // Break-even
  var beEl=document.getElementById('be_rows');
  if(totLoad>0){
    var blendBuy   = totPay/totLoad*100;
    var taxPctLoad = totMkt>0 ? (totTax/totLoad*100) : 0;  // effective tax as % of load value
    var effPct     = eff;                                   // mineral revenue as % of load value
    var marginPct  = effPct - blendBuy - taxPctLoad;
    var h='';
    h+='<div class="be-row"><span class="be-lbl">Blended buy % (value-weighted)</span><span class="be-val hi">'+blendBuy.toFixed(2)+'%</span></div>';
    h+='<div class="be-row"><span class="be-lbl">Mineral revenue as % of load value (eff)</span><span class="be-val">'+effPct.toFixed(2)+'%</span></div>';
    h+='<div class="be-row"><span class="be-lbl">Tax cost as % of load value</span><span class="be-val">'+taxPctLoad.toFixed(2)+'%</span></div>';
    if(marginPct>0){
      var beLoad=ship/(marginPct/100);
      h+='<div class="be-row"><span class="be-lbl">Net margin (eff \u2212 buy \u2212 tax%)</span><span class="be-val">'+marginPct.toFixed(2)+'%</span></div>';
      h+='<div class="be-row"><span class="be-lbl">Min load value to cover shipping</span><span class="be-val hi">'+fmtB(beLoad)+' ISK</span></div>';
      h+='<div class="be-row"><span class="be-lbl">Shipping as % of current load value</span><span class="be-val">'+(ship/totLoad*100).toFixed(2)+'%</span></div>';
    } else {
      h+='<div class="be-row"><span class="be-lbl" style="color:var(--red)">No margin after buy % + tax \u2014 cannot cover shipping</span></div>';
    }
    beEl.innerHTML=h;
  } else {
    beEl.innerHTML='<div class="be-row"><span class="be-lbl">Add ore rows above to see break-even</span></div>';
  }
  saveState();
}

loadState();
</script>
</body>
</html>"""

html = html.replace('MAT_HTML_PLACEHOLDER', mat_html)
html = html.replace('ORES_DATA_PLACEHOLDER', ores_js)
html = html.replace('MATS_DATA_PLACEHOLDER', mats_js)
html = html.replace('SNAP_DATE_PLACEHOLDER', snap_label)

with open('ore_haul_calculator.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Done. {len(ores)} ores, {len(materials)} materials.")
