"""
Build haul_quote.html — customer-facing jump freight quote tool.
Customers enter pickup system, volume, and collateral to get an instant fee quote.

Rate config is read from haul_rates.json (saved via the Publish button in haul_calculator.html).
If haul_rates.json is absent, falls back to the constants below.
"""
import json, sqlite3, os
from datetime import datetime, timezone

# ── Default rate config (fallback if haul_rates.json not present) ────────────
RATE_PER_LY    = 12      # ISK / m³ / LY  — per-LY service markup
COLLATERAL_PCT = 0       # % of collateral added to fee (0 = free collateral coverage)
PRICING_MODE   = 'per_ly'
RATE_FLAT      = 0

# ── Pilot config (update when skills or modules change) ──────────────────────
SHIP_BASE_FUEL  = 10000    # Rhea base fuel/LY
SHIP_BASE_CARGO = 180000   # Rhea base cargo m³
JF_SKILL        = 4        # Jump Freighters skill level
JFC_SKILL       = 4        # Jump Fuel Conservation skill level
ECON_BONUS      = 0.07     # Experimental Jump Drive Economizer (7%)
EXP_BONUS       = 1.275    # Expanded Cargohold II (27.5% = ×1.275)
LOW_SLOTS       = 3
ISO_JBV_PCT     = 100      # % of JBV to pay for isotopes

# ── Load published config from haul_rates.json if present ────────────────────
_rates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'haul_rates.json')
_rates_source = 'defaults'
if os.path.exists(_rates_path):
    try:
        with open(_rates_path, encoding='utf-8') as _rf:
            _rc = json.load(_rf)
        PRICING_MODE   = _rc.get('pricing_mode',   PRICING_MODE)
        RATE_PER_LY    = float(_rc.get('rate_per_ly',    RATE_PER_LY))
        RATE_FLAT      = float(_rc.get('rate_flat',      RATE_FLAT))
        COLLATERAL_PCT = float(_rc.get('collateral_pct', COLLATERAL_PCT))
        JF_SKILL       = int(_rc.get('jf_skill',   JF_SKILL))
        JFC_SKILL      = int(_rc.get('jfc_skill',  JFC_SKILL))
        ECON_BONUS     = float(_rc.get('econ_bonus', ECON_BONUS))
        EXP_BONUS      = float(_rc.get('exp_bonus',  EXP_BONUS))
        ISO_JBV_PCT    = float(_rc.get('iso_jbv_pct', ISO_JBV_PCT))
        _pub = _rc.get('published', '')
        _rates_source = f'haul_rates.json (published {_pub[:16].replace("T"," ")})'
        print(f"  Loaded config from haul_rates.json")
    except Exception as _e:
        print(f"  Warning: could not read haul_rates.json: {_e} — using defaults")

# Module volumes (m³) — always carries all 9, 3 fitted
MOD_VOL_ECON     = 3500
MOD_VOL_EXP      = 5
MOD_VOL_BULKHEAD = 5
BULKHEADS_CARRY  = 3   # always in cargo

# EVE stacking penalty constant
STACK_C = 2.67

# ── Fetch live isotope prices from DB ────────────────────────────────────────
ISOTOPE_IDS = {
    17888: 'Nitrogen Isotopes',
    17889: 'Hydrogen Isotopes',
    17887: 'Oxygen Isotopes',
    16274: 'Helium Isotopes',
}
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mydatabase.db')
isotope_prices = {}
snap_date = datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')
try:
    _conn = sqlite3.connect(DB_PATH)
    _iso_ids_str = ','.join(str(i) for i in ISOTOPE_IDS)
    _rows = _conn.execute(f"""
        SELECT type_id, best_buy FROM market_price_snapshots
        WHERE type_id IN ({_iso_ids_str})
          AND (type_id, timestamp) IN (
              SELECT type_id, MAX(timestamp) FROM market_price_snapshots
              WHERE type_id IN ({_iso_ids_str})
              GROUP BY type_id
          )
    """).fetchall()
    for tid, price in _rows:
        isotope_prices[tid] = round(price, 2) if price else 0
    _snap_row = _conn.execute(f"""
        SELECT MAX(timestamp) FROM market_price_snapshots
        WHERE type_id IN ({_iso_ids_str})
    """).fetchone()
    if _snap_row and _snap_row[0]:
        from datetime import datetime as _dt
        _ts = _dt.strptime(_snap_row[0][:16].replace('T', ' '), '%Y-%m-%d %H:%M')
        snap_date = _ts.strftime('%d %b %Y %H:%M UTC')
    _conn.close()
