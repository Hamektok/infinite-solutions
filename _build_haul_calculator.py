"""
Build haul_calculator.html — jump-freight admin fee calculator.
Admin sets trip parameters; inputs are volume (m³) and collateral (ISK).
Fee = (fuel recovery/m³ + flat markup/m³) × volume + collateral% × collateral
"""
import json
from datetime import datetime, timezone

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
.page{{width:100%;max-width:780px;}}
.hdr{{text-align:center;margin-bottom:18px;}}
.hdr h1{{font-family:'Orbitron',sans-serif;font-size:1.5em;font-weight:900;letter-spacing:4px;
  background:linear-gradient(135deg,#ff9944,#ffcc44);-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;background-clip:text;}}
.hdr .sub{{color:var(--dim);font-size:.85em;letter-spacing:2px;text-transform:uppercase;margin-top:4px;}}
.back-link{{display:inline-block;color:var(--dim);font-size:.85em;text-decoration:none;letter-spacing:1px;}}
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
hr.div{{border:none;border-top:1px solid var(--border);margin:12px 0;}}
.sum-bar{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:4px;}}
.sb{{background:var(--panel2);border:1px solid var(--border);border-radius:6px;padding:10px 8px;text-align:center;}}
.sb.hi{{border-color:var(--border-o);background:rgba(255,140,50,.06);}}
.sb-lbl{{font-size:.65em;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;}}
.sb-val{{font-family:'Orbitron',sans-serif;font-size:.88em;font-weight:700;}}
.sb-val.green{{color:var(--green);}}.sb-val.gold{{color:var(--gold);}}.sb-val.lg{{font-size:1.15em;}}
.sb-sub{{font-size:.78em;color:var(--dim);margin-top:3px;}}
.be-card{{background:rgba(68,170,255,.04);border:1px solid rgba(68,170,255,.18);
  border-radius:6px;padding:12px 16px;margin-top:10px;}}
.be-title{{font-family:'Orbitron',sans-serif;font-size:.63em;letter-spacing:2px;
  text-transform:uppercase;color:var(--blue);margin-bottom:8px;}}
.be-row{{display:flex;justify-content:space-between;align-items:center;font-size:.9em;margin-bottom:4px;}}
.be-row:last-child{{margin-bottom:0;}}
.be-lbl{{color:var(--dim);}}
.be-val{{font-family:'Orbitron',sans-serif;font-size:.85em;font-weight:700;color:var(--text);}}
.be-val.hi{{color:var(--blue);}}.be-val.green{{color:var(--green);}}.be-val.gold{{color:var(--gold);}}
.footer{{text-align:center;color:var(--dim);font-size:.76em;margin-top:20px;
  padding-top:12px;border-top:1px solid var(--border);}}
</style>
</head>
<body>
<div class="page">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
  <a class="back-link" href="index.html">&#8592; Industrial Market</a>
  <a class="back-link" href="ore_haul_calculator.html">Ore Haul Calculator &#8594;</a>
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
    <span class="iv" id="sys_dist_note">&mdash;</span>
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
    <span class="unit">isotopes / LY &nbsp;&nbsp;</span>
    <span class="iv" id="iso_calc_note">&mdash;</span>
  </div>

  <hr class="div">

  <div class="form-row">
    <label>Flat Markup</label>
    <input type="number" id="fee_flat" min="0" step="1" value="0" oninput="recalc()" style="width:110px">
    <span class="unit">ISK / m&#179; &nbsp;<span style="font-size:.82em">(on top of fuel recovery)</span></span>
  </div>
  <div class="form-row">
    <label>Collateral Fee</label>
    <input type="number" id="coll_pct" min="0" max="10" step="0.01" value="0" oninput="recalc()" style="width:90px">
    <span class="unit">% of collateral</span>
  </div>
  <div class="form-row">
    <label>Ship Capacity</label>
    <input type="number" id="ship_cap" min="0" step="1000" value="0" oninput="recalc()" style="width:120px">
    <span class="unit">m&#179; &nbsp;<span style="font-size:.82em">(optional &mdash; shows trips needed)</span></span>
  </div>
</div>

<div class="panel">
  <div class="panel-title">Cargo</div>
  <div class="form-row">
    <label>Volume</label>
    <input type="number" id="cargo_vol" min="0" step="1" value="0" oninput="recalc()" style="width:150px">
    <span class="unit">m&#179;</span>
  </div>
  <div class="form-row">
    <label>Collateral</label>
    <input type="number" id="cargo_coll" min="0" step="1000000" value="0" oninput="recalc()" style="width:180px">
    <span class="unit">ISK</span>
  </div>

  <hr class="div">

  <div class="sum-bar">
    <div class="sb">
      <div class="sb-lbl">Isotopes Used</div>
      <div class="sb-val" id="s_iso">&mdash;</div>
      <div class="sb-sub" id="s_iso_sub">&nbsp;</div>
    </div>
    <div class="sb">
      <div class="sb-lbl">Fuel Cost</div>
      <div class="sb-val gold" id="s_fuel">&mdash;</div>
      <div class="sb-sub" id="s_fuel_sub">&nbsp;</div>
    </div>
    <div class="sb">
      <div class="sb-lbl">Trips Needed</div>
      <div class="sb-val" id="s_trips">&mdash;</div>
      <div class="sb-sub" id="s_trips_sub">&nbsp;</div>
    </div>
    <div class="sb hi">
      <div class="sb-lbl">Total Fee</div>
      <div class="sb-val lg green" id="s_fee">&mdash;</div>
      <div class="sb-sub" id="s_fee_sub">&nbsp;</div>
    </div>
  </div>

  <div class="be-card" id="breakdown_card" style="display:none">
    <div class="be-title">Fee Breakdown</div>
    <div class="be-row"><span class="be-lbl">Fuel recovery</span><span class="be-val" id="b_fuel">&mdash;</span></div>
    <div class="be-row"><span class="be-lbl">Flat markup</span><span class="be-val" id="b_flat">&mdash;</span></div>
    <div class="be-row"><span class="be-lbl">Collateral fee</span><span class="be-val" id="b_coll">&mdash;</span></div>
    <div class="be-row" style="border-top:1px solid rgba(68,170,255,.15);margin-top:6px;padding-top:6px">
      <span class="be-lbl">Total fee</span><span class="be-val hi" id="b_total">&mdash;</span>
    </div>
    <div class="be-row"><span class="be-lbl">Effective ISK / m&#179;</span><span class="be-val gold" id="b_rate">&mdash;</span></div>
  </div>
</div>

<div class="footer">
  Infinite Solutions &middot; Hamektok Hakaari &middot; {build_date}
</div>
</div>
<script>
const SYSTEMS = {systems_js};

function fmt(n,d) {{ d=d||0; return isFinite(n)?n.toLocaleString(undefined,{{minimumFractionDigits:d,maximumFractionDigits:d}}):'\u2014'; }}
function fmtB(n) {{
  var a=Math.abs(n), s=n<0?'-':'';
  if(a>=1e9) return s+(a/1e9).toFixed(3)+'B';
  if(a>=1e6) return s+(a/1e6).toFixed(2)+'M';
  if(a>=1e3) return s+(a/1e3).toFixed(0)+'k';
  return s+fmt(a,0);
}}

function getSysLy() {{
  var idx = parseInt(document.getElementById('sys_sel').value)||0;
  return SYSTEMS[idx] ? SYSTEMS[idx].ly : 0;
}}
function getIsoQty() {{
  var ly   = getSysLy();
  var fpl  = parseFloat(document.getElementById('fuel_per_ly').value)||0;
  var mult = document.getElementById('trip_type').value==='round' ? 2 : 1;
  return ly * fpl * mult;
}}

function recalc() {{
  var isoQty   = getIsoQty();
  var isoPrice = parseFloat(document.getElementById('iso_type').value)||0;
  var fuelCost = isoQty * isoPrice;

  var vol      = parseFloat(document.getElementById('cargo_vol').value)||0;
  var coll     = parseFloat(document.getElementById('cargo_coll').value)||0;
  var flatPerM3 = parseFloat(document.getElementById('fee_flat').value)||0;
  var collPct   = parseFloat(document.getElementById('coll_pct').value)||0;
  var shipCap   = parseFloat(document.getElementById('ship_cap').value)||0;

  var ly = getSysLy();
  var distEl = document.getElementById('sys_dist_note');
  distEl.textContent = ly > 0 ? ly.toFixed(3)+' ly from 4-HWWF' : '4-HWWF (hub)';

  var isoEl = document.getElementById('iso_calc_note');
  isoEl.textContent = isoQty > 0 ? fmt(Math.round(isoQty))+' isotopes' : '\u2014';

  // Fee components
  var fuelPerM3  = vol > 0 ? fuelCost / vol : 0;
  var fuelFee    = fuelPerM3 * vol;           // = fuelCost when vol > 0
  var flatFee    = flatPerM3 * vol;
  var collFee    = coll * collPct / 100;
  var totalFee   = fuelFee + flatFee + collFee;
  var effPerM3   = vol > 0 ? totalFee / vol : 0;

  var trips = (shipCap > 0 && vol > 0) ? Math.ceil(vol / shipCap) : 0;

  // Summary bar
  var isoSumEl = document.getElementById('s_iso');
  isoSumEl.textContent = isoQty > 0 ? fmt(Math.round(isoQty)) : '\u2014';
  document.getElementById('s_iso_sub').textContent = isoQty > 0 ? fmtB(fuelCost)+' ISK' : '';

  document.getElementById('s_fuel').textContent = vol > 0 ? fmtB(fuelCost)+' ISK' : '\u2014';
  document.getElementById('s_fuel_sub').textContent = fuelPerM3 > 0 ? fmt(fuelPerM3,2)+' ISK/m\u00B3' : '';

  document.getElementById('s_trips').textContent = trips > 0 ? trips : (vol > 0 && shipCap === 0 ? '\u2014' : '\u2014');
  document.getElementById('s_trips_sub').textContent = trips > 0 ? '@ '+fmt(shipCap)+' m\u00B3 cap' : '';

  document.getElementById('s_fee').textContent = vol > 0 || coll > 0 ? fmtB(totalFee)+' ISK' : '\u2014';
  document.getElementById('s_fee_sub').textContent = effPerM3 > 0 ? fmt(effPerM3,2)+' ISK/m\u00B3 eff.' : '';

  // Breakdown card
  var card = document.getElementById('breakdown_card');
  if (vol > 0 || coll > 0) {{
    card.style.display = 'block';
    document.getElementById('b_fuel').textContent  = fmtB(fuelFee)+' ISK';
    document.getElementById('b_flat').textContent  = fmtB(flatFee)+' ISK';
    document.getElementById('b_coll').textContent  = fmtB(collFee)+' ISK';
    document.getElementById('b_total').textContent = fmtB(totalFee)+' ISK';
    document.getElementById('b_rate').textContent  = effPerM3 > 0 ? fmt(effPerM3,2)+' ISK/m\u00B3' : '\u2014';
  }} else {{
    card.style.display = 'none';
  }}

  saveState();
}}

function saveState() {{
  var s = {{}};
  ['sys_sel','trip_type','iso_type','fuel_per_ly','fee_flat','coll_pct','ship_cap','cargo_vol','cargo_coll'].forEach(function(id) {{
    var el = document.getElementById(id); if(el) s[id] = el.value;
  }});
  try{{ localStorage.setItem('haul_calc_state', JSON.stringify(s)); }}catch(e){{}}
}}

function loadState() {{
  var raw; try{{ raw = localStorage.getItem('haul_calc_state'); }}catch(e){{}}
  if (!raw) {{ recalc(); return; }}
  var s; try{{ s = JSON.parse(raw); }}catch(e){{ recalc(); return; }}
  ['sys_sel','trip_type','iso_type','fuel_per_ly','fee_flat','coll_pct','ship_cap','cargo_vol','cargo_coll'].forEach(function(id) {{
    var el = document.getElementById(id); if(el && s[id] != null) el.value = s[id];
  }});
  recalc();
}}

window.onload = loadState;
</script>
</body>
</html>"""

with open('haul_calculator.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Done. Written to haul_calculator.html  ({len(VALE_SYSTEMS)} systems)")
