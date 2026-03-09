#!/usr/bin/env python3
"""
onboard_consignor.py
Opens a local browser form to onboard a new PI consignor into mydatabase.db.
Usage:  python onboard_consignor.py
Stop:   Ctrl+C in the terminal.
"""

import json
import os
import sqlite3
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

DB_PATH        = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mydatabase.db')
AGREEMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'consignor_agreements')
PORT           = 8877


def generate_agreement_text(data: dict, consignor_pct: float, don_opted: bool, don_pct: float) -> str:
    """Return a Discord-formatted agreement string."""
    comm_pct   = float(data['commission_pct'])
    slot_label = 'Exclusive' if data.get('slot_type') == 'exclusive' else 'Shared'

    lines = [
        '**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**',
        '**Infinite Solutions — Partner Program Agreement**',
        '**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**',
        f'**Consignor:** {data["character_name"]}',
        f'**Item:** {data["item_name"]}',
        f'**Slot Type:** {slot_label}',
        f'**Effective Date:** {data["start_date"]}',
        '',
        '**— Commercial Terms —**',
        f'• Corp Commission: **{comm_pct:.1f}%**',
        f'• Your Share: **{consignor_pct:.1f}%**',
    ]

    if data.get('list_price'):
        lines.append(f'• List Price: **{float(data["list_price"]):,.2f} ISK/unit**')
    if data.get('max_units'):
        lines.append(f'• Monthly Supply Cap: **{int(data["max_units"]):,} units**')
    if don_opted and don_pct > 0:
        lines.append(f'• Corp Donation: **{don_pct:.1f}%** of your share per sale *(voluntary)*')

    demand_label = data.get('demand_tier', 'medium').capitalize()
    lines.append(f'• Demand Tier: {demand_label}')

    if data.get('notes', '').strip():
        lines += ['', '**— Notes —**', f'*{data["notes"].strip()}*']

    lines += [
        '',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        'This agreement is on file with **Infinite Solutions** at **LX-ZOJ**.',
        'Contact **Hamektok Hakaari** with any questions.',
    ]

    return '\n'.join(lines)


