"""
Build gank_watchlist.html — standalone public watchlist page.
Reads gank_watchlist from DB and embeds data as static HTML.
No navigation links — shared URL for corp members.
"""
import sqlite3, os
from datetime import datetime, timezone

DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mydatabase.db')
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gank_watchlist.html')

# ── Load data from DB ─────────────────────────────────────────────────────────
FREIGHTERS      = {'Charon','Fenrir','Obelisk','Providence','Bowhead','Avalanche'}
JUMP_FREIGHTERS = {'Rhea','Nomad','Anshar','Ark'}

def ship_cats(ship_set):
    cats = set()
    for s in ship_set:
        if s in FREIGHTERS:      cats.add('fr')
        if s in JUMP_FREIGHTERS: cats.add('jf')
    return ' '.join(sorted(cats)) if cats else 'other'

build_ts = datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')

ganker_alliances = []
ganker_corps     = []
ganker_chars     = []
cyno_chars       = []

try:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT w.entity_name, w.entity_type, w.tag, w.kill_count,
               GROUP_CONCAT(DISTINCT k.victim_ship_name) as ships
        FROM gank_watchlist w
        LEFT JOIN gank_kill_log k ON k.entity_id = w.entity_id
        GROUP BY w.entity_id
        ORDER BY w.kill_count DESC, w.entity_name COLLATE NOCASE
    """).fetchall()
    conn.close()

    for name, etype, tag, kills, ships_csv in rows:
        ship_set = set(ships_csv.split(',')) if ships_csv else set()
        cats     = ship_cats(ship_set)
        label    = (name or '(unknown)', kills or 0, cats)
        if tag == 'cyno_alt':
            cyno_chars.append(label)
        elif etype == 'alliance':
            ganker_alliances.append(label)
        elif etype == 'corporation':
            ganker_corps.append(label)
        else:
            ganker_chars.append(label)
except Exception as e:
    print(f'Warning: could not load DB data: {e}')

total_entries = len(ganker_alliances) + len(ganker_corps) + len(ganker_chars) + len(cyno_chars)


def name_list(entries, empty_msg='No entries yet.'):
    if not entries:
        return f'<p class="empty">{empty_msg}</p>'
    def esc(s):
        return s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
    items = ''.join(
        f'<li data-ships="{cats}">'
        f'<span class="name">{esc(n)}</span>'
        f'<span class="kills">{k}x</span>'
        f'<button class="copy-btn" data-name="{esc(n)}" title="Copy to clipboard">'
        f'<svg viewBox="0 0 16 16" fill="currentColor"><path d="M4 2a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V2zm2-1a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1H6z"/>'
        f'<path d="M2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1v-1H9v1H2V6h1V5H2z"/></svg>'
        f'</button>'
        f'</li>'
        for n, k, cats in entries
    )
    return f'<ul class="namelist">{items}</ul>'


ganker_alliance_html = name_list(ganker_alliances)
ganker_corp_html     = name_list(ganker_corps)
ganker_char_html     = name_list(ganker_chars)
cyno_char_html       = name_list(cyno_chars)


html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ganker Watchlist &mdash; Infinite Solutions</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;600;700&display=swap');
:root{{
  --bg:#09090d;--panel:#0d1018;--panel2:#111520;
  --border:#1e2535;--text:#d8e0f0;--dim:#5a6880;
  --col-alliance:#e05050;
  --col-corp:#5588e0;
  --col-char:#44cc88;
  --col-cyno:#e0a030;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;
  padding:24px 14px 60px;display:flex;justify-content:center;}}
.page{{width:100%;max-width:1100px;}}
.hdr{{text-align:center;margin-bottom:20px;}}
.hdr h1{{font-family:'Orbitron',sans-serif;font-size:1.5em;font-weight:900;
  letter-spacing:4px;background:linear-gradient(135deg,#ff9944,#ffcc44);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.hdr .sub{{color:var(--dim);font-size:.82em;letter-spacing:3px;text-transform:uppercase;margin-top:6px;}}
.hdr .meta{{color:var(--dim);font-size:.78em;margin-top:5px;}}
.desc{{color:var(--dim);font-size:.88em;line-height:1.6;margin-bottom:20px;
  padding:12px 16px;background:var(--panel2);border:1px solid var(--border);border-radius:6px;}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px;}}
.box{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:18px 20px;}}
.box-title{{font-family:'Orbitron',sans-serif;font-size:.58em;font-weight:700;
  letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;padding-bottom:8px;
  border-bottom:1px solid var(--border);}}
.box-title.alliance{{color:var(--col-alliance);}}
.box-title.corp{{color:var(--col-corp);}}
.box-title.char{{color:var(--col-char);}}
.box-title.cyno{{color:var(--col-cyno);}}
.box-count{{font-size:.75em;color:var(--dim);margin-bottom:10px;}}
ul.namelist{{list-style:none;}}
ul.namelist li{{display:flex;align-items:center;gap:6px;
  padding:4px 0;font-size:.9em;border-bottom:1px solid rgba(30,37,53,0.5);}}
ul.namelist li:last-child{{border-bottom:none;}}
ul.namelist .name{{flex:1;word-break:break-word;}}
ul.namelist .kills{{flex-shrink:0;font-size:.78em;color:var(--dim);min-width:24px;text-align:right;}}
.copy-btn{{flex-shrink:0;background:none;border:none;cursor:pointer;
  color:var(--dim);padding:2px;line-height:0;border-radius:3px;
  transition:color .15s;}}
.copy-btn:hover{{color:var(--text);}}
.copy-btn.copied{{color:#44cc88;}}
.copy-btn svg{{width:13px;height:13px;}}
p.empty{{color:var(--dim);font-size:.82em;font-style:italic;}}
footer{{text-align:center;color:var(--dim);font-size:.76em;margin-top:28px;letter-spacing:1px;}}
@media(max-width:950px){{.grid{{grid-template-columns:repeat(2,1fr);}}}}
@media(max-width:500px){{.grid{{grid-template-columns:1fr;}}}}
.filter-bar{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  margin-bottom:16px;padding:10px 14px;
  background:var(--panel2);border:1px solid var(--border);border-radius:6px;}}
.filter-bar .filter-label{{color:var(--dim);font-size:.78em;letter-spacing:2px;
  text-transform:uppercase;margin-right:4px;}}
.filter-btn{{background:var(--panel);border:1px solid var(--border);color:var(--dim);
  font-family:'Rajdhani',sans-serif;font-size:.85em;font-weight:600;
  padding:5px 14px;border-radius:4px;cursor:pointer;letter-spacing:1px;
  transition:background .15s,color .15s,border-color .15s;}}
.filter-btn:hover{{color:var(--text);border-color:#3a4555;}}
.filter-btn.active{{background:#1a2535;color:#ffcc44;border-color:#ffcc44;}}
.filter-count{{margin-left:auto;color:var(--dim);font-size:.78em;}}
</style>
</head>
<body>
<div class="page">

  <div class="hdr">
    <h1>GANKER WATCHLIST</h1>
    <div class="sub">Infinite Solutions</div>
    <div class="meta">{total_entries:,} entities tracked &mdash; updated {build_ts}</div>
  </div>

  <div class="filter-bar">
    <span class="filter-label">Filter by victim ship:</span>
    <button class="filter-btn active" data-filter="all">All</button>
    <button class="filter-btn" data-filter="fr">Freighter</button>
    <button class="filter-btn" data-filter="jf">Jump Freighter</button>
    <span class="filter-count" id="filter-count"></span>
  </div>

  <div class="desc">
    This list contains characters, corporations, and alliances observed ganking haulers
    or freighters in high-security space, or lighting cynos in low-sec.
    Entries are sorted by kill count &mdash; higher priority targets appear first.
    <br><br>
    If you believe an entry has been added in error or should be removed, contact
    <strong style="color:var(--text);">Hamektok Hakaari</strong> in-game.
  </div>

  <div class="grid">

    <div class="box">
      <div class="box-title alliance">&#9760; Alliances</div>
      <div class="box-count">{len(ganker_alliances)} entries</div>
      {ganker_alliance_html}
    </div>

    <div class="box">
      <div class="box-title corp">&#9760; Corporations</div>
      <div class="box-count">{len(ganker_corps)} entries</div>
      {ganker_corp_html}
    </div>

    <div class="box">
      <div class="box-title char">&#9760; Characters</div>
      <div class="box-count">{len(ganker_chars)} entries</div>
      {ganker_char_html}
    </div>

    <div class="box">
      <div class="box-title cyno">&#9650; Cyno Alts</div>
      <div class="box-count">{len(cyno_chars)} entries</div>
      {cyno_char_html}
    </div>

  </div>

  <footer>
    Infinite Solutions &mdash; Contact: Hamektok Hakaari &mdash; Last updated: {build_ts}
  </footer>

</div>
<script>
document.querySelectorAll('.copy-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    navigator.clipboard.writeText(btn.dataset.name).then(() => {{
      btn.classList.add('copied');
      setTimeout(() => btn.classList.remove('copied'), 1200);
    }});
  }});
}});

// ── Ship type filter ──────────────────────────────────────────────────────────
const activeFilters = new Set();

function applyFilter() {{
  const all = activeFilters.size === 0 || activeFilters.has('all');
  let visible = 0;
  document.querySelectorAll('ul.namelist li').forEach(li => {{
    const ships = li.dataset.ships || '';
    const show  = all || [...activeFilters].some(f => ships.split(' ').includes(f));
    li.style.display = show ? '' : 'none';
    if (show) visible++;
  }});
  const total = document.querySelectorAll('ul.namelist li').length;
  document.getElementById('filter-count').textContent =
    all ? '' : visible + ' of {total_entries} shown';
}}

document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const f = btn.dataset.filter;
    if (f === 'all') {{
      activeFilters.clear();
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    }} else {{
      activeFilters.delete('all');
      document.querySelector('.filter-btn[data-filter="all"]').classList.remove('active');
      if (activeFilters.has(f)) {{
        activeFilters.delete(f);
        btn.classList.remove('active');
        if (activeFilters.size === 0) {{
          document.querySelector('.filter-btn[data-filter="all"]').classList.add('active');
        }}
      }} else {{
        activeFilters.add(f);
        btn.classList.add('active');
      }}
    }}
    applyFilter();
  }});
}});
</script>
</body>
</html>"""

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Built {OUT_PATH}')
print(f'  Ganker alliances:  {len(ganker_alliances)}')
print(f'  Ganker corps:      {len(ganker_corps)}')
print(f'  Ganker characters: {len(ganker_chars)}')
print(f'  Cyno alts:         {len(cyno_chars)}')
print(f'  Total:             {total_entries}')
