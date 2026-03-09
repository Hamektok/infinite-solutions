"""
Generate an interactive HTML report of TEST Buyback competitor stock history.
Reads from test_comp_snapshots table, produces intel_report.html, opens in browser.
"""

import json
import os
import re
import sqlite3
import webbrowser
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mydatabase.db')
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'intel_report.html')

TOP_N = 15   # items shown in line chart per category

MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

COLOURS = [
    '#00d9ff', '#00ff88', '#ffd700', '#ff8844', '#cc66ff',
    '#ff4488', '#44ffcc', '#ffee44', '#88aaff', '#ff6666',
    '#66ffaa', '#ffaa00', '#00aaff', '#ff88cc', '#aaffee',
]

TAB_ORDER  = ['PI', 'Minerals, Gas', 'Moon Goo, Composites', 'Ore, Ice']
TAB_IDS    = ['pi', 'minerals', 'moongoo', 'oreice']
TAB_ACCENT = ['#cc66ff', '#00d9ff', '#ffd700', '#00ff88']

# Partner program items (highlighted gold in tables)
OUR_ITEMS = {'Wetware Mainframe', 'Proteins'}


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT tab_label, item_name, snapshot_timestamp, quantity
        FROM test_comp_snapshots
        ORDER BY tab_label, item_name, snapshot_timestamp
    """)
    rows = cur.fetchall()
    conn.close()

    data = defaultdict(lambda: defaultdict(list))
    for tab, item, ts, qty in rows:
        data[tab][item].append((ts, qty))
    return data


def short_ts(ts):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})', ts)
    if not m:
        return ts
    _, mo, day, hr, mn = m.groups()
    return f"{MONTHS[int(mo)]} {day} {hr}:{mn}"


def swing_pct(series):
    qtys = [q for _, q in series]
    if not qtys or max(qtys) == 0:
        return 0
    return (max(qtys) - min(qtys)) / max(qtys) * 100


def trend_pct(series):
    qtys = [q for _, q in series]
    if len(qtys) < 4:
        return 0
    mid = len(qtys) // 2
    first = sum(qtys[:mid]) / mid
    second = sum(qtys[mid:]) / (len(qtys) - mid)
    return (second - first) / first * 100 if first else 0


# ── Chart data builders ───────────────────────────────────────────────────────

def build_line_chart(item_series, top_n=TOP_N):
    ranked = sorted(item_series.items(), key=lambda x: swing_pct(x[1]), reverse=True)
    selected = ranked[:top_n]
    if not selected:
        return None
    all_ts = sorted({ts for _, s in selected for ts, _ in s})
    labels = [short_ts(ts) for ts in all_ts]
    datasets = []
    for i, (name, series) in enumerate(selected):
        ts_map = {ts: qty for ts, qty in series}
        colour = COLOURS[i % len(COLOURS)]
        datasets.append({
            'label': name,
            'data': [ts_map.get(ts) for ts in all_ts],
            'borderColor': colour,
            'backgroundColor': colour + '22',
            'borderWidth': 2,
            'pointRadius': 2,
            'pointHoverRadius': 5,
            'tension': 0.3,
            'spanGaps': True,
        })
    return {'labels': labels, 'datasets': datasets}


def build_overview_bar(data):
    rows = []
    for tab, item_series in data.items():
        for item, series in item_series.items():
            sw = swing_pct(series)
            if sw > 5:
                rows.append((item, tab, sw))
    rows.sort(key=lambda x: x[2], reverse=True)
    top = rows[:20]
    tab_colour = dict(zip(TAB_ORDER, TAB_ACCENT))
    return {
        'labels':  [r[0] for r in top],
        'swings':  [round(r[2], 1) for r in top],
        'colours': [tab_colour.get(r[1], '#888') for r in top],
        'tabs':    [r[1] for r in top],
    }


# ── HTML builders ─────────────────────────────────────────────────────────────

def breakdown_table(item_series):
    rows_html = ''
    items = sorted(item_series.items(), key=lambda x: -sum(q for _, q in x[1]) / len(x[1]))
    for name, series in items:
        avg  = sum(q for _, q in series) / len(series)
        last = series[-1][1]
        sw   = swing_pct(series)
        tr   = trend_pct(series)
        arrow = '▲' if tr > 5 else ('▼' if tr < -5 else '—')
        tcls  = 'up' if tr > 5 else ('dn' if tr < -5 else 'fl')
        hl    = ' class="hl"' if name in OUR_ITEMS else ''
        star  = '  ★' if name in OUR_ITEMS else ''
        rows_html += (
            f'<tr{hl}>'
            f'<td>{name}{star}</td>'
            f'<td class="num">{avg:,.0f}</td>'
            f'<td class="num">{last:,}</td>'
            f'<td class="num">{sw:.1f}%</td>'
            f'<td class="t {tcls}">{arrow} {abs(tr):.1f}%</td>'
            f'</tr>\n'
        )
    return f'''
<table>
  <thead>
    <tr>
      <th>Item</th>
      <th class="r">Avg Qty</th>
      <th class="r">Latest</th>
      <th class="r">Swing</th>
      <th class="r">4-Day Trend</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>'''


def generate_html(data):
    snap_timestamps = {ts for tab in data.values() for s in tab.values() for ts, _ in s}
    snap_count = len(snap_timestamps)
    min_ts = short_ts(min(snap_timestamps))
    max_ts = short_ts(max(snap_timestamps))

    overview_json = json.dumps(build_overview_bar(data))

    # Build per-tab content
    nav_btns   = ['<button class="nav active" id="btn-overview" onclick="show(\'overview\')">Overview</button>']
    panels     = []
    chart_inits = []

    # Overview panel
    panels.append('''<div class="panel active" id="panel-overview">
  <h2>Top 20 Most Volatile Items &mdash; All Categories</h2>
  <p class="sub">Items with the largest quantity swings over the collection period, colour-coded by category.</p>
  <div class="chart-box" style="height:440px">
    <canvas id="chart-overview"></canvas>
  </div>
  <div class="legend" style="margin-top:12px">
''' + ''.join(
        f'<span class="dot" style="background:{c}"></span>{t}  '
        for t, c in zip(TAB_ORDER, TAB_ACCENT)
    ) + '''
  </div>
</div>''')

    chart_inits.append(f'''
  (function(){{
    const sd = {overview_json};
    new Chart(document.getElementById('chart-overview'), {{
      type: 'bar',
      data: {{
        labels: sd.labels,
        datasets: [{{ label: 'Swing %', data: sd.swings,
          backgroundColor: sd.colours, borderColor: sd.colours,
          borderWidth:1, borderRadius:3 }}]
      }},
      options: {{
        responsive:true, maintainAspectRatio:false, indexAxis:'y',
        plugins:{{
          legend:{{display:false}},
          tooltip:{{
            backgroundColor:'#0a1a2e', borderColor:'#1a3a5a', borderWidth:1,
            titleColor:'#00d9ff', bodyColor:'#b0c8d8',
            callbacks:{{ label: c => ` Swing: ${{c.parsed.x}}%  |  ${{sd.tabs[c.dataIndex]}}` }}
          }}
        }},
        scales:{{
          x:{{ ticks:{{color:'#6699aa', callback:v=>v+'%'}}, grid:{{color:'#0d1e2e'}} }},
          y:{{ ticks:{{color:'#8899aa',font:{{size:11}}}}, grid:{{color:'#0d1e2e'}} }}
        }}
      }}
    }});
  }})();''')

    for tab_label, tab_id, accent in zip(TAB_ORDER, TAB_IDS, TAB_ACCENT):
        item_series = data.get(tab_label, {})
        item_count  = len(item_series)
        shown       = min(TOP_N, item_count)

        nav_btns.append(
            f'<button class="nav" id="btn-{tab_id}" onclick="show(\'{tab_id}\')" '
            f'style="--accent:{accent}">{tab_label}</button>'
        )

        chart_data = build_line_chart(item_series)
        table_html = breakdown_table(item_series) if item_series else '<p class="sub">No data.</p>'

        if chart_data:
            cd_json = json.dumps(chart_data)
            chart_block = f'''
  <div class="chart-box">
    <canvas id="chart-{tab_id}"></canvas>
  </div>'''
            chart_inits.append(f'''
  makeLineChart('chart-{tab_id}', {cd_json});''')
        else:
            chart_block = '<p class="sub">No chart data available.</p>'

        panels.append(f'''<div class="panel" id="panel-{tab_id}">
  <h2 style="color:{accent}">{tab_label}</h2>
  <p class="sub">Top {shown} most volatile items (chart) &mdash; all {item_count} items (table below).
     ★ = partner program item.</p>
  {chart_block}
  <div class="tbl-wrap">
    {table_html}
  </div>
</div>''')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>TEST Buyback — Competitor Intel</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:#060e18; color:#b0c8d8; font-family:'Segoe UI',sans-serif; font-size:14px; }}

header {{
  background:linear-gradient(135deg,#0a1a2e,#061224);
  border-bottom:1px solid #1a3a5a;
  padding:16px 28px;
  display:flex; align-items:baseline; gap:16px;
}}
header h1 {{ font-size:18px; color:#00d9ff; letter-spacing:1px; font-weight:600; }}
header .meta {{ font-size:12px; color:#445566; }}

/* Sidebar nav */
.layout {{ display:flex; min-height:calc(100vh - 53px); }}
nav {{
  width:190px; flex-shrink:0;
  background:#080f1a;
  border-right:1px solid #1a3a5a;
  padding:16px 0;
}}
button.nav {{
  display:block; width:100%;
  background:none; border:none;
  color:#556677; text-align:left;
  padding:10px 20px; font-size:13px;
  cursor:pointer;
  border-left:3px solid transparent;
  transition:all 0.15s;
  --accent:#00d9ff;
}}
button.nav:hover {{ color:#aabbcc; background:#0a1525; }}
button.nav.active {{
  color:var(--accent, #00d9ff);
  border-left-color:var(--accent, #00d9ff);
  background:#0d1e30;
  font-weight:600;
}}

/* Main content */
main {{ flex:1; padding:28px 32px; overflow-y:auto; }}
.panel {{ display:none; }}
.panel.active {{ display:block; }}
h2 {{ font-size:15px; color:#00d9ff; border-bottom:1px solid #1a3a5a;
      padding-bottom:8px; margin-bottom:14px; letter-spacing:.4px; }}
.sub {{ font-size:12px; color:#445566; font-style:italic; margin-bottom:14px; }}

.chart-box {{
  background:#080f1a; border:1px solid #1a3a5a; border-radius:6px;
  padding:20px; height:380px; margin-bottom:28px;
}}
.chart-box canvas {{ max-height:340px; }}

/* Table */
.tbl-wrap {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{
  text-align:left; color:#445566; font-size:11px;
  letter-spacing:.5px; text-transform:uppercase;
  padding:7px 12px; border-bottom:1px solid #1a3a5a;
}}
th.r {{ text-align:right; }}
td {{ padding:6px 12px; border-bottom:1px solid #0d1e2e; }}
tr:hover td {{ background:#0a1a2e; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; color:#7799aa; }}
td.t {{ text-align:right; font-weight:600; }}
td.t.up {{ color:#00ff88; }}
td.t.dn {{ color:#ff6666; }}
td.t.fl {{ color:#334455; }}
tr.hl td {{ color:#ffd700; }}
tr.hl td:first-child {{ font-weight:600; }}

.legend {{ font-size:12px; color:#6699aa; display:flex; flex-wrap:wrap; gap:14px; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%;
        margin-right:5px; vertical-align:middle; }}
</style>
</head>
<body>
<header>
  <h1>TEST Buyback &mdash; Competitor Intel</h1>
  <span class="meta">{snap_count} snapshots &nbsp;&bull;&nbsp; {min_ts} &rarr; {max_ts} UTC &nbsp;&bull;&nbsp; every 2 hrs</span>
</header>
<div class="layout">
  <nav>
    {''.join(nav_btns)}
  </nav>
  <main>
    {''.join(panels)}
  </main>
</div>

<script>
Chart.defaults.color = '#556677';
Chart.defaults.borderColor = '#1a3a5a';

function show(id) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + id).classList.add('active');
  document.getElementById('btn-' + id).classList.add('active');
}}

function makeLineChart(id, cd) {{
  const ctx = document.getElementById(id);
  if (!ctx) return;
  new Chart(ctx, {{
    type: 'line',
    data: cd,
    options: {{
      responsive:true, maintainAspectRatio:false,
      interaction:{{ mode:'index', intersect:false }},
      plugins:{{
        legend:{{
          position:'bottom',
          labels:{{ font:{{size:11}}, color:'#6699aa', boxWidth:12, padding:10 }}
        }},
        tooltip:{{
          backgroundColor:'#0a1a2e', borderColor:'#1a3a5a', borderWidth:1,
          titleColor:'#00d9ff', bodyColor:'#b0c8d8',
          callbacks:{{ label: c => ` ${{c.dataset.label}}: ${{(c.parsed.y??0).toLocaleString()}}` }}
        }}
      }},
      scales:{{
        x:{{
          ticks:{{ font:{{size:10}}, maxRotation:45, color:'#445566', maxTicksLimit:24 }},
          grid:{{ color:'#0d1e2e' }}
        }},
        y:{{
          ticks:{{
            color:'#6699aa',
            callback: v => v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?(v/1e3).toFixed(0)+'K':v
          }},
          grid:{{ color:'#0d1e2e' }}
        }}
      }}
    }}
  }});
}}

{''.join(chart_inits)}
</script>
</body>
</html>"""
    return html


def main():
    print("Loading snapshot data...")
    data = load_data()
    total = sum(len(s) for tab in data.values() for s in tab.values())
    items = sum(len(tab) for tab in data.values())
    print(f"  {total:,} data points, {items} items across {len(data)} tabs")

    print("Generating report...")
    html = generate_html(data)

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Written: {OUT_PATH}")

    webbrowser.open(f'file:///{OUT_PATH.replace(os.sep, "/")}')
    print("  Opened in browser.")


if __name__ == '__main__':
    main()
