"""
Build haul_calculator.html — standalone jump-freight hauling fee calculator.
Same visual design as ore_haul_calculator.html.
No DB queries required: only needs the Vale systems list and isotope prices.
"""
import json
from datetime import datetime, timezone

# ── Vale of the Silent systems with LY distance from 4-HWWF ─────────────────
VALE_SYSTEMS = [
    ('4-HWWF', 0),     ('PM-DWE', 0.893), ('4GYV-Q', 0.937), ('EIDI-N', 1.023),
    ('YMJG-4', 1.136), ('DAYP-G', 1.356), ('WBR5-R', 1.443), ('8TPX-N', 1.491),
    ('KRUN-N', 1.499), ('TVN-FM', 1.502), ('IPAY-2', 1.577), ('K8X-6B', 1.72),
    ('0MV-4W', 1.927), ('AZBR-2', 2.03),  ('Q-L07F', 2.198), ('U54-1L', 2.247),
    ('P3EN-E', 2.278), ('T-GCGL', 2.44),  ('V-OJEN', 2.469), ('X445-5', 2.533),
    ('05R-7A', 2.559), ('FS-RFL', 2.619), ('NCGR-Q', 2.658), ('Z-8Q65', 2.7),
    ('IFJ-EL', 2.748), ('9OO-LH', 2.759), ('MC6O-F', 2.774), ('X97D-W', 2.799),
    ('49-0LI', 2.815), ('0-R5TS', 2.844), ('669-IX', 2.888), ('0R-F2F', 3.002),
    ('47L-J4', 3.07),  ('N-HSK0', 3.163), ('HE-V4V', 3.182), ('V-NL3K', 3.223),
    ('0J3L-V', 3.232), ('S-NJBB', 3.307), ('XF-PWO', 3.361), ('R-P7KL', 3.37),
    ('A8A-JN', 3.386), ('NFM-0V', 3.389), ('E-D0VZ', 3.401), ('6WW-28', 3.432),
    ('UH-9ZG', 3.448), ('YXIB-I', 3.497), ('LZ-6SU', 3.503), ('Y0-BVN', 3.631),
    ('7-UH4Z', 3.631), ('1N-FJ8', 3.718), ('2DWM-2', 3.732), ('H-UCD1', 3.802),
    ('G-LOIT', 3.828), ('1-GBBP', 3.837), ('B-588R', 3.905), ('5ZO-NZ', 4.132),
    ('H-NOU5', 4.337), ('97-M96', 4.356), ('T-ZWA1', 4.379), ('3HX-DL', 4.409),
    ('7-K5EL', 4.429), ('KX-2UI', 4.579), ('GEKJ-9', 4.62),  ('MY-T2P', 4.817),
    ('Y-ZXIO', 4.827), ('C-FP70', 4.899), ('G96R-F', 5.079), ('Q-R3GP', 5.081),
    ('ZA0L-U', 5.118), ('FA-DMO', 5.257), ('XV-8JQ', 5.341), ('N-5QPW', 5.528),
    ('MO-FIF', 5.566), ('MA-XAP', 5.716), ('H-5GUI', 5.717), ('C-J7CR', 5.852),
    ('Q-EHMJ', 5.941), ('XSQ-TF', 6.193), ('H-1EOH', 6.423), ('FMBR-8', 6.451),
    ('FH-TTC', 6.633), ('VI2K-J', 6.669), ('6Y-WRK', 6.755), ('5T-KM3', 6.789),
    ('IR-DYY', 6.818), ('MQ-O27', 7.129), ('ZLZ-1Z', 7.348), ('F-D49D', 7.382),
    ('RVCZ-C', 7.422), ('B-E3KQ', 7.87),  ('Y5J-EU', 7.899), ('H-EY0P', 8.008),
    ('O-LR1H', 8.088), ('LS9B-9', 8.17),  ('C-DHON', 8.317), ('G5ED-Y', 8.656),
    ('UNAG-6', 8.692), ('A-QRQT', 8.849), ('8-TFDX', 9.072), ('BR-6XP', 9.092),
    ('E-SCTX', 9.276), ('7-PO3P', 9.281), ('WMBZ-U', 9.319), ('UL-4ZW', 9.656),
    ('VORM-W', 9.73),
]