def save_agreement_file(char_name: str, item_name: str, start_date: str, text: str) -> str:
    """Write agreement to consignor_agreements/ and return the file path."""
    os.makedirs(AGREEMENTS_DIR, exist_ok=True)
    safe_char = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in char_name).strip()
    safe_item = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in item_name).strip()
    filename  = f'{start_date}_{safe_char}_{safe_item}.txt'
    filepath  = os.path.join(AGREEMENTS_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    return filepath

# ── PI items by tier (type_id, display name) ──────────────────────────────────
PI_TIERS = [
    ('P1 — Raw Extraction', [
        (2393,'Bacteria'),(2396,'Biofuels'),(3779,'Biomass'),(2401,'Chiral Structures'),
        (2390,'Electrolytes'),(2397,'Industrial Fibers'),(2392,'Oxidizing Compound'),
        (3683,'Oxygen'),(2389,'Plasmoids'),(2399,'Precious Metals'),(2395,'Proteins'),
        (2398,'Reactive Metals'),(9828,'Silicon'),(2400,'Toxic Metals'),(3645,'Water'),
    ]),
    ('P2 — Refined Commodities', [
        (2329,'Biocells'),(3828,'Construction Blocks'),(9836,'Consumer Electronics'),
        (9832,'Coolant'),(44,'Enriched Uranium'),(15317,'Genetically Enhanced Livestock'),
        (3689,'Mechanical Parts'),(2327,'Microfiber Shielding'),(9842,'Miniature Electronics'),
        (2463,'Nanites'),(2317,'Oxides'),(2321,'Polyaramids'),(3695,'Polytextiles'),
        (9830,'Rocket Fuel'),(3697,'Silicate Glass'),(9838,'Superconductors'),
        (2312,'Supertensile Plastics'),(3691,'Synthetic Oil'),(2319,'Test Cultures'),
        (9840,'Transmitter'),(3775,'Viral Agent'),
    ]),
    ('P3 — Specialized Commodities', [
        (2358,'Biotech Research Reports'),(2345,'Camera Drones'),(2344,'Condensates'),
        (2367,'Cryoprotectant Solution'),(17392,'Data Chips'),(2348,'Gel-Matrix Biopaste'),
        (9834,'Guidance Systems'),(2366,'Hazmat Detection Systems'),(2361,'Hermetic Membranes'),
        (17898,'High-Tech Transmitters'),(2360,'Industrial Explosives'),(2354,'Neocoms'),
        (2352,'Nuclear Reactors'),(9846,'Planetary Vehicles'),(9848,'Robotics'),
        (2351,'Smartfab Units'),(2349,'Supercomputers'),(2346,'Synthetic Synapses'),
        (12836,'Transcranial Microcontrollers'),(17136,'Ukomi Superconductors'),(28974,'Vaccines'),
    ]),
    ('P4 — Advanced Commodities', [
        (2867,'Broadcast Node'),(2868,'Integrity Response Drones'),(2869,'Nano-Factory'),
        (2870,'Organic Mortar Applicators'),(2871,'Recursive Computing Module'),
        (2872,'Self-Harmonizing Power Core'),(2875,'Sterile Conduits'),(2876,'Wetware Mainframe'),
    ]),
]


def build_select_options():
    html = '<option value="">— Select item —</option>'
    for label, items in PI_TIERS:
        html += f'<optgroup label="{label}">'
        for tid, name in sorted(items, key=lambda x: x[1]):
            html += f'<option value="{tid}" data-name="{name}">{name}</option>'
        html += '</optgroup>'
    return html


def get_current_price(type_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            'SELECT best_sell FROM market_price_snapshots '
            'WHERE type_id=? ORDER BY timestamp DESC LIMIT 1',
            (type_id,)
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


# ── HTML page ─────────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Onboard Consignor — Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&family=Rajdhani:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:      #080e18;  --bg2: #0a1520;  --bg3: #0d1f30;  --card: #0f2035;
    --border:  #1a3a55;  --border2: #224460;
    --accent:  #66d9ff;  --gold: #ffcc44;  --green: #44dd88;
    --orange:  #ff9944;  --red: #ff5555;
    --muted:   #4a7090;  --text: #c8dde8;  --dim: #6a8fa8;
  }
  body {
    background: var(--bg); color: var(--text);
    font-family: 'Rajdhani','Segoe UI',sans-serif;
    font-size: 15px; line-height: 1.7;
    min-height: 100vh; padding: 40px 16px 80px;
  }
  .page { max-width: 680px; margin: 0 auto; }

  /* HEADER */
  .survey-header { text-align: center; margin-bottom: 40px; }
  .survey-header .org {
    font-family: 'Orbitron',monospace; font-size: 0.6rem;
    letter-spacing: 0.22em; text-transform: uppercase;
    color: var(--muted); margin-bottom: 10px;
  }
  .survey-header h1 {
    font-family: 'Orbitron',monospace; font-size: 1.3rem;
    font-weight: 700; color: var(--gold);
    letter-spacing: 0.06em; margin-bottom: 10px;
  }
  .survey-header p { color: var(--dim); font-size: 0.92rem; max-width: 520px; margin: 0 auto; }
  .admin-badge {
    display: inline-block;
    font-family: 'Orbitron',monospace; font-size: 0.55rem;
    letter-spacing: 0.16em; text-transform: uppercase;
    background: rgba(255,204,68,0.1); border: 1px solid var(--gold);
    color: var(--gold); padding: 3px 10px; border-radius: 3px; margin-bottom: 14px;
  }

  /* SECTION CARDS */
  .section {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 24px 28px; margin-bottom: 20px;
  }
  .section-label {
    font-family: 'Orbitron',monospace; font-size: 0.58rem;
    letter-spacing: 0.2em; text-transform: uppercase;
    color: var(--accent); margin-bottom: 20px;
    display: flex; align-items: center; gap: 10px;
  }
  .section-label::after { content:''; flex:1; height:1px; background: var(--border); }

  /* QUESTIONS */
  .question { margin-bottom: 22px; }
  .question:last-child { margin-bottom: 0; }
  .q-label {
    font-weight: 600; color: #ddeeff; font-size: 0.95rem;
    margin-bottom: 3px; display: flex; align-items: center; gap: 8px;
  }
  .q-label .q-num {
    font-family: 'Orbitron',monospace; font-size: 0.58rem;
    background: var(--border2); color: var(--accent);
    padding: 2px 7px; border-radius: 3px; letter-spacing: 0.08em;
  }
  .q-label .req { color: var(--orange); font-size: 0.7rem; }
  .q-hint { color: var(--muted); font-size: 0.8rem; margin-bottom: 10px; font-style: italic; }
  .opt-em { color: var(--dim); font-size: 0.78rem; margin-left: 2px; }

  /* RADIO OPTIONS */
  .radio-group { display: flex; flex-direction: column; gap: 6px; }
  .radio-group.inline { flex-direction: row; flex-wrap: wrap; gap: 8px; }
  .opt-label {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 14px; background: var(--bg3);
    border: 1px solid var(--border); border-radius: 7px;
    cursor: pointer; transition: border-color 0.12s, background 0.12s;
    user-select: none; font-size: 0.88rem;
  }
  .opt-label:hover { border-color: var(--border2); background: #112030; }
  input[type=radio] { display: none; }
  .opt-indicator {
    width: 16px; height: 16px; border: 2px solid var(--border2);
    border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
  }
  input[type=radio]:checked + .opt-label {
    border-color: var(--accent); background: rgba(102,217,255,0.06); color: #e8f8ff;
  }
  input[type=radio]:checked + .opt-label .opt-indicator {
    border-color: var(--accent); background: var(--accent);
    box-shadow: 0 0 6px rgba(102,217,255,0.5);
  }
  input[type=radio]:checked + .opt-label .opt-indicator::after {
    content:''; width:6px; height:6px; background: var(--bg); border-radius: 50%;
  }

  /* TEXT / NUMBER INPUTS */
  .text-input, textarea, select {
    width: 100%; background: var(--bg3);
    border: 1px solid var(--border); border-radius: 7px;
    color: var(--text); font-family: 'Rajdhani','Segoe UI',sans-serif;
    font-size: 0.9rem; padding: 10px 14px; outline: none;
    transition: border-color 0.12s;
  }
  .text-input:focus, textarea:focus, select:focus { border-color: var(--accent); }
  textarea { min-height: 80px; line-height: 1.5; resize: vertical; }
  ::placeholder { color: var(--muted); }

  /* SELECT styling */
  select {
    cursor: pointer; appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%234a7090' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 14px center; padding-right: 36px;
  }
  select option  { background: #0d1f30; color: var(--text); }
  select optgroup { color: var(--gold); font-style: normal; font-weight: 600; }

  /* TWO-COLUMN ROW */
  .input-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 500px) { .input-row { grid-template-columns: 1fr; } }

  /* PRICE + FETCH BUTTON ROW */
  .input-with-btn { display: flex; gap: 8px; }
  .input-with-btn .text-input { flex: 1; }
  .btn-fetch {
    font-family: 'Orbitron',monospace; font-size: 0.55rem; letter-spacing: 0.1em;
    padding: 0 14px; background: var(--border2); border: 1px solid var(--border2);
    color: var(--accent); border-radius: 7px; cursor: pointer;
    white-space: nowrap; transition: all 0.12s; flex-shrink: 0;
  }
  .btn-fetch:hover:not(:disabled) { background: var(--accent); color: var(--bg); }
  .btn-fetch:disabled { opacity: 0.35; cursor: not-allowed; }

  /* PREVIEW + NOTE */
  .field-note { font-size: 0.8rem; margin-top: 5px; }
  .field-note.ok  { color: var(--green); }
  .field-note.dim { color: var(--dim); }
  .field-note.warn { color: var(--orange); }

  /* ERROR */
  .err-msg {
    display: none; color: var(--red); font-size: 0.8rem; margin-top: 6px;
    padding: 6px 12px; background: rgba(255,85,85,0.07);
    border-left: 3px solid var(--red); border-radius: 0 5px 5px 0;
  }
  .err-msg.show { display: block; }

  /* SUBMIT */
  .submit-wrap { text-align: center; margin-top: 30px; }
  .btn-submit {
    font-family: 'Orbitron',monospace; font-size: 0.7rem; letter-spacing: 0.16em;
    font-weight: 700; text-transform: uppercase; padding: 14px 48px;
    background: var(--gold); color: var(--bg); border: none; border-radius: 7px;
    cursor: pointer; transition: all 0.15s;
  }
  .btn-submit:hover:not(:disabled) { background: #ffe066; transform: translateY(-1px); }
  .btn-submit:disabled { background: var(--muted); cursor: not-allowed; transform: none; }
  .submit-note { color: var(--muted); font-size: 0.78rem; margin-top: 10px; }

  /* SUCCESS */
  #success-screen { display: none; padding: 40px 0 60px; animation: fadeIn 0.4s ease; }
  .success-top { text-align: center; margin-bottom: 28px; }
  #success-screen .check-icon {
    width: 72px; height: 72px; border-radius: 50%;
    background: rgba(68,221,136,0.12); border: 2px solid var(--green);
    display: flex; align-items: center; justify-content: center;
    font-size: 2rem; margin: 0 auto 20px;
  }
  #success-screen h2 { font-family: 'Orbitron',monospace; color: var(--green); font-size: 1.1rem; letter-spacing: 0.08em; margin-bottom: 8px; }
  #success-screen .sub { color: var(--dim); font-size: 0.9rem; margin-bottom: 4px; }
  #success-screen .saved-path { color: var(--muted); font-size: 0.78rem; font-style: italic; }

  /* Discord agreement block */
  .agreement-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 20px 24px; margin-bottom: 16px;
  }
  .agreement-card-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 12px;
  }
  .agreement-card-header span {
    font-family: 'Orbitron',monospace; font-size: 0.58rem;
    letter-spacing: 0.18em; text-transform: uppercase; color: var(--accent);
  }
  .btn-copy {
    font-family: 'Orbitron',monospace; font-size: 0.58rem; letter-spacing: 0.1em;
    padding: 6px 18px; background: transparent;
    border: 1px solid var(--accent); color: var(--accent);
    border-radius: 5px; cursor: pointer; transition: all 0.15s;
  }
  .btn-copy:hover { background: rgba(102,217,255,0.12); }
  .btn-copy.copied { border-color: var(--green); color: var(--green); }
  #discord-text {
    width: 100%; background: #060d16; border: 1px solid var(--border);
    border-radius: 6px; color: #c8dde8; font-family: 'Consolas','Courier New',monospace;
    font-size: 0.82rem; line-height: 1.6; padding: 14px; resize: vertical;
    min-height: 260px; outline: none;
  }
  .btn-another {
    font-family: 'Orbitron',monospace; font-size: 0.65rem; letter-spacing: 0.12em;
    padding: 10px 28px; background: transparent;
    border: 1px solid var(--border2); color: var(--dim);
    border-radius: 6px; cursor: pointer; transition: all 0.15s; display: block; margin: 0 auto;
  }
  .btn-another:hover { border-color: var(--accent); color: var(--accent); }

  @keyframes fadeIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:none; } }