except Exception as e:
    print(f"Warning: could not fetch isotope prices: {e}")
    isotope_prices = {17888: 669, 17889: 580, 17887: 736, 16274: 825}

# Default isotope = Nitrogen (Caldari ships / Rhea uses Nitrogen)
DEFAULT_ISO_ID    = 17888
DEFAULT_ISO_PRICE = isotope_prices.get(DEFAULT_ISO_ID, 669)

# Build isotope dropdown options
ISO_ORDER = [17888, 17889, 17887, 16274]
isotope_options = '\n'.join(
    f'        <option value="{isotope_prices.get(tid, 0)}"'
    f'{" selected" if tid == DEFAULT_ISO_ID else ""}>'
    f'{ISOTOPE_IDS[tid]}</option>'
    for tid in ISO_ORDER
)

# Adjusted base fuel/LY before module effects
ADJUSTED_BASE = SHIP_BASE_FUEL * (1 - 0.1 * JF_SKILL) * (1 - 0.1 * JFC_SKILL)

# Pre-compute the 4 configs and embed them in JS
import math

def stack_eff(rank):
    return math.exp(-((rank - 1) / STACK_C) ** 2)

def econ_fuel(n):
    fuel = ADJUSTED_BASE
    for i in range(1, n + 1):
        fuel *= (1 - ECON_BONUS * stack_eff(i))
    return fuel

def fitting_overhead(econ_fitted, exp_fitted):
    econ_in_cargo = 3 - econ_fitted
    exp_in_cargo  = 3 - exp_fitted
    return econ_in_cargo * MOD_VOL_ECON + exp_in_cargo * MOD_VOL_EXP + BULKHEADS_CARRY * MOD_VOL_BULKHEAD

configs_py = []
for econ in range(LOW_SLOTS + 1):
    exp = LOW_SLOTS - econ
    fuel_per_ly = econ_fuel(econ)
    cargo = SHIP_BASE_CARGO * (EXP_BONUS ** exp)
    overhead = fitting_overhead(econ, exp)
    effective_cargo = max(0, cargo - overhead)
    configs_py.append({
        'econ': econ,
        'exp': exp,
        'fuelPerLY': round(fuel_per_ly, 6),
        'effectiveCargo': round(effective_cargo, 4),
    })

configs_js = json.dumps(configs_py, separators=(',', ':'))

# Vale systems list
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
# Pickup datalist — all systems including 4-HWWF
systems_datalist = '\n'.join(
    f'        <option value="{s[0]}">{s[0]}{f" &mdash; {s[1]:.3f} ly" if s[1] > 0 else " &mdash; Hub"}</option>'
    for s in VALE_SYSTEMS
)
# Destination datalist — all systems EXCEPT 4-HWWF (only used for outbound)
systems_datalist_dest = '\n'.join(
    f'        <option value="{s[0]}">{s[0]} &mdash; {s[1]:.3f} ly</option>'
    for s in VALE_SYSTEMS if s[0] != '4-HWWF'
)
# Baked-in iso price (not shown to customer)
ISO_PRICE_BAKED = round(DEFAULT_ISO_PRICE * ISO_JBV_PCT / 100, 4)

build_date = datetime.now(timezone.utc).strftime('%d %b %Y')