systems_js = json.dumps([{'name': s[0], 'ly': s[1]} for s in VALE_SYSTEMS], separators=(',', ':'))
systems_options = '\n'.join(
    f'      <option value="{i}">{s[0]} &mdash; {s[1]:.3f} ly</option>'
    for i, s in enumerate(VALE_SYSTEMS)
)

build_date = datetime.now(timezone.utc).strftime('%d %b %Y')

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Haul Calculator &mdash; Infinite Solutions</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;600;700&display=swap');
:root{{
  --accent:#ff8833;--accent2:#ffcc44;--bg:#09090d;--panel:#0d1018;
  --panel2:#111520;--border:#1e2535;--border-o:rgba(255,140,50,0.2);
  --text:#d8e0f0;--dim:#5a6880;--green:#33dd88;--red:#ff5555;
  --gold:#ffd700;--blue:#44aaff;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;
  padding:20px 14px 48px;display:flex;justify-content:center;}}
.page{{width:100%;max-width:900px;}}
.hdr{{text-align:center;margin-bottom:18px;}}
.hdr h1{{font-family:'Orbitron',sans-serif;font-size:1.5em;font-weight:900;letter-spacing:4px;
  background:linear-gradient(135deg,#ff9944,#ffcc44);-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;background-clip:text;}}
.hdr .sub{{color:var(--dim);font-size:.85em;letter-spacing:2px;text-transform:uppercase;margin-top:4px;}}
.back-link{{display:inline-block;margin-bottom:12px;color:var(--dim);font-size:.85em;text-decoration:none;letter-spacing:1px;}}
.back-link:hover{{color:var(--text);}}
.panel{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px 20px;margin-bottom:12px;}}
.panel-title{{font-family:'Orbitron',sans-serif;font-size:.67em;font-weight:700;letter-spacing:2px;
  text-transform:uppercase;color:var(--accent);margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid var(--border-o);}}
.form-row{{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap;}}
.form-row:last-child{{margin-bottom:0;}}
label{{color:var(--dim);font-size:.9em;font-weight:600;letter-spacing:.5px;min-width:170px;flex-shrink:0;}}
select,input[type="number"]{{background:var(--panel2);border:1px solid var(--border);border-radius:4px;
  color:var(--text);font-family:'Rajdhani',sans-serif;font-size:.97em;font-weight:600;
  padding:5px 9px;outline:none;transition:border-color .15s;}}
select:focus,input[type="number"]:focus{{border-color:var(--accent);}}
.unit{{color:var(--dim);font-size:.87em;}}
.iv{{color:var(--accent2);font-weight:700;font-size:.93em;}}
hr.div{{border:none;border-top:1px solid var(--border);margin:10px 0;}}
.tbl-wrap{{overflow-x:auto;}}
table{{width:100%;border-collapse:collapse;font-size:.88em;}}
thead th{{background:var(--panel2);color:var(--dim);font-size:.72em;letter-spacing:1px;text-transform:uppercase;
  padding:8px 9px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap;}}
tbody td{{padding:6px 9px;border-bottom:1px solid var(--border);vertical-align:middle;}}
tbody tr:last-child td{{border-bottom:none;}}
tbody tr:hover{{background:rgba(255,255,255,.02);}}
.td-num input{{width:100px;font-size:.86em;padding:4px 6px;}}
.td-name input{{min-width:200px;font-size:.86em;padding:4px 6px;background:var(--panel2);
  border:1px solid var(--border);border-radius:4px;color:var(--text);
  font-family:'Rajdhani',sans-serif;font-weight:600;outline:none;}}
.td-name input:focus{{border-color:var(--accent);}}
.td-c{{font-family:'Orbitron',sans-serif;font-size:.8em;font-weight:700;white-space:nowrap;}}
.td-dim{{color:var(--dim);font-size:.8em;font-family:'Rajdhani',sans-serif;font-weight:600;white-space:nowrap;}}
.del-btn{{background:rgba(255,60,60,.12);border:1px solid rgba(255,60,60,.25);border-radius:4px;
  color:#ff7777;cursor:pointer;font-size:.82em;font-weight:700;padding:2px 7px;transition:all .12s;}}
.del-btn:hover{{background:rgba(255,60,60,.28);}}
.add-row-btn{{background:rgba(255,140,50,.07);border:1px dashed var(--border-o);border-radius:4px;
  color:var(--accent);font-family:'Rajdhani',sans-serif;font-size:.88em;font-weight:700;
  padding:8px 0;cursor:pointer;width:100%;margin-top:7px;transition:all .12s;}}
.add-row-btn:hover{{background:rgba(255,140,50,.15);}}
.sum-bar{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:12px;}}
.sb{{background:var(--panel2);border:1px solid var(--border);border-radius:6px;padding:8px 6px;text-align:center;}}
.sb.profit{{border-color:var(--border-o);background:rgba(255,140,50,.06);}}
.sb-lbl{{font-size:.65em;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;}}
.sb-val{{font-family:'Orbitron',sans-serif;font-size:.88em;font-weight:700;}}
.sb-val.green{{color:var(--green);}}.sb-val.gold{{color:var(--gold);}}.sb-val.lg{{font-size:1.2em;}}
.sb-sub{{font-size:.78em;color:var(--dim);margin-top:2px;}}
.footer{{text-align:center;color:var(--dim);font-size:.76em;margin-top:20px;
  padding-top:12px;border-top:1px solid var(--border);}}
.import-row{{display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap;margin-bottom:8px;}}
.import-row textarea{{flex:1;min-width:200px;background:var(--panel2);border:1px solid var(--border);
  border-radius:4px;color:var(--text);font-family:'Rajdhani',sans-serif;font-size:.93em;
  padding:7px 10px;resize:vertical;min-height:60px;outline:none;}}
.import-row textarea:focus{{border-color:var(--accent);}}
.import-btn{{background:rgba(255,140,50,.12);border:1px solid var(--border-o);border-radius:4px;
  color:var(--accent);font-family:'Rajdhani',sans-serif;font-size:.9em;font-weight:700;
  padding:8px 18px;cursor:pointer;white-space:nowrap;transition:all .12s;align-self:flex-start;}}
.import-btn:hover{{background:rgba(255,140,50,.25);}}
.import-status{{font-size:.83em;margin-top:4px;min-height:1.2em;}}
.import-status.ok{{color:var(--green);}}.import-status.err{{color:var(--red);}}
</style>
</head>
<body>
<div class="page">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
  <a class="back-link" style="margin-bottom:0" href="index.html">&#8592; Industrial Market</a>
  <a class="back-link" style="margin-bottom:0" href="ore_haul_calculator.html">Ore Haul Calculator &#8594;</a>
</div>
<div class="hdr">
  <h1>HAUL CALCULATOR</h1>
  <div class="sub">Jump Freight &middot; Vale of the Silent &middot; 4-HWWF Central</div>
</div>

<div class="panel">
  <div class="panel-title">Trip Parameters</div>

  <div class="form-row">
    <label>Pickup System</label>
    <select id="sys_sel" onchange="recalc()" style="min-width:200px">
{systems_options}
    </select>
    <span class="unit" id="sys_dist_note">&mdash;</span>
  </div>
  <div class="form-row">
    <label>Trip</label>
    <select id="trip_type" onchange="recalc()" style="min-width:140px">
      <option value="one">One-way</option>
      <option value="round" selected>Round-trip</option>
    </select>
  </div>
  <div class="form-row">
    <label>Isotope Type</label>
    <select id="iso_type" onchange="recalc()" style="min-width:260px">
      <option value="642.30" selected>Nitrogen Isotopes &mdash; 642 ISK/unit</option>
      <option value="512.90">Hydrogen Isotopes &mdash; 513 ISK/unit</option>
      <option value="705.20">Oxygen Isotopes &mdash; 705 ISK/unit</option>
      <option value="725.30">Helium Isotopes &mdash; 725 ISK/unit</option>
    </select>
  </div>
  <div class="form-row">
    <label>Fuel per LY</label>
    <input type="number" id="fuel_per_ly" value="0" min="0" step="100" oninput="recalc()" style="width:110px">
    <span class="unit">isotopes/LY</span>
    <span class="iv" id="iso_calc_note">&mdash;</span>
  </div>

  <hr class="div">

  <div class="form-row">
    <label>Flat Markup</label>
    <input type="number" id="fee_flat" min="0" step="1" value="0" oninput="recalc()" style="width:110px">
    <span class="unit">ISK/m&#179; &nbsp;<span style="font-size:.8em">(added on top of fuel recovery)</span></span>
  </div>

  <div class="form-row">
    <label>Ship Capacity</label>
    <input type="number" id="ship_cap" min="0" step="1000" value="0" oninput="recalc()" style="width:120px">
    <span class="unit">m&#179; &nbsp;<span style="font-size:.8em">(optional — used to show trips needed)</span></span>
  </div>
</div>

<div class="panel">
  <div class="panel-title">Import Cargo List</div>
  <div class="import-row">
    <textarea id="import_text" placeholder="Paste item list from EVE (one item per line):&#10;Compressed Hezorime&#9;6000000&#10;Veldspar&#9;1000000&#10;Or just a total volume in m&#179;"></textarea>
    <div style="display:flex;flex-direction:column;gap:6px">
      <button class="import-btn" onclick="doImport()">&#9654; Import</button>
      <button class="import-btn" style="background:rgba(255,60,60,.1);border-color:rgba(255,60,60,.3);color:#ff7777" onclick="clearLoad()">&#x2715; Clear</button>
    </div>
  </div>
  <div id="import_status" class="import-status"></div>
</div>

<div class="panel">
  <div class="panel-title">Cargo &mdash; Enter Items &amp; Volumes</div>
  <div class="tbl-wrap">
  <table>
    <thead><tr>
      <th style="min-width:220px">Item / Description</th>
      <th style="min-width:120px">Volume (m&#179;)</th>
      <th style="min-width:130px">Fuel Cost</th>
      <th style="min-width:110px">Fee (incl. markup)</th>
      <th></th>
    </tr></thead>
    <tbody id="load_body"></tbody>
  </table>
  </div>
  <button class="add-row-btn" onclick="addRow()">+ Add Cargo</button>

  <div class="sum-bar">
    <div class="sb"><div class="sb-lbl">Total Volume</div><div class="sb-val gold" id="s_vol">&mdash;</div><div class="sb-sub" id="s_trips">&nbsp;</div></div>
    <div class="sb"><div class="sb-lbl">Isotopes Used</div><div class="sb-val" id="s_iso">&mdash;</div><div class="sb-sub" id="s_iso_sub">&nbsp;</div></div>
    <div class="sb"><div class="sb-lbl">Fuel Cost (ISK)</div><div class="sb-val" id="s_fuel">&mdash;</div><div class="sb-sub" id="s_rate_sub">&nbsp;</div></div>
    <div class="sb profit"><div class="sb-lbl">Total Fee to Charge</div><div class="sb-val lg green" id="s_fee">&mdash;</div><div class="sb-sub" id="s_fee_sub">&nbsp;</div></div>
  </div>
</div>

<div class="footer">
  Infinite Solutions &middot; Hamektok Hakaari &middot; {build_date}
</div>
</div>
<script>
const SYSTEMS = {systems_js};

var rowId = 0;

function addRow(name, vol) {{
  name = name || '';
  vol  = vol  != null ? vol : 0;
  var id = ++rowId;
  var tr = document.createElement('tr');
  tr.id = 'row_'+id;
  tr.innerHTML =
    '<td class="td-name"><input type="text" id="rn_'+id+'" value="'+escHtml(name)+'" placeholder="Item name (optional)" oninput="recalc();saveState()"></td>' +
    '<td class="td-num"><input type="number" id="rv_'+id+'" value="'+vol+'" min="0" step="1" oninput="recalc();saveState()"></td>' +
    '<td class="td-c" id="rc_'+id+'">&mdash;</td>' +
    '<td class="td-c" id="rf_'+id+'">&mdash;</td>' +
    '<td><button class="del-btn" onclick="delRow('+id+')">&#x2715;</button></td>';
  document.getElementById('load_body').appendChild(tr);
  recalc();
  saveState();
}}

function delRow(id) {{
  var tr = document.getElementById('row_'+id);
  if (tr) tr.remove();
  recalc();
  saveState();
}}

function clearLoad() {{
  document.getElementById('load_body').innerHTML = '';
  rowId = 0;
  addRow();
  document.getElementById('import_status').textContent = '';
  saveState();
}}

function escHtml(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function fmt(n,d) {{ d=d||0; return isFinite(n)?n.toLocaleString(undefined,{{minimumFractionDigits:d,maximumFractionDigits:d}}):'\u2014'; }}
function fmtB(n) {{
  var a=Math.abs(n),s=n<0?'-':'';
  if(a>=1e9) return s+(a/1e9).toFixed(3)+'B';
  if(a>=1e6) return s+(a/1e6).toFixed(1)+'M';
  if(a>=1e3) return s+(a/1e3).toFixed(0)+'k';
  return s+fmt(a);
}}

function getSysLy() {{
  var idx = parseInt(document.getElementById('sys_sel').value)||0;
  return SYSTEMS[idx] ? SYSTEMS[idx].ly : 0;
}}
function getIsoQty() {{
  var ly   = getSysLy();
  var fpl  = parseFloat(document.getElementById('fuel_per_ly').value)||0;
  var mult = document.getElementById('trip_type').value === 'round' ? 2 : 1;
  return ly * fpl * mult;
}}
function getTotalFuelCost() {{
  return getIsoQty() * (parseFloat(document.getElementById('iso_type').value)||0);
}}

function recalc() {{
  var isoQty    = getIsoQty();
  var fuelCost  = getTotalFuelCost();
  var flatPerM3 = parseFloat(document.getElementById('fee_flat').value)||0;
  var shipCap   = parseFloat(document.getElementById('ship_cap').value)||0;

  // Collect rows
  var rows = [];
  document.querySelectorAll('#load_body tr').forEach(function(tr) {{
    var id  = tr.id.replace('row_','');
    var vol = parseFloat(document.getElementById('rv_'+id).value)||0;
    rows.push({{id:id, vol:vol}});
  }});

  var totalVol = rows.reduce(function(s,r){{return s+r.vol;}},0);

  // Fuel cost per m³ based on total load
  var fuelPerM3 = totalVol > 0 ? fuelCost / totalVol : 0;
  var feePerM3  = fuelPerM3 + flatPerM3;

  // Update each row
  rows.forEach(function(r) {{
    var rowFuel = fuelPerM3 * r.vol;
    var rowFee  = feePerM3  * r.vol;
    var cel = document.getElementById('rc_'+r.id);
    var fel = document.getElementById('rf_'+r.id);
    if(cel) cel.textContent = r.vol > 0 ? fmtB(rowFuel)+' ISK' : '\u2014';
    if(fel) fel.textContent = r.vol > 0 ? fmtB(rowFee)+' ISK'  : '\u2014';
  }});

  // System distance note
  var ly = getSysLy();
  var distNote = document.getElementById('sys_dist_note');
  if(distNote) distNote.textContent = ly > 0 ? ly.toFixed(3)+' ly from 4-HWWF' : '4-HWWF (hub)';

  // Isotope calc note
  var isoNote = document.getElementById('iso_calc_note');
  if(isoNote) isoNote.textContent = isoQty > 0 ? fmt(Math.round(isoQty))+' isotopes' : '\u2014';

  // Summary bar
  var totalFee = feePerM3 * totalVol;

  var trips = (shipCap > 0 && totalVol > 0) ? Math.ceil(totalVol / shipCap) : 0;
  var tripsEl = document.getElementById('s_trips');
  if(tripsEl) tripsEl.textContent = trips > 0 ? trips+' trip'+(trips>1?'s':'')+' @ '+fmt(shipCap)+' m\u00B3' : '';

  document.getElementById('s_vol').textContent  = fmt(Math.round(totalVol))+' m\u00B3';
  document.getElementById('s_iso').textContent  = isoQty > 0 ? fmt(Math.round(isoQty)) : '\u2014';
  document.getElementById('s_iso_sub').textContent = isoQty > 0 ? fmtB(fuelCost)+' ISK total' : '';
  document.getElementById('s_fuel').textContent = totalVol > 0 ? fmtB(fuelCost)+' ISK' : '\u2014';
  document.getElementById('s_rate_sub').textContent = fuelPerM3 > 0 ? fmtB(fuelPerM3)+' ISK/m\u00B3' : '';
  document.getElementById('s_fee').textContent  = totalVol > 0 ? fmtB(totalFee)+' ISK' : '\u2014';
  document.getElementById('s_fee_sub').textContent  = feePerM3 > 0 ? fmt(feePerM3,2)+' ISK/m\u00B3' : '';

  saveState();
}}

// ── Import parser ─────────────────────────────────────────────────────────
function doImport() {{
  var raw = document.getElementById('import_text').value.trim();
  var statusEl = document.getElementById('import_status');
  if (!raw) {{ statusEl.className='import-status err'; statusEl.textContent='Nothing to import.'; return; }}

  var items = [];
  raw.split('\\n').forEach(function(line) {{
    line = line.trim();
    if (!line) return;
    // Tab-separated EVE format: Name<TAB>Qty<TAB>...
    var parts = line.split('\\t');
    if (parts.length >= 2) {{
      var name = parts[0].trim();
      var qty  = parts[1].replace(/,/g,'').trim();
      if (name) items.push({{name: name, qty: qty}});
    }} else {{
      // Free-form: just a name or name + number
      var m = line.match(/^(.+?)\\s+([0-9,]+)$/);
      if (m) items.push({{name: m[1].trim(), qty: m[2].replace(/,/g,'')}});
      else items.push({{name: line, qty: '0'}});
    }}
  }});

  if (!items.length) {{
    statusEl.className='import-status err';
    statusEl.textContent='Could not parse any items.';
    return;
  }}

  // Clear existing rows
  document.getElementById('load_body').innerHTML = '';
  rowId = 0;
  items.forEach(function(it) {{
    addRow(it.name, parseFloat(it.qty)||0);
  }});

  statusEl.className='import-status ok';
  statusEl.textContent='Imported '+items.length+' item'+(items.length>1?'s':'')+'. Enter volumes in m\u00B3 for each row.';
  document.getElementById('import_text').value = '';
  recalc();
}}

// ── Persistence ──────────────────────────────────────────────────────────
function saveState() {{
  var s = {{}};
  ['sys_sel','trip_type','iso_type','fuel_per_ly','fee_flat','ship_cap'].forEach(function(id) {{
    var el = document.getElementById(id); if(el) s[id] = el.value;
  }});
  var rows = [];
  document.querySelectorAll('#load_body tr').forEach(function(tr) {{
    var id  = tr.id.replace('row_','');
    var nel = document.getElementById('rn_'+id);
    var vel = document.getElementById('rv_'+id);
    if(vel) rows.push({{n: nel?nel.value:'', v: vel.value}});
  }});
  s.rows = rows;
  try{{ localStorage.setItem('haul_calc_state', JSON.stringify(s)); }}catch(e){{}}
}}

function loadState() {{
  var raw; try{{ raw = localStorage.getItem('haul_calc_state'); }}catch(e){{}}
  if (!raw) {{ addRow('',0); return; }}
  var s; try{{ s = JSON.parse(raw); }}catch(e){{ addRow('',0); return; }}
  ['sys_sel','trip_type','iso_type','fuel_per_ly','fee_flat','ship_cap'].forEach(function(id) {{
    var el = document.getElementById(id); if(el && s[id] != null) el.value = s[id];
  }});
  var rows = s.rows && s.rows.length ? s.rows : [{{n:'',v:0}}];
  rows.forEach(function(r) {{ addRow(r.n, parseFloat(r.v)||0); }});
  recalc();
}}

window.onload = loadState;
</script>
</body>
</html>"""

out_path = 'haul_calculator.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Done. Written to {out_path}")
print(f"  Systems: {len(VALE_SYSTEMS)}")