</style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="survey-header">
    <div class="admin-badge">Admin Tool · Local Only</div>
    <div class="org">Infinite Solutions · LX-ZOJ Market Slots</div>
    <h1>Consignor Onboarding</h1>
    <p>Enter the agreed terms below. The record is written directly to mydatabase.db and will appear in the admin dashboard immediately on next load.</p>
  </div>

  <form id="onboard-form" autocomplete="off" novalidate>

    <!-- ── SECTION 1: Identity ── -->
    <div class="section">
      <div class="section-label">Section 1 — Consignor Identity</div>

      <div class="question">
        <div class="q-label"><span class="q-num">F1</span> In-Game Character Name <span class="req">*</span></div>
        <input type="text" class="text-input" id="character_name" placeholder="Exact in-game character name">
        <div class="err-msg" id="f1-err">Character name is required.</div>
      </div>

      <div class="question">
        <div class="q-label"><span class="q-num">F2</span> Item Being Consigned <span class="req">*</span></div>
        <select id="item_select" onchange="onItemChange()">
          {{SELECT_OPTIONS}}
        </select>
        <div class="err-msg" id="f2-err">Please select an item.</div>
      </div>

      <div class="question">
        <div class="q-label"><span class="q-num">F3</span> Slot Type <span class="req">*</span></div>
        <div class="radio-group">
          <input type="radio" name="slot_type" id="slot_exclusive" value="exclusive">
          <label class="opt-label" for="slot_exclusive">
            <span class="opt-indicator"></span>
            <div><strong>Exclusive</strong> <span class="opt-em">— only this consignor sells this item in the citadel</span></div>
          </label>
          <input type="radio" name="slot_type" id="slot_shared" value="shared" checked>
          <label class="opt-label" for="slot_shared">
            <span class="opt-indicator"></span>
            <div><strong>Shared</strong> <span class="opt-em">— multiple consignors may supply the same item</span></div>
          </label>
        </div>
      </div>
    </div>

    <!-- ── SECTION 2: Commercial Terms ── -->
    <div class="section">
      <div class="section-label">Section 2 — Commercial Terms</div>

      <div class="question">
        <div class="q-label"><span class="q-num">F4</span> Our Commission Rate (%) <span class="req">*</span></div>
        <div class="q-hint">The percentage we keep. Consignor receives the remainder.</div>
        <input type="number" class="text-input" id="commission_pct"
               value="2.5" min="0" max="50" step="0.5" style="max-width:160px;"
               oninput="updateCommPreview()">
        <div class="field-note dim" id="comm-preview">Consignor receives: 97.5%</div>
        <div class="err-msg" id="f4-err">Required — enter a commission percentage.</div>
      </div>

      <div class="question">
        <div class="q-label"><span class="q-num">F5</span> List Price per Unit (ISK) <span class="opt-em">(optional)</span></div>
        <div class="q-hint">Current market sell price. Leave blank to set later in the admin dashboard.</div>
        <div class="input-with-btn">
          <input type="number" class="text-input" id="list_price" placeholder="e.g. 850000" min="0" step="0.01">
          <button type="button" class="btn-fetch" id="fetch-price-btn" onclick="fetchPrice()" disabled>Fetch Current</button>
        </div>
        <div class="field-note dim" id="price-note"></div>
      </div>

      <div class="input-row">
        <div class="question" style="margin-bottom:0">
          <div class="q-label"><span class="q-num">F6</span> Max Units/mo <span class="opt-em">(optional)</span></div>
          <div class="q-hint">Agreed monthly supply cap.</div>
          <input type="number" class="text-input" id="max_units" placeholder="e.g. 500000" min="0" step="1000">
        </div>
        <div class="question" style="margin-bottom:0">
          <div class="q-label"><span class="q-num">F7</span> Start Date <span class="req">*</span></div>
          <div class="q-hint">Agreement effective date.</div>
          <input type="date" class="text-input" id="start_date" value="{{TODAY}}">
        </div>
      </div>
    </div>

    <!-- ── SECTION 3: Slot Settings ── -->
    <div class="section">
      <div class="section-label">Section 3 — Slot Settings</div>

      <div class="question">
        <div class="q-label"><span class="q-num">F8</span> Demand Tier</div>
        <div class="q-hint">Used for display ordering and priority in the admin dashboard.</div>
        <div class="radio-group inline">
          <input type="radio" name="demand_tier" id="demand_high" value="high">
          <label class="opt-label" for="demand_high"><span class="opt-indicator"></span>High demand</label>
          <input type="radio" name="demand_tier" id="demand_medium" value="medium" checked>
          <label class="opt-label" for="demand_medium"><span class="opt-indicator"></span>Medium demand</label>
          <input type="radio" name="demand_tier" id="demand_low" value="low">
          <label class="opt-label" for="demand_low"><span class="opt-indicator"></span>Low demand</label>
        </div>
      </div>

      <div class="question">
        <div class="q-label"><span class="q-num">F9</span> Priority <span class="opt-em">(1 = highest)</span></div>
        <div class="q-hint">For shared slots: lower number = higher priority when multiple consignors supply the same item.</div>
        <input type="number" class="text-input" id="priority" value="1" min="1" max="9" style="max-width:90px;">
      </div>

      <div class="question">
        <div class="q-label"><span class="q-num">F10</span> Notes <span class="opt-em">(optional)</span></div>
        <textarea id="notes" placeholder="Special terms, agreed exceptions, referral context, contact details…"></textarea>
      </div>
    </div>

    <!-- ── SECTION 4: Corp Donation ── -->
    <div class="section">
      <div class="section-label">Section 4 — Corp Donation <span class="opt-em">(optional)</span></div>

      <div class="question">
        <div class="q-label">Does this consignor wish to donate a portion of their share to the corporation?</div>
        <div class="q-hint">This is entirely optional and at the consignor's discretion. The donation is deducted from their share at each sale — it does not affect your commission.</div>
        <div class="radio-group">
          <label><input type="radio" name="corp_donation_opted" value="0" checked onchange="onDonationChange()"> No donation</label>
          <label><input type="radio" name="corp_donation_opted" value="1" onchange="onDonationChange()"> Yes — donate to corp</label>
        </div>
      </div>

      <div class="question" id="donation-pct-row" style="display:none;">
        <div class="q-label">Donation Percentage (%)</div>
        <div class="q-hint">What % of the consignor's share goes to the corporation each sale?</div>
        <input type="number" class="text-input" id="corp_donation_pct" value="5" min="0.1" max="100" step="0.1" style="max-width:110px;">
        <div class="field-note" id="donation-preview"></div>
      </div>
    </div>

    <!-- SUBMIT -->
    <div class="submit-wrap">
      <div class="err-msg" id="submit-err" style="display:none;text-align:center;margin-bottom:12px;">
        Please fix the highlighted fields above.
      </div>
      <button type="submit" class="btn-submit" id="submit-btn">Add Consignor</button>
      <div class="submit-note">Writes directly to mydatabase.db · visible in admin dashboard immediately</div>
    </div>

  </form>

  <!-- SUCCESS -->
  <div id="success-screen">
    <div class="success-top">
      <div class="check-icon">✓</div>
      <h2>Consignor Added</h2>
      <p class="sub" id="success-detail"></p>
      <p class="saved-path" id="saved-path"></p>
    </div>

    <div class="agreement-card">
      <div class="agreement-card-header">
        <span>Discord Agreement Message</span>
        <button class="btn-copy" id="copy-btn" onclick="copyAgreement()">Copy to Clipboard</button>
      </div>
      <textarea id="discord-text" readonly spellcheck="false"></textarea>
    </div>

    <button class="btn-another" onclick="resetForm()">+ Add Another Consignor</button>
  </div>

