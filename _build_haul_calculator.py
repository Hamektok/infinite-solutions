"""
Build haul_calculator.html — jump-freight admin fee calculator.
Compares all 4 low-slot configurations (economizers vs cargo expanders)
and highlights the cheapest setup for the given cargo volume.
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

skill_options = '\n'.join(
    f'      <option value="{i}"{" selected" if i==4 else ""}>{i}</option>'
    for i in range(1, 6)
)

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
.back-link{{display:inline-block;color:var(--dim);font-size:.85em;text-decoration:none;letter-spacing:1px;}}
.back-link:hover{{color:var(--text);}}
.panel{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px 20px;margin-bottom:12px;}}
.panel-title{{font-family:'Orbitron',sans-serif;font-size:.67em;font-weight:700;letter-spacing:2px;
  text-transform:uppercase;color:var(--accent);margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid var(--border-o);}}
.form-row{{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap;}}
.form-row:last-child{{margin-bottom:0;}}
label{{color:var(--dim);font-size:.9em;font-weight:600;letter-spacing:.5px;min-width:190px;flex-shrink:0;}}
select,input[type="number"]{{background:var(--panel2);border:1px solid var(--border);border-radius:4px;
  color:var(--text);font-family:'Rajdhani',sans-serif;font-size:.97em;font-weight:600;
  padding:5px 9px;outline:none;transition:border-color .15s;}}
select:focus,input[type="number"]:focus{{border-color:var(--accent);}}
.unit{{color:var(--dim);font-size:.87em;}}
.iv{{color:var(--accent2);font-weight:700;font-size:.93em;}}
.note{{color:var(--dim);font-size:.82em;font-style:italic;}}
hr.div{{border:none;border-top:1px solid var(--border);margin:12px 0;}}
.sum-bar{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:4px;}}
.sb{{background:var(--panel2);border:1px solid var(--border);border-radius:6px;padding:10px 8px;text-align:center;}}
.sb.hi{{border-color:var(--border-o);background:rgba(255,140,50,.06);}}
.sb-lbl{{font-size:.65em;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;}}
.sb-val{{font-family:'Orbitron',sans-serif;font-size:.88em;font-weight:700;}}
.sb-val.green{{color:var(--green);}}.sb-val.gold{{color:var(--gold);}}.sb-val.lg{{font-size:1.1em;}}
.sb-sub{{font-size:.78em;color:var(--dim);margin-top:3px;}}
/* Comparison table */
.tbl-wrap{{overflow-x:auto;margin-top:4px;}}
table{{width:100%;border-collapse:collapse;font-size:.88em;}}
thead th{{background:var(--panel2);color:var(--dim);font-size:.7em;letter-spacing:1px;
  text-transform:uppercase;padding:8px 10px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap;}}
thead th:first-child{{text-align:left;}}
tbody td{{padding:7px 10px;border-bottom:1px solid var(--border);text-align:right;
  font-family:'Orbitron',sans-serif;font-size:.78em;font-weight:700;white-space:nowrap;}}
tbody td:first-child{{text-align:left;font-family:'Rajdhani',sans-serif;font-size:.9em;font-weight:600;}}
tbody tr:last-child td{{border-bottom:none;}}
tbody tr.winner{{background:rgba(51,221,136,.06);}}
tbody tr.winner td{{color:var(--green);}}
tbody tr.winner td:first-child{{color:var(--text);}}
.winner-badge{{display:inline-block;background:rgba(51,221,136,.15);border:1px solid rgba(51,221,136,.4);
  border-radius:3px;color:var(--green);font-family:'Orbitron',sans-serif;font-size:.6em;
  font-weight:700;letter-spacing:1px;padding:1px 6px;margin-left:8px;vertical-align:middle;}}
tbody tr td.td-fee{{color:var(--gold);}}
tbody tr.winner td.td-fee{{color:var(--green);}}
tbody tr td.td-dim{{color:var(--dim);font-family:'Rajdhani',sans-serif;font-size:.85em;font-weight:600;}}
.callout{{background:rgba(51,221,136,.05);border:1px solid rgba(51,221,136,.25);
  border-radius:6px;padding:12px 16px;margin-top:10px;display:none;}}
.callout-title{{font-family:'Orbitron',sans-serif;font-size:.63em;letter-spacing:2px;
  text-transform:uppercase;color:var(--green);margin-bottom:8px;}}
.callout-row{{display:flex;justify-content:space-between;align-items:center;font-size:.9em;margin-bottom:4px;}}
.callout-row:last-child{{margin-bottom:0;}}
.callout-lbl{{color:var(--dim);}}
.callout-val{{font-family:'Orbitron',sans-serif;font-size:.85em;font-weight:700;}}
.callout-val.green{{color:var(--green);}}.callout-val.gold{{color:var(--gold);}}
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

  <hr class="div">

  <div class="form-row">
    <label>Ship</label>
    <select id="ship_sel" onchange="recalc()" style="min-width:260px">
      <option value="rhea">Rhea &mdash; 10,000 fuel/LY &mdash; 180,000 m&#179;</option>
    </select>
    <span class="unit" id="ship_note">&mdash;</span>
  </div>
  <div class="form-row">
    <label>Jump Freighters Skill</label>
    <select id="jf_skill" onchange="recalc()" style="min-width:80px">
{skill_options}
    </select>
    <span class="unit" id="jf_note">&mdash;</span>
  </div>
  <div class="form-row">
    <label>Jump Fuel Conservation</label>
    <select id="jfc_skill" onchange="recalc()" style="min-width:80px">
{skill_options}
    </select>
    <span class="unit" id="jfc_note">&mdash;</span>
  </div>

  <hr class="div">

  <div class="form-row">
    <label>Economizer Module</label>
    <select id="econ_type" onchange="recalc()" style="min-width:340px">
      <option value="0.07" selected>Experimental Jump Drive Economizer &mdash; 7%</option>
      <option value="0.10">Prototype Jump Drive Economizer &mdash; 10%</option>
    </select>
  </div>
  <div class="form-row">
    <label>Cargo Expander Module</label>
    <select id="exp_type" onchange="recalc()" style="min-width:340px">
      <option value="1.275" selected>Expanded Cargohold II &mdash; 27.5%</option>
    </select>
  </div>

  <hr class="div">

  <div class="form-row">
    <label>Flat Markup</label>
    <input type="number" id="fee_flat" min="0" step="1" value="0" oninput="recalc()" style="width:110px">
    <span class="unit">ISK / m&#179;</span>
  </div>
  <div class="form-row">
    <label>Collateral Fee</label>
    <input type="number" id="coll_pct" min="0" max="10" step="0.01" value="0" oninput="recalc()" style="width:90px">
    <span class="unit">% of collateral</span>
  </div>
</div>

<div class="panel">
  <div class="panel-title">Cargo</div>
  <div class="form-row">
    <label>Volume</label>
    <input type="number" id="cargo_vol" min="0" step="1" value="0" oninput="recalc()" style="width:160px">
    <span class="unit">m&#179;</span>
  </div>
  <div class="form-row">
    <label>Collateral</label>
    <input type="number" id="cargo_coll" min="0" step="1000000" value="0" oninput="recalc()" style="width:180px">
    <span class="unit">ISK</span>
  </div>
</div>

<div class="panel">
  <div class="panel-title">Configuration Comparison &mdash; 3 Low Slots</div>
  <div class="tbl-wrap">
  <table>
    <thead>
      <tr>
        <th style="min-width:180px;text-align:left">Fit</th>
        <th>Available Cargo<br><span style="font-size:.8em;opacity:.6">after fittings</span></th>
        <th>Fuel / LY</th>
        <th>Trips</th>
        <th>Isotopes</th>
        <th>Fuel Cost</th>
        <th>Total Fee</th>
      </tr>
    </thead>
    <tbody id="cfg_body"></tbody>
  </table>
  </div>

  <div class="callout" id="winner_callout">
    <div class="callout-title">&#9733; Recommended Fit</div>
    <div class="callout-row"><span class="callout-lbl">Configuration</span><span class="callout-val" id="w_fit">&mdash;</span></div>
    <div class="callout-row"><span class="callout-lbl">Trips needed</span><span class="callout-val" id="w_trips">&mdash;</span></div>
    <div class="callout-row"><span class="callout-lbl">Total isotopes</span><span class="callout-val" id="w_iso">&mdash;</span></div>
    <div class="callout-row"><span class="callout-lbl">Fuel cost</span><span class="callout-val gold" id="w_fuel">&mdash;</span></div>
    <div class="callout-row"><span class="callout-lbl">Total fee to charge</span><span class="callout-val green" id="w_fee">&mdash;</span></div>
    <div class="callout-row"><span class="callout-lbl">Savings vs worst fit</span><span class="callout-val green" id="w_save">&mdash;</span></div>
  </div>
</div>

<div class="footer">
  Infinite Solutions &middot; Hamektok Hakaari &middot; {build_date}
</div>
</div>
<script>
const SYSTEMS = {systems_js};

// Ship definitions — add more ships here as needed
var SHIPS = {{
  rhea: {{ name: 'Rhea', baseFuel: 10000, baseCargo: 180000 }}
}};

var LOW_SLOTS = 3;

// Always carries all 9 modules; 3 are fitted (0 m³), 6 are in cargo.
// Which are fitted vs in cargo depends on the config.
// Module volumes: Exp=5 m³, Bulkhead=5 m³, Econ=3500 m³
// Bulkheads are never fitted in these configs (not econ or exp) — always in cargo.
var MOD_VOL = {{ exp: 5, econ: 3500, bulkhead: 5 }};
var BULKHEAD_CARRY = 3;  // always in cargo regardless of config

// Overhead for a given config: unfitted econ + unfitted exp + bulkheads
function fittingOverhead(econFitted, expFitted) {{
  var econInCargo = 3 - econFitted;
  var expInCargo  = 3 - expFitted;
  return econInCargo * MOD_VOL.econ + expInCargo * MOD_VOL.exp + BULKHEAD_CARRY * MOD_VOL.bulkhead;
}}
var STACK_C    = 2.67;   // EVE stacking penalty constant

// EVE stacking penalty: e^(-((rank-1)/2.67)^2), rank is 1-based
function stackEff(rank) {{
  return Math.exp(-Math.pow((rank - 1) / STACK_C, 2));
}}

// Fuel/LY after applying n economizers with stacking penalties
function econFuel(adjustedBase, n) {{
  var econBonus = parseFloat(document.getElementById('econ_type').value)||0.07;
  var fuel = adjustedBase;
  for (var i = 1; i <= n; i++) {{
    fuel *= (1 - econBonus * stackEff(i));
  }}
  return fuel;
}}

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

// Get selected ship data
function getShip() {{
  var key = document.getElementById('ship_sel').value;
  return SHIPS[key] || SHIPS.rhea;
}}

// Compute adjusted base fuel/LY from skills (before mods)
function getAdjustedBase() {{
  var ship = getShip();
  var jf   = parseInt(document.getElementById('jf_skill').value)||4;
  var jfc  = parseInt(document.getElementById('jfc_skill').value)||4;
  return ship.baseFuel * (1 - 0.1*jf) * (1 - 0.1*jfc);
}}

// Returns array of config objects for all valid econ/exp combos across LOW_SLOTS slots
function getConfigs(adjustedBase, baseCargo) {{
  var expBonus = parseFloat(document.getElementById('exp_type').value)||1.275;
  var configs = [];
  for (var econ = 0; econ <= LOW_SLOTS; econ++) {{
    var exp = LOW_SLOTS - econ;
    var fuelPerLY = econFuel(adjustedBase, econ);
    var cargo     = baseCargo * Math.pow(expBonus, exp);
    var overhead = fittingOverhead(econ, exp);
    var effectiveCargo = Math.max(0, cargo - overhead);
    configs.push({{
      econ:          econ,
      exp:           exp,
      fuelPerLY:     fuelPerLY,
      cargo:         cargo,
      overhead:      overhead,
      effectiveCargo: effectiveCargo,
      label:    econ===0 ? '3 Exp' :
                exp===0  ? '3 Econ' :
                econ+'E / '+exp+'X'
    }});
  }}
  return configs;
}}

function recalc() {{
  var ly        = getSysLy();
  var mult      = document.getElementById('trip_type').value==='round' ? 2 : 1;
  var isoPrice  = parseFloat(document.getElementById('iso_type').value)||0;
  var vol       = parseFloat(document.getElementById('cargo_vol').value)||0;
  var coll      = parseFloat(document.getElementById('cargo_coll').value)||0;
  var flatPerM3 = parseFloat(document.getElementById('fee_flat').value)||0;
  var collPct   = parseFloat(document.getElementById('coll_pct').value)||0;

  var ship    = getShip();
  var adjBase = getAdjustedBase();
  var jf      = parseInt(document.getElementById('jf_skill').value)||4;
  var jfc     = parseInt(document.getElementById('jfc_skill').value)||4;
  var baseCargo = ship.baseCargo;

  // Update notes
  document.getElementById('ship_note').textContent   = fmt(ship.baseFuel)+' fuel/LY base \u00B7 '+fmt(ship.baseCargo)+' m\u00B3 base \u2192 '+fmt(Math.round(adjBase))+' fuel/LY at skill';
  document.getElementById('jf_note').textContent     = '\u2212'+(jf*10)+'% \u2192 \u00D7'+(1-0.1*jf).toFixed(1);
  document.getElementById('jfc_note').textContent    = '\u2212'+(jfc*10)+'% \u2192 \u00D7'+(1-0.1*jfc).toFixed(1);
  document.getElementById('sys_dist_note').textContent = ly > 0 ? ly.toFixed(3)+' ly from 4-HWWF' : '4-HWWF (hub)';

  var configs = getConfigs(adjBase, baseCargo);
  var collFee = coll * collPct / 100;
  var flatFee = flatPerM3 * vol;

  // Compute totals for each config
  var results = configs.map(function(c) {{
    var trips     = vol > 0 ? Math.ceil(vol / c.effectiveCargo) : 0;
    var isoUsed   = trips * ly * mult * c.fuelPerLY;
    var fuelCost  = isoUsed * isoPrice;
    var totalFee  = fuelCost + flatFee + collFee;
    return {{
      econ:          c.econ,
      exp:           c.exp,
      label:         c.label,
      cargo:         c.cargo,
      overhead:      c.overhead,
      effectiveCargo: c.effectiveCargo,
      fuelPerLY:     c.fuelPerLY,
      trips:         trips,
      isoUsed:       isoUsed,
      fuelCost:      fuelCost,
      totalFee:      totalFee
    }};
  }});

  // Find winner (minimum totalFee; if all zero, no winner)
  var hasData = vol > 0 || coll > 0;
  var winIdx = -1;
  if (hasData) {{
    var minFee = Infinity;
    results.forEach(function(r,i) {{ if(r.totalFee < minFee) {{ minFee=r.totalFee; winIdx=i; }} }});
  }}
  var maxFee = hasData ? Math.max.apply(null, results.map(function(r){{return r.totalFee;}})) : 0;

  // Build table rows
  var tbody = document.getElementById('cfg_body');
  tbody.innerHTML = '';
  results.forEach(function(r, i) {{
    var isWin = (i === winIdx);
    var tr = document.createElement('tr');
    if (isWin) tr.className = 'winner';

    var fitLabel = (r.econ===0 ? '0 Econ' : r.econ+' Econ') + ' + ' +
                   (r.exp===0  ? '0 Exp'  : r.exp+' Exp');
    var badge = isWin ? '<span class="winner-badge">BEST</span>' : '';

    tr.innerHTML =
      '<td>'+fitLabel+badge+'</td>' +
      '<td class="td-dim">'+fmt(Math.round(r.effectiveCargo))+' m\u00B3<br><span style="font-size:.8em;opacity:.55">'+fmt(Math.round(r.cargo))+' \u2212 '+fmt(r.overhead)+'</span></td>' +
      '<td class="td-dim">'+fmt(Math.round(r.fuelPerLY))+'</td>' +
      '<td>'+(r.trips > 0 ? r.trips : '\u2014')+'</td>' +
      '<td>'+(r.isoUsed > 0 ? fmt(Math.round(r.isoUsed)) : '\u2014')+'</td>' +
      '<td>'+(r.fuelCost > 0 ? fmtB(r.fuelCost)+' ISK' : '\u2014')+'</td>' +
      '<td class="td-fee">'+(hasData ? fmtB(r.totalFee)+' ISK' : '\u2014')+'</td>';
    tbody.appendChild(tr);
  }});

  // Winner callout
  var callout = document.getElementById('winner_callout');
  if (hasData && winIdx >= 0) {{
    var w = results[winIdx];
    callout.style.display = 'block';
    document.getElementById('w_fit').textContent   = (w.econ===0?'0 Econ':w.econ+' Econ')+' + '+(w.exp===0?'0 Exp':w.exp+' Exp');
    document.getElementById('w_trips').textContent = w.trips > 0 ? w.trips+' trip'+(w.trips>1?'s':'') : '\u2014';
    document.getElementById('w_iso').textContent   = w.isoUsed > 0 ? fmt(Math.round(w.isoUsed)) : '\u2014';
    document.getElementById('w_fuel').textContent  = fmtB(w.fuelCost)+' ISK';
    document.getElementById('w_fee').textContent   = fmtB(w.totalFee)+' ISK';
    var savings = maxFee - w.totalFee;
    document.getElementById('w_save').textContent  = savings > 0 ? fmtB(savings)+' ISK vs worst fit' : 'Tied \u2014 all fits equal';
  }} else {{
    callout.style.display = 'none';
  }}

  saveState();
}}

function saveState() {{
  var s = {{}};
  ['sys_sel','trip_type','iso_type','ship_sel','jf_skill','jfc_skill',
   'econ_type','exp_type','fee_flat','coll_pct','cargo_vol','cargo_coll'].forEach(function(id) {{
    var el = document.getElementById(id); if(el) s[id] = el.value;
  }});
  try{{ localStorage.setItem('haul_calc_state', JSON.stringify(s)); }}catch(e){{}}
}}

function loadState() {{
  var raw; try{{ raw = localStorage.getItem('haul_calc_state'); }}catch(e){{}}
  if (!raw) {{ recalc(); return; }}
  var s; try{{ s = JSON.parse(raw); }}catch(e){{ recalc(); return; }}
  ['sys_sel','trip_type','iso_type','ship_sel','jf_skill','jfc_skill',
   'econ_type','exp_type','fee_flat','coll_pct','cargo_vol','cargo_coll'].forEach(function(id) {{
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