# ── HTML template ─────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Infinite Solutions &mdash; Freighting Service</title>
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
.page{{width:100%;max-width:680px;}}
.hdr{{text-align:center;margin-bottom:18px;}}
.hdr h1{{font-family:'Orbitron',sans-serif;font-size:1.5em;font-weight:900;letter-spacing:4px;
  background:linear-gradient(135deg,#ff9944,#ffcc44);-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;background-clip:text;}}
.hdr .sub{{color:var(--dim);font-size:.85em;letter-spacing:2px;text-transform:uppercase;margin-top:4px;}}
.back-link{{display:inline-block;color:var(--dim);font-size:.85em;text-decoration:none;letter-spacing:1px;}}
.back-link:hover{{color:var(--text);}}
.panel{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:18px 22px;margin-bottom:12px;}}
.panel-title{{font-family:'Orbitron',sans-serif;font-size:.67em;font-weight:700;letter-spacing:2px;
  text-transform:uppercase;color:var(--accent);margin-bottom:14px;padding-bottom:7px;border-bottom:1px solid var(--border-o);}}
.form-row{{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap;}}
.form-row:last-child{{margin-bottom:0;}}
label{{color:var(--dim);font-size:.9em;font-weight:600;letter-spacing:.5px;min-width:140px;flex-shrink:0;}}
select,input[type="number"],input[type="text"]{{background:var(--panel2);border:1px solid var(--border);border-radius:4px;
  color:var(--text);font-family:'Rajdhani',sans-serif;font-size:.97em;font-weight:600;
  padding:6px 10px;outline:none;transition:border-color .15s;}}
select:focus,input:focus{{border-color:var(--accent);}}
.unit{{color:var(--dim);font-size:.87em;}}
.iv{{color:var(--accent2);font-weight:700;font-size:.93em;}}
hr.div{{border:none;border-top:1px solid var(--border);margin:14px 0;}}

/* Quote result card */
.quote-card{{background:rgba(51,221,136,.05);border:1px solid rgba(51,221,136,.3);
  border-radius:8px;padding:20px 24px;margin-top:4px;display:none;}}
.quote-card.show{{display:block;}}
.quote-total-lbl{{font-family:'Orbitron',sans-serif;font-size:.6em;letter-spacing:2px;
  text-transform:uppercase;color:var(--dim);margin-bottom:6px;}}
.quote-total{{font-family:'Orbitron',sans-serif;font-size:1.7em;font-weight:900;color:var(--green);
  letter-spacing:1px;line-height:1;margin-bottom:4px;}}
.quote-total-sub{{color:var(--dim);font-size:.85em;margin-bottom:18px;}}

.quote-route{{background:var(--panel2);border:1px solid var(--border);border-radius:6px;
  padding:10px 14px;margin-bottom:14px;font-size:.9em;}}
.quote-route-row{{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;}}
.quote-route-row:last-child{{margin-bottom:0;}}
.qrl{{color:var(--dim);}}
.qrv{{font-family:'Orbitron',sans-serif;font-size:.82em;font-weight:700;color:var(--text);}}
.qrv.accent{{color:var(--accent2);}}

.breakdown{{border-top:1px solid var(--border);padding-top:14px;margin-bottom:14px;}}
.bd-row{{display:flex;justify-content:space-between;align-items:center;
  font-size:.9em;margin-bottom:7px;}}
.bd-row:last-child{{margin-bottom:0;}}
.bd-lbl{{color:var(--dim);}}
.bd-val{{font-family:'Orbitron',sans-serif;font-size:.82em;font-weight:700;color:var(--gold);}}
.bd-total{{border-top:1px solid var(--border);padding-top:10px;margin-top:10px;}}
.bd-total .bd-lbl{{color:var(--text);font-weight:700;font-size:.95em;}}
.bd-total .bd-val{{color:var(--green);font-size:.95em;}}

.copy-btn{{display:block;width:100%;padding:11px;
  background:rgba(255,140,50,.1);border:1px solid rgba(255,140,50,.35);
  border-radius:5px;color:var(--accent);font-family:'Orbitron',sans-serif;
  font-size:.68em;letter-spacing:2px;font-weight:700;cursor:pointer;
  transition:background .15s,border-color .15s;text-transform:uppercase;}}
.copy-btn:hover{{background:rgba(255,140,50,.18);border-color:rgba(255,140,50,.6);}}
.copy-btn.copied{{background:rgba(51,221,136,.1);border-color:rgba(51,221,136,.4);color:var(--green);}}

.quote-empty{{text-align:center;padding:28px 20px;color:var(--dim);font-size:.9em;
  border:1px dashed var(--border);border-radius:8px;}}
.quote-empty .q-icon{{font-size:2em;margin-bottom:8px;opacity:.4;}}

/* Contact card */
.contact-card{{background:var(--panel2);border:1px solid var(--border);
  border-radius:6px;padding:14px 18px;text-align:center;}}
.contact-card .ct{{font-size:.85em;color:var(--dim);margin-bottom:6px;}}
.contact-card .cn{{font-family:'Orbitron',sans-serif;font-size:.95em;font-weight:700;
  color:var(--accent2);letter-spacing:1px;}}
.contact-card .ci{{font-size:.8em;color:var(--dim);margin-top:5px;}}

/* Service info pills */
.service-pills{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:4px;}}
.pill{{background:var(--panel2);border:1px solid var(--border);border-radius:20px;
  padding:4px 12px;font-size:.78em;color:var(--dim);letter-spacing:.5px;}}
.pill span{{color:var(--accent2);font-weight:700;}}

.footer{{text-align:center;color:var(--dim);font-size:.76em;margin-top:20px;
  padding-top:12px;border-top:1px solid var(--border);}}
.snap-note{{font-size:.75em;color:var(--dim);margin-top:4px;text-align:right;}}
</style>
</head>
<body>
<div class="page">

<div class="hdr">
  <h1>INFINITE SOLUTIONS</h1>
  <div class="sub">Freighting Service</div>
</div>

<!-- Service Info -->
<div class="panel">
  <div class="panel-title">How It Works</div>
  <p style="font-size:.88em;color:var(--text);line-height:1.65;margin-bottom:10px;">
    Enter your <strong style="color:var(--accent2);">pickup system</strong>, the
    <strong style="color:var(--accent2);">volume</strong> of your cargo, and its
    <strong style="color:var(--accent2);">declared collateral value</strong> to receive an instant quote.
  </p>
  <p style="font-size:.88em;color:var(--text);line-height:1.65;margin-bottom:10px;">
    Once you have your quote, create a <strong style="color:var(--accent2);">courier contract</strong> in EVE
    addressed to <strong style="color:var(--accent2);">Gromalok Hakaari</strong>.
    Set the <strong style="color:var(--accent2);">reward</strong> to the quoted fee,
    the <strong style="color:var(--accent2);">collateral</strong> to your declared value,
    and the <strong style="color:var(--accent2);">pickup</strong> and
    <strong style="color:var(--accent2);">destination</strong> to the systems shown in your quote.
  </p>
</div>

<!-- Inputs -->
<div class="panel">
  <div class="panel-title">Your Cargo</div>

  <div class="form-row">
    <label>Pickup System</label>
    <input type="text" id="sys_input" list="sys_list" placeholder="Type system name&hellip;"
      oninput="onPickupChange()" onchange="onPickupChange()" autocomplete="off"
      style="min-width:220px;flex:1;">
    <datalist id="sys_list">
{systems_datalist}
    </datalist>
    <span class="iv" id="sys_dist_note"></span>
  </div>

  <!-- Inbound: destination is always 4-HWWF (static, no input) -->
  <div class="form-row" id="dest_row_fixed">
    <label>Destination</label>
    <input type="text" value="4-HWWF" disabled
      style="min-width:220px;flex:1;opacity:0.6;">
  </div>
  <!-- Outbound (pickup = 4-HWWF): destination is free choice, excludes 4-HWWF -->
  <div class="form-row" id="dest_row_free" hidden>
    <label>Destination</label>
    <input type="text" id="dest_input" list="sys_list_dest" placeholder="Type destination system&hellip;"
      oninput="recalc()" autocomplete="off"
      style="min-width:220px;flex:1;">
    <datalist id="sys_list_dest">
{systems_datalist_dest}
    </datalist>
    <span class="iv" id="dest_note"></span>
  </div>

  <div class="form-row">
    <label>Volume</label>
    <input type="number" id="cargo_vol" min="0" step="1000" value="" oninput="recalc()"
      placeholder="e.g. 150000" style="width:160px;">
    <span class="unit">m&#179;</span>
  </div>

  <div class="form-row">
    <label>Collateral</label>
    <input type="number" id="cargo_coll" min="0" step="1000000" value="" oninput="recalc()"
      placeholder="Declared value (ISK)" style="width:190px;">
    <span class="unit">ISK</span>
  </div>
</div>

<!-- Quote Output -->
<div class="panel">
  <div class="panel-title">Your Quote</div>

  <div id="quote_empty" class="quote-empty">
    <div class="q-icon">&#128230;</div>
    Enter a pickup system and cargo volume above to get your quote.
  </div>

  <div id="quote_card" class="quote-card">
    <div class="quote-total-lbl">Total Fee</div>
    <div class="quote-total" id="q_total">&mdash;</div>
    <div class="quote-total-sub" id="q_total_sub">&mdash;</div>

    <div class="quote-route" id="q_route_box">
      <div class="quote-route-row">
        <span class="qrl">Route</span>
        <span class="qrv accent" id="q_route">&mdash;</span>
      </div>
      <div class="quote-route-row">
        <span class="qrl">Distance</span>
        <span class="qrv" id="q_dist">&mdash;</span>
      </div>
      <div class="quote-route-row">
        <span class="qrl">Cargo volume</span>
        <span class="qrv" id="q_vol">&mdash;</span>
      </div>
      <div class="quote-route-row" id="q_coll_row">
        <span class="qrl">Collateral</span>
        <span class="qrv" id="q_coll">&mdash;</span>
      </div>
      <div class="quote-route-row">
        <span class="qrl">Trips required</span>
        <span class="qrv" id="q_trips">&mdash;</span>
      </div>
    </div>

    <div class="breakdown">
      <div class="bd-row">
        <span class="bd-lbl">Fuel recovery</span>
        <span class="bd-val" id="q_fuel">&mdash;</span>
      </div>
      <div class="bd-row">
        <span class="bd-lbl">Service fee ({RATE_PER_LY} ISK/m&#179;/LY)</span>
        <span class="bd-val" id="q_markup">&mdash;</span>
      </div>
      <div class="bd-row" id="q_coll_fee_row" style="display:none">
        <span class="bd-lbl">Collateral fee ({COLLATERAL_PCT}%)</span>
        <span class="bd-val" id="q_coll_fee">&mdash;</span>
      </div>
      <div class="bd-row bd-total">
        <span class="bd-lbl">Total</span>
        <span class="bd-val" id="q_total2">&mdash;</span>
      </div>
    </div>

    <button class="copy-btn" id="copy_btn" onclick="copyQuote()">
      &#128203; &nbsp;Copy Quote to Clipboard
    </button>
  </div>
</div>

<!-- Contact -->
<div class="panel">
  <div class="panel-title">Arrange Delivery</div>
  <div class="contact-card">
    <div class="ct">Create a courier contract in EVE Online addressed to:</div>
    <div class="cn">Gromalok Hakaari</div>
    <div class="ci" id="contract_instructions">
      Set reward to quoted fee &middot; Set collateral to declared value &middot;
      Pickup and destination as shown in your quote above
    </div>
  </div>
</div>

<div class="footer">
  Infinite Solutions &middot; Hamektok Hakaari &middot; {build_date}
</div>

</div>
<script>
const SYSTEMS        = {systems_js};
const CONFIGS        = {configs_js};
const RATE_PER_LY    = {RATE_PER_LY};
const RATE_FLAT      = {RATE_FLAT};
const PRICING_MODE   = '{PRICING_MODE}';
const COLLATERAL_PCT = {COLLATERAL_PCT};
const ISO_PRICE      = {ISO_PRICE_BAKED};  // baked at build time from DB snapshot
const HUB            = '4-HWWF';

function fmt(n, d) {{
  d = d || 0;
  return isFinite(n) ? n.toLocaleString(undefined, {{minimumFractionDigits:d, maximumFractionDigits:d}}) : '\u2014';
}}
function fmtB(n) {{
  var a = Math.abs(n), s = n < 0 ? '-' : '';
  if (a >= 1e9) return s + (a / 1e9).toFixed(3) + 'B';
  if (a >= 1e6) return s + (a / 1e6).toFixed(2) + 'M';
  if (a >= 1e3) return s + (a / 1e3).toFixed(1) + 'k';
  return s + fmt(a, 0);
}}

function lookupLy(name) {{
  var n = (name || '').trim().toUpperCase();
  if (!n) return null;
  for (var i = 0; i < SYSTEMS.length; i++) {{
    if (SYSTEMS[i].name.toUpperCase() === n) return SYSTEMS[i].ly;
  }}
  return undefined; // not in list
}}

function onPickupChange() {{
  var pickup = (document.getElementById('sys_input').value || '').trim().toUpperCase();
  var distEl = document.getElementById('sys_dist_note');
  var fixedRow = document.getElementById('dest_row_fixed');
  var freeRow  = document.getElementById('dest_row_free');

  if (pickup === HUB) {{
    // Outbound: show free-choice destination input, hide fixed display
    fixedRow.hidden = true;
    freeRow.hidden  = false;
    var destEl = document.getElementById('dest_input');
    if (destEl.value.toUpperCase() === HUB) destEl.value = '';
    distEl.textContent = 'Hub \u2014 choose destination below';
    distEl.style.color = 'var(--dim)';
  }} else {{
    // Inbound (or empty): show fixed 4-HWWF display, hide free input
    fixedRow.hidden = false;
    freeRow.hidden  = true;
    if (pickup === '') {{
      distEl.textContent = '';
    }} else {{
      var ly = lookupLy(pickup);
      if (ly === undefined) {{
        distEl.textContent = 'System not found';
        distEl.style.color = 'var(--red)';
      }} else {{
        distEl.textContent = ly.toFixed(3) + ' ly';
        distEl.style.color = '';
      }}
    }}
  }}
  recalc();
}}

function getRoute() {{
  var pickup = (document.getElementById('sys_input').value || '').trim().toUpperCase();
  if (!pickup) return null;

  var ly, from, to;
  if (pickup === HUB) {{
    // Outbound: dest field is required
    var dest = (document.getElementById('dest_input').value || '').trim().toUpperCase();
    if (!dest) return null;
    ly   = lookupLy(dest);
    from = HUB;
    to   = dest;
  }} else {{
    // Inbound: destination is always HUB — don't read dest_input (cosmetic only)
    ly   = lookupLy(pickup);
    from = pickup;
    to   = HUB;
  }}

  if (ly == null || ly === undefined) return null;
  return {{ ly: ly, from: from, to: to }};
}}

function recalc() {{
  var route = getRoute();
  var vol   = parseFloat(document.getElementById('cargo_vol').value)  || 0;
  var coll  = parseFloat(document.getElementById('cargo_coll').value) || 0;

  // Update dest note
  var destNoteEl = document.getElementById('dest_note');
  var pickup = (document.getElementById('sys_input').value || '').trim().toUpperCase();
  if (pickup === HUB) {{
    var destVal = (document.getElementById('dest_input').value || '').trim().toUpperCase();
    var destLy  = lookupLy(destVal);
    if (destVal === '') {{
      destNoteEl.textContent = '';
    }} else if (destLy === undefined) {{
      destNoteEl.textContent = 'System not found';
      destNoteEl.style.color = 'var(--red)';
    }} else {{
      destNoteEl.textContent = destLy.toFixed(3) + ' ly';
      destNoteEl.style.color = '';
    }}
  }} else {{
    destNoteEl.textContent = '';
  }}

  var emptyEl = document.getElementById('quote_empty');
  var cardEl  = document.getElementById('quote_card');

  if (!route || route.ly <= 0 || !vol) {{
    emptyEl.style.display = '';
    cardEl.classList.remove('show');
    saveState();
    return;
  }}

  var ly        = route.ly;
  var collFee   = coll * COLLATERAL_PCT / 100;
  var markupFee = PRICING_MODE === 'per_ly' ? RATE_PER_LY * ly * vol : RATE_FLAT * vol;
  var bestResult = null;

  CONFIGS.forEach(function(c) {{
    var trips    = Math.ceil(vol / c.effectiveCargo);
    var isoUsed  = trips * ly * 2 * c.fuelPerLY;
    var fuelCost = isoUsed * ISO_PRICE;
    var total    = fuelCost + markupFee + collFee;
    if (bestResult === null || total < bestResult.total) {{
      bestResult = {{ trips: trips, isoUsed: isoUsed, fuelCost: fuelCost, total: total }};
    }}
  }});

  emptyEl.style.display = 'none';
  cardEl.classList.add('show');

  var totalISK = bestResult.total;
  document.getElementById('q_total').textContent   = fmtB(totalISK) + ' ISK';
  document.getElementById('q_total2').textContent  = fmtB(totalISK) + ' ISK';
  document.getElementById('q_total_sub').innerHTML = fmt(Math.round(totalISK)) + ' ISK &mdash; round trip, ' +
    bestResult.trips + (bestResult.trips === 1 ? ' trip' : ' trips');

  document.getElementById('q_route').textContent = route.from + ' \u2192 ' + route.to;
  document.getElementById('q_dist').textContent  = ly.toFixed(3) + ' ly (\u00D72 round trip)';
  document.getElementById('q_vol').textContent   = fmt(Math.round(vol)) + ' m\u00B3';

  var collRow = document.getElementById('q_coll_row');
  if (coll > 0) {{
    document.getElementById('q_coll').textContent = fmtB(coll) + ' ISK';
    collRow.style.display = '';
  }} else {{
    collRow.style.display = 'none';
  }}

  document.getElementById('q_trips').textContent  = bestResult.trips + (bestResult.trips === 1 ? ' trip' : ' trips') + ' (round trip each)';
  document.getElementById('q_fuel').textContent   = fmtB(bestResult.fuelCost) + ' ISK';
  document.getElementById('q_markup').textContent = fmtB(markupFee) + ' ISK';

  var collFeeRow = document.getElementById('q_coll_fee_row');
  if (COLLATERAL_PCT > 0 && coll > 0) {{
    document.getElementById('q_coll_fee').textContent = fmtB(collFee) + ' ISK';
    collFeeRow.style.display = '';
  }} else {{
    collFeeRow.style.display = 'none';
  }}

  // Update contract instructions with actual systems
  var ci = document.getElementById('contract_instructions');
  if (ci) {{
    ci.innerHTML = 'Set reward to quoted fee &middot; Set collateral to declared value &middot; ' +
      'Pickup: <strong style="color:var(--accent2)">' + route.from + '</strong> &middot; ' +
      'Deliver to: <strong style="color:var(--accent2)">' + route.to + '</strong>';
  }}

  var btn = document.getElementById('copy_btn');
  btn.classList.remove('copied');
  btn.textContent = '\U0001F4CB  Copy Quote to Clipboard';

  window._quoteData = {{
    from:     route.from,
    to:       route.to,
    ly:       ly,
    vol:      vol,
    coll:     coll,
    trips:    bestResult.trips,
    fuelCost: bestResult.fuelCost,
    markup:   markupFee,
    collFee:  collFee,
    total:    totalISK,
  }};

  saveState();
}}

function copyQuote() {{
  var d = window._quoteData;
  if (!d) return;

  var lines = [
    'Freight Quote \u2014 Infinite Solutions',
    '',
    'Route:      ' + d.from + ' \u2192 ' + d.to + ' (' + d.ly.toFixed(3) + ' ly, round trip)',
    'Volume:     ' + fmt(Math.round(d.vol)) + ' m\u00B3',
    'Collateral: ' + (d.coll > 0 ? fmtB(d.coll) + ' ISK' : 'None declared'),
    '',
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
    'Fuel recovery:  ' + fmtB(d.fuelCost) + ' ISK',
    'Service fee:    ' + fmtB(d.markup) + ' ISK',
  ];
  if (COLLATERAL_PCT > 0 && d.coll > 0) {{
    lines.push('Collateral fee: ' + fmtB(d.collFee) + ' ISK  (' + COLLATERAL_PCT + '%)');
  }}
  lines = lines.concat([
    '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
    'TOTAL FEE:      ' + fmt(Math.round(d.total)) + ' ISK',
    '',
    'Create courier contract to: Gromalok Hakaari',
    'Pickup: ' + d.from + '  |  Deliver to: ' + d.to,
  ]);

  var text = lines.join('\n');
  var onDone = function(ok) {{
    var btn = document.getElementById('copy_btn');
    btn.classList.add('copied');
    btn.textContent = '\u2713  Copied to Clipboard';
    setTimeout(function() {{
      btn.classList.remove('copied');
      btn.textContent = '\U0001F4CB  Copy Quote to Clipboard';
    }}, 2500);
  }};
  navigator.clipboard.writeText(text).then(onDone).catch(function() {{
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); document.execCommand('copy');
    document.body.removeChild(ta); onDone();
  }});
}}

function saveState() {{
  var s = {{}};
  ['cargo_vol', 'cargo_coll'].forEach(function(id) {{
    var el = document.getElementById(id); if (el) s[id] = el.value;
  }});
  // Note: pickup/destination not saved — always start fresh to avoid stale state
  try {{ localStorage.setItem('haul_quote_state', JSON.stringify(s)); }} catch(e) {{}}
}}

function loadState() {{
  var raw; try {{ raw = localStorage.getItem('haul_quote_state'); }} catch(e) {{}}
  if (!raw) {{ recalc(); return; }}
  var s; try {{ s = JSON.parse(raw); }} catch(e) {{ recalc(); return; }}
  ['cargo_vol', 'cargo_coll'].forEach(function(id) {{
    var el = document.getElementById(id); if (el && s[id] != null) el.value = s[id];
  }});
  recalc();
}}

// Poll pickup field — catches datalist selections that don't fire oninput/onchange
window.onload = function() {{
  loadState();
  var _lastPickup = document.getElementById('sys_input').value || '';
  setInterval(function() {{
    var cur = document.getElementById('sys_input').value || '';
    if (cur !== _lastPickup) {{
      _lastPickup = cur;
      onPickupChange();
    }}
  }}, 200);
}};
</script>
</body>
</html>"""

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'haul_quote.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Done. Written to haul_quote.html")
print(f"  Config:  {_rates_source}")
print(f"  Systems: {len(VALE_SYSTEMS)} Vale systems")
print(f"  Rate:    {RATE_PER_LY} ISK/m³/LY  |  Collateral: {COLLATERAL_PCT}%  |  Iso JBV: {ISO_JBV_PCT}%")
print(f"  Skills:  JF {JF_SKILL} / JFC {JFC_SKILL}  |  Isotope default: {ISOTOPE_IDS[DEFAULT_ISO_ID]} @ {DEFAULT_ISO_PRICE:,.2f} ISK/unit")
print(f"  Configs: {', '.join(str(c['econ'])+'E/'+str(c['exp'])+'X='+str(round(c['effectiveCargo']))+' m³' for c in configs_py)}")