</div>
<script>
  // ── Corp donation toggle ───────────────────────────────────────────────────
  function onDonationChange() {
    const opted = document.querySelector('input[name=corp_donation_opted]:checked').value === '1';
    document.getElementById('donation-pct-row').style.display = opted ? '' : 'none';
    if (opted) updateDonationPreview();
  }
  function updateDonationPreview() {
    const pct = parseFloat(document.getElementById('corp_donation_pct').value);
    const el  = document.getElementById('donation-preview');
    if (!isNaN(pct) && pct > 0) {
      el.textContent = pct.toFixed(1) + '% of consignor\'s share goes to the corp each sale.';
      el.className   = 'field-note ok';
    }
  }
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('corp_donation_pct')?.addEventListener('input', updateDonationPreview);
  });

  // ── Commission preview ─────────────────────────────────────────────────────
  function updateCommPreview() {
    const v   = parseFloat(document.getElementById('commission_pct').value);
    const el  = document.getElementById('comm-preview');
    if (!isNaN(v) && v >= 0 && v <= 100) {
      el.textContent = 'Consignor receives: ' + (100 - v).toFixed(1) + '%';
      el.className   = 'field-note ok';
    } else {
      el.textContent = 'Enter a valid commission %';
      el.className   = 'field-note warn';
    }
  }

  // ── Item select ────────────────────────────────────────────────────────────
  function onItemChange() {
    const has = !!document.getElementById('item_select').value;
    document.getElementById('fetch-price-btn').disabled = !has;
    document.getElementById('price-note').textContent = '';
  }

  // ── Fetch latest market price ──────────────────────────────────────────────
  async function fetchPrice() {
    const type_id = document.getElementById('item_select').value;
    if (!type_id) return;
    const btn  = document.getElementById('fetch-price-btn');
    const note = document.getElementById('price-note');
    btn.textContent = '…';
    btn.disabled    = true;
    try {
      const resp = await fetch('/price/' + type_id);
      const data = await resp.json();
      if (data.price) {
        document.getElementById('list_price').value = data.price.toFixed(2);
        note.textContent  = 'Fetched: ' + data.price.toLocaleString(undefined, {maximumFractionDigits:2}) + ' ISK (latest snapshot)';
        note.className    = 'field-note ok';
      } else {
        note.textContent = 'No price snapshot on file for this item yet.';
        note.className   = 'field-note warn';
      }
    } catch {
      note.textContent = 'Request failed.';
      note.className   = 'field-note warn';
    }
    btn.textContent = 'Fetch Current';
    btn.disabled    = false;
  }

  // ── Submit ─────────────────────────────────────────────────────────────────
  document.getElementById('onboard-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const charName   = document.getElementById('character_name').value.trim();
    const itemSel    = document.getElementById('item_select');
    const commPctVal = document.getElementById('commission_pct').value;
    const commPct    = parseFloat(commPctVal);
    const startDate  = document.getElementById('start_date').value;

    // Clear errors
    document.querySelectorAll('.err-msg').forEach(el => {
      el.classList.remove('show'); el.style.display = '';
    });
    document.getElementById('submit-err').style.display = 'none';

    let valid = true;
    if (!charName)               { show('f1-err'); valid = false; }
    if (!itemSel.value)          { show('f2-err'); valid = false; }
    if (isNaN(commPct))          { show('f4-err'); valid = false; }

    if (!valid) {
      document.getElementById('submit-err').style.display = 'block';
      document.querySelector('.err-msg.show')?.scrollIntoView({ behavior:'smooth', block:'center' });
      return;
    }

    const selectedOpt = itemSel.options[itemSel.selectedIndex];
    const itemName    = selectedOpt.getAttribute('data-name') || selectedOpt.text;
    const listPrice   = document.getElementById('list_price').value;
    const maxUnits    = document.getElementById('max_units').value;

    const donOpted = document.querySelector('input[name=corp_donation_opted]:checked').value === '1';
    const donPct   = donOpted ? (parseFloat(document.getElementById('corp_donation_pct').value) || 0) : 0;

    const payload = {
      character_name:       charName,
      item_type_id:         parseInt(itemSel.value),
      item_name:            itemName,
      slot_type:            document.querySelector('input[name=slot_type]:checked').value,
      commission_pct:       commPct,
      list_price:           listPrice  ? parseFloat(listPrice) : null,
      max_units:            maxUnits   ? parseInt(maxUnits)    : null,
      start_date:           startDate,
      demand_tier:          document.querySelector('input[name=demand_tier]:checked').value,
      priority:             parseInt(document.getElementById('priority').value) || 1,
      notes:                document.getElementById('notes').value.trim(),
      corp_donation_opted:  donOpted ? 1 : 0,
      corp_donation_pct:    donPct,
    };

    const btn = document.getElementById('submit-btn');
    btn.disabled    = true;
    btn.textContent = 'Saving…';

    try {
      const resp   = await fetch('/submit', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });
      const result = await resp.json();
      if (result.status === 'ok') {
        document.getElementById('onboard-form').style.display = 'none';
        const slotLabel = payload.slot_type === 'exclusive' ? 'Exclusive slot' : 'Shared slot';
        const commLabel = (100 - commPct).toFixed(1) + '% to consignor';
        document.getElementById('success-detail').textContent =
          charName + ' — ' + itemName + ' — ' + slotLabel + ' — ' + commLabel;
        document.getElementById('discord-text').value = result.discord_msg || '';
        document.getElementById('saved-path').textContent =
          result.saved_to ? 'Saved to consignor_agreements/' + result.saved_to : '';
        document.getElementById('copy-btn').textContent = 'Copy to Clipboard';
        document.getElementById('copy-btn').classList.remove('copied');
        document.getElementById('success-screen').style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } else {
        alert('Database error:\n' + result.message);
        btn.disabled    = false;
        btn.textContent = 'Add Consignor';
      }
    } catch (err) {
      alert('Request failed: ' + err.message);
      btn.disabled    = false;
      btn.textContent = 'Add Consignor';
    }
  });

  function show(id) { document.getElementById(id).classList.add('show'); }

  function copyAgreement() {
    const ta  = document.getElementById('discord-text');
    const btn = document.getElementById('copy-btn');
    navigator.clipboard.writeText(ta.value).then(() => {
      btn.textContent = '✓ Copied!';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = 'Copy to Clipboard';
        btn.classList.remove('copied');
      }, 2500);
    }).catch(() => {
      ta.select();
      document.execCommand('copy');
    });
  }

  // ── Reset for another entry ────────────────────────────────────────────────
  function resetForm() {
    document.getElementById('onboard-form').reset();
    updateCommPreview();
    document.getElementById('price-note').textContent = '';
    document.getElementById('fetch-price-btn').disabled = true;
    document.getElementById('success-screen').style.display = 'none';
    document.getElementById('onboard-form').style.display   = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
</script>
</body>
</html>"""


# ── HTTP handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    _select_html: str = ''
    _today:       str = ''

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            html = HTML_TEMPLATE.replace('{{SELECT_OPTIONS}}', Handler._select_html)
            html = html.replace('{{TODAY}}', Handler._today)
            self._respond(200, 'text/html; charset=utf-8', html.encode())
        elif path.startswith('/price/'):
            try:
                type_id = int(path.rsplit('/', 1)[-1])
                price   = get_current_price(type_id)
                self._respond(200, 'application/json',
                              json.dumps({'price': price}).encode())
            except Exception:
                self._respond(400, 'application/json', b'{"error":"bad request"}')
        else:
            self._respond(404, 'text/plain', b'Not Found')

    def do_POST(self):
        if self.path != '/submit':
            self._respond(404, 'text/plain', b'Not Found')
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))
            conn   = sqlite3.connect(DB_PATH)
            don_opted = int(data.get('corp_donation_opted', 0))
            don_pct   = float(data.get('corp_donation_pct', 0)) if don_opted else 0.0
            conn.execute(
                '''INSERT INTO consignors
                   (character_name, item_name, item_type_id, list_price,
                    consignor_pct, start_date, active, notes,
                    slot_type, slot_priority, max_units, demand_tier, current_qty,
                    corp_donation_opted, corp_donation_pct)
                   VALUES (?,?,?,?,?,?,1,?,?,?,?,?,0,?,?)''',
                (
                    data['character_name'],
                    data['item_name'],
                    int(data['item_type_id']),
                    data.get('list_price'),
                    round(100.0 - float(data['commission_pct']), 4),
                    data['start_date'],
                    data.get('notes') or '',
                    data.get('slot_type', 'shared'),
                    int(data.get('priority', 1)),
                    data.get('max_units'),
                    data.get('demand_tier', 'medium'),
                    don_opted,
                    don_pct,
                )
            )
            conn.commit()
            conn.close()

            consignor_pct = round(100.0 - float(data['commission_pct']), 4)
            discord_msg   = generate_agreement_text(data, consignor_pct, bool(don_opted), don_pct)
            filepath      = save_agreement_file(
                data['character_name'], data['item_name'], data['start_date'], discord_msg
            )

            body = json.dumps({
                'status':      'ok',
                'discord_msg': discord_msg,
                'saved_to':    os.path.basename(filepath),
            }).encode()
            self._respond(200, 'application/json', body)
        except Exception as ex:
            body = json.dumps({'status': 'error', 'message': str(ex)}).encode()
            self._respond(200, 'application/json', body)

    def _respond(self, code, ct, body: bytes):
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass   # suppress console noise


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    Handler._select_html = build_select_options()
    Handler._today       = date.today().isoformat()

    server = HTTPServer(('127.0.0.1', PORT), Handler)
    url    = f'http://localhost:{PORT}/'
    print(f'Consignor onboarding form → {url}')
    print('Press Ctrl+C to stop.')
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped.')


if __name__ == '__main__':
    main()
