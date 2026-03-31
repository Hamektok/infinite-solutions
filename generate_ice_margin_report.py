"""
generate_ice_margin_report.py
Generates a standalone HTML ice ore margin analysis report for LX-ZOJ.
"""

import sys
import io
import sqlite3
import json
import os
import webbrowser
from datetime import datetime, timedelta, timezone
from math import floor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── Paths ────────────────────────────────────────────────────────────────────
DB_PATH  = os.path.join(os.path.dirname(__file__), 'mydatabase.db')
OUT_PATH = os.path.join(os.path.dirname(__file__), 'ice_margin_report.html')

# ── Type ID Constants ────────────────────────────────────────────────────────
ICE_COMP = [
    28433,  # Compressed Blue Ice
    28434,  # Compressed Clear Icicle
    28435,  # Compressed Dark Glitter
    28437,  # Compressed Gelidus
    28438,  # Compressed Glacial Mass
    28439,  # Compressed Glare Crust
    28440,  # Compressed Krystallos
    28444,  # Compressed White Glaze
    28436,  # Compressed Clear Icicle IV-Grade
    28441,  # Compressed White Glaze IV-Grade
    28442,  # Compressed Glacial Mass IV-Grade
    28443,  # Compressed Blue Ice IV-Grade
]

ICE_PRODUCTS = [
    (16272, 'Heavy Water'),
    (16273, 'Liquid Ozone'),
    (16274, 'Helium Isotopes'),
    (16275, 'Strontium Clathrates'),
    (17887, 'Oxygen Isotopes'),
    (17888, 'Nitrogen Isotopes'),
    (17889, 'Hydrogen Isotopes'),
]

ALL_PRODUCT_IDS = [pid for pid, _ in ICE_PRODUCTS]
PRODUCT_NAME    = {pid: name for pid, name in ICE_PRODUCTS}

# Ice family names (base name without grade suffix)
ICE_FAMILY_MAP = {
    28433: 'Blue Ice',
    28434: 'Clear Icicle',
    28435: 'Dark Glitter',
    28437: 'Gelidus',
    28438: 'Glacial Mass',
    28439: 'Glare Crust',
    28440: 'Krystallos',
    28444: 'White Glaze',
    28436: 'Clear Icicle',    # IV-Grade variant
    28441: 'White Glaze',     # IV-Grade variant
    28442: 'Glacial Mass',    # IV-Grade variant
    28443: 'Blue Ice',        # IV-Grade variant
}

# Ordered family list for display
FAMILY_ORDER = [
    'Blue Ice', 'Clear Icicle', 'Dark Glitter', 'Gelidus',
    'Glacial Mass', 'Glare Crust', 'Krystallos', 'White Glaze',
]


def ore_family(type_id: int, name: str) -> str:
    """Extract family name from type_id mapping or name string."""
    if type_id in ICE_FAMILY_MAP:
        return ICE_FAMILY_MAP[type_id]
    # Fallback: strip "Compressed " and grade suffixes
    n = name.replace('Compressed ', '')
    for suffix in [' IV-Grade', ' III-Grade', ' II-Grade']:
        n = n.replace(suffix, '')
    return n.strip()


def is_variant(name: str) -> bool:
    """Return True if this is a grade variant (not the base ore)."""
    return 'IV-Grade' in name or 'III-Grade' in name or 'II-Grade' in name


def variant_label(name: str) -> str:
    if 'IV-Grade' in name:
        return 'IV-Grade'
    if 'III-Grade' in name:
        return 'III-Grade'
    if 'II-Grade' in name:
        return 'II-Grade'
    return 'Base'


def price_near(daily_hist: dict, target_date: str) -> float | None:
    """Find closest available daily price at or before target_date."""
    if not daily_hist:
        return None
    candidates = [d for d in daily_hist if d <= target_date]
    if not candidates:
        candidates = sorted(daily_hist.keys())
    if not candidates:
        return None
    best = max(candidates)
    return daily_hist[best]


# ── Margin calculation ────────────────────────────────────────────────────────
def calc_margin(ore_price: float, volume: float, portion: int,
                yields: list, prod_jbv: dict, params: dict,
                prod_pcts: dict) -> tuple[float | None, float, float]:
    """
    Returns (margin_pct, total_cost, prod_value).
    margin = (prod_value - total_cost) / total_cost * 100  (ROI-based).
    """
    if ore_price is None or ore_price <= 0:
        return None, 0.0, 0.0

    buy_basis  = params['buy_basis']
    buy_pct    = params['buy_pct']
    broker_pct = params['broker_pct']
    ship_rate  = params['ship_rate']
    collat_pct = params['collat_pct']
    refine_eff = params['refine_eff']

    is_jsv = 'JSV' in buy_basis
    eff_broker = 0.0 if is_jsv else broker_pct

    ore_cost   = ore_price * buy_pct * portion
    ship_cost  = volume * portion * ship_rate
    collat     = ore_cost * collat_pct
    total_cost = ore_cost + (ore_cost * eff_broker) + ship_cost + collat

    prod_value = 0.0
    for mat in yields:
        mat_id = mat['materialTypeID']
        qty    = mat['quantity']
        jbv    = prod_jbv.get(mat_id)
        if jbv and jbv > 0:
            sell_pct = prod_pcts.get(mat_id, 0.95)
            prod_value += qty * refine_eff * jbv * sell_pct

    if prod_value <= 0 or total_cost <= 0:
        return None, total_cost, prod_value

    margin = (prod_value - total_cost) / total_cost * 100
    return margin, total_cost, prod_value


# ── Narrative generators ──────────────────────────────────────────────────────
def generate_ore_narrative(family: str, base_margin: float | None,
                           yields: list, prod_jbv_now: dict,
                           prod_jbv_30d: dict, prod_pcts: dict,
                           refine_eff: float, total_cost: float,
                           prod_value: float) -> str:
    """Generate 3-4 sentence analysis for a family card."""
    if base_margin is None:
        return f"{family} has insufficient price data for analysis."

    # Identify dominant product by ISK contribution
    contribs = []
    for mat in yields:
        mat_id = mat['materialTypeID']
        qty    = mat['quantity']
        jbv    = prod_jbv_now.get(mat_id)
        if jbv and jbv > 0:
            sell_pct = prod_pcts.get(mat_id, 0.95)
            isk = qty * refine_eff * jbv * sell_pct
            contribs.append((isk, PRODUCT_NAME.get(mat_id, str(mat_id)), mat_id))
    contribs.sort(reverse=True)

    if not contribs:
        return f"{family}: no product price data available."

    dom_isk, dom_name, dom_id = contribs[0]
    dom_pct = (dom_isk / prod_value * 100) if prod_value > 0 else 0

    # Trend for dominant product
    jbv_now = prod_jbv_now.get(dom_id)
    jbv_30d = prod_jbv_30d.get(dom_id)
    trend_txt = ''
    if jbv_now and jbv_30d and jbv_30d > 0:
        chg = (jbv_now - jbv_30d) / jbv_30d * 100
        if chg > 5:
            trend_txt = f"{dom_name} has risen {chg:.1f}% over the past 30 days, boosting returns."
        elif chg < -5:
            trend_txt = f"{dom_name} has fallen {abs(chg):.1f}% over the past 30 days, compressing margins."
        else:
            trend_txt = f"{dom_name} pricing has been stable over the past 30 days."
    else:
        trend_txt = f"{dom_name} historical data is limited."

    # Margin descriptor
    if base_margin >= 20:
        margin_desc = "excellent"
    elif base_margin >= 10:
        margin_desc = "solid"
    elif base_margin >= 5:
        margin_desc = "modest"
    elif base_margin >= 0:
        margin_desc = "thin"
    else:
        margin_desc = "negative"

    s1 = (f"The base {family} ore currently offers a {margin_desc} margin of "
          f"{base_margin:.1f}% ROI.")
    s2 = (f"{dom_name} is the dominant value driver, contributing "
          f"{dom_pct:.0f}% of batch revenue.")
    s3 = trend_txt

    # Secondary drivers
    secondary = []
    for isk, name, mat_id in contribs[1:]:
        if isk > 0 and prod_value > 0:
            pct = isk / prod_value * 100
            jbv_n = prod_jbv_now.get(mat_id)
            jbv_o = prod_jbv_30d.get(mat_id)
            if jbv_n and jbv_o and jbv_o > 0:
                chg = (jbv_n - jbv_o) / jbv_o * 100
                if abs(chg) > 5:
                    dir_word = "rising" if chg > 0 else "falling"
                    secondary.append(f"{name} ({pct:.0f}% of value, {dir_word} {abs(chg):.1f}%)")

    if secondary:
        s4 = "Secondary contributors: " + ", ".join(secondary) + "."
    else:
        s4 = ""

    parts = [s for s in [s1, s2, s3, s4] if s]
    return " ".join(parts)


def generate_exec_summary(analyses: list) -> dict:
    """Generate executive summary dict."""
    valid = [a for a in analyses if a['current_margin'] is not None]
    if not valid:
        return {'paragraph': 'Insufficient data for executive summary.',
                'best': None, 'worst': None, 'improved': None, 'declined': None}

    improving = sum(1 for a in valid if a.get('chg_30d') and a['chg_30d'] > 0)
    declining = sum(1 for a in valid if a.get('chg_30d') and a['chg_30d'] < 0)
    mixed     = len(valid) - improving - declining

    best  = max(valid, key=lambda a: a['current_margin'])
    worst = min(valid, key=lambda a: a['current_margin'])

    movers = [a for a in valid if a.get('chg_30d') is not None]
    most_improved   = max(movers, key=lambda a: a['chg_30d']) if movers else None
    biggest_decline = min(movers, key=lambda a: a['chg_30d']) if movers else None

    if improving > declining + mixed:
        trend_word = "improving broadly"
    elif declining > improving + mixed:
        trend_word = "declining across most ores"
    else:
        trend_word = "mixed"

    para_parts = [
        f"Ice ore margins are {trend_word} — "
        f"{improving} ores trending up, {declining} down, {mixed} flat over 30 days."
    ]

    para_parts.append(
        f"Best opportunity: {best['name']} at {best['current_margin']:.1f}% margin."
    )
    if worst['current_margin'] < 0:
        para_parts.append(
            f"Avoid {worst['name']} ({worst['current_margin']:.1f}% margin)."
        )

    if most_improved and most_improved['chg_30d'] and most_improved['chg_30d'] > 0:
        para_parts.append(
            f"Biggest 30-day gainer: {most_improved['name']} "
            f"(+{most_improved['chg_30d']:.1f} pp)."
        )
    if biggest_decline and biggest_decline['chg_30d'] and biggest_decline['chg_30d'] < 0:
        para_parts.append(
            f"Biggest 30-day loser: {biggest_decline['name']} "
            f"({biggest_decline['chg_30d']:.1f} pp)."
        )

    return {
        'paragraph':  " ".join(para_parts),
        'best':       {'name': best['name'],  'value': best['current_margin']},
        'worst':      {'name': worst['name'], 'value': worst['current_margin']},
        'improved':   ({'name': most_improved['name'],   'value': most_improved['chg_30d']}
                       if most_improved else None),
        'declined':   ({'name': biggest_decline['name'], 'value': biggest_decline['chg_30d']}
                       if biggest_decline else None),
    }


def signal_for(margin: float | None, ore_jsv: float | None, ore_jbv: float | None,
               chg_30d: float | None) -> str:
    if margin is None:
        return 'No Data'
    if ore_jsv and ore_jbv and ore_jsv > ore_jbv * 20:
        return 'Thin Market'
    if margin >= 20 and chg_30d and chg_30d > 0:
        return 'Strong Buy'
    if margin >= 10:
        return 'Buy'
    if margin >= 5:
        return 'Watch'
    if margin >= 0:
        return 'Marginal'
    return 'Avoid'


def row_class(margin: float | None, ore_jsv: float | None, ore_jbv: float | None) -> str:
    if margin is None:
        return 'row-nodata'
    if ore_jsv and ore_jbv and ore_jsv > ore_jbv * 20:
        return 'row-nodata'
    if margin >= 5:
        return 'row-green'
    if margin >= 0:
        return 'row-yellow'
    return 'row-red'


# ── Database queries ──────────────────────────────────────────────────────────
def load_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── site_config params ───────────────────────────────────────────────────
    cur.execute("SELECT key, value FROM site_config")
    cfg = {r['key']: r['value'] for r in cur.fetchall()}

    params = {
        'buy_basis':  cfg.get('ore_param_buy_basis', 'JSV  (instant)'),
        'buy_pct':    float(cfg.get('ore_param_buy_pct', '100')) / 100.0,
        'broker_pct': float(cfg.get('ore_param_broker_pct', '1.5')) / 100.0,
        'ship_rate':  float(cfg.get('ore_param_ship_rate', '125')),
        'collat_pct': float(cfg.get('ore_param_collat_pct', '1')) / 100.0,
        'refine_eff': float(cfg.get('ore_param_refine_eff', '90.63')) / 100.0,
    }

    prod_pcts = {}
    for pid, _ in ICE_PRODUCTS:
        key = f'ice_pct_{pid}'
        prod_pcts[pid] = float(cfg.get(key, '95')) / 100.0

    # ── Inventory metadata ───────────────────────────────────────────────────
    all_ids = ICE_COMP + ALL_PRODUCT_IDS
    ph = ','.join('?' * len(all_ids))
    cur.execute(
        f"SELECT type_id, type_name, volume, portion_size FROM inv_types WHERE type_id IN ({ph})",
        all_ids)
    inv = {r['type_id']: {'name': r['type_name'], 'volume': r['volume'],
                           'portion': r['portion_size']}
           for r in cur.fetchall()}

    # ── Type materials (yields) ──────────────────────────────────────────────
    ph2 = ','.join('?' * len(ICE_COMP))
    cur.execute(f"SELECT type_id, materials_json FROM type_materials WHERE type_id IN ({ph2})",
                ICE_COMP)
    yields_map = {r['type_id']: json.loads(r['materials_json']) for r in cur.fetchall()}

    # ── Daily price history ──────────────────────────────────────────────────
    ph3 = ','.join('?' * len(all_ids))
    cur.execute(f"""
        SELECT type_id,
               DATE(timestamp) AS day,
               AVG(best_buy)   AS jbv,
               AVG(best_sell)  AS jsv
        FROM market_price_snapshots
        WHERE type_id IN ({ph3})
        GROUP BY type_id, DATE(timestamp)
        ORDER BY type_id, day
    """, all_ids)

    daily_hist: dict[int, dict[str, dict]] = {}
    for r in cur.fetchall():
        tid = r['type_id']
        if tid not in daily_hist:
            daily_hist[tid] = {}
        daily_hist[tid][r['day']] = {'jbv': r['jbv'], 'jsv': r['jsv']}

    cur.execute("SELECT MAX(timestamp) FROM market_price_snapshots")
    row = cur.fetchone()
    latest_ts = row[0] if row else 'unknown'

    conn.close()
    return params, prod_pcts, inv, yields_map, daily_hist, latest_ts


# ── Price point helpers ───────────────────────────────────────────────────────
def get_price_at(daily_hist: dict, type_id: int, target_date: str,
                 field: str = 'jsv') -> float | None:
    hist = daily_hist.get(type_id)
    if not hist:
        return None
    val = price_near({d: v[field] for d, v in hist.items()}, target_date)
    return val


def get_latest_price(daily_hist: dict, type_id: int,
                     field: str = 'jsv') -> float | None:
    hist = daily_hist.get(type_id)
    if not hist:
        return None
    latest_day = max(hist.keys())
    return hist[latest_day].get(field)


def get_ore_buy_price(daily_hist: dict, type_id: int, buy_basis: str,
                      target_date: str = None) -> float | None:
    is_jsv = 'JSV' in buy_basis
    field  = 'jsv' if is_jsv else 'jbv'
    if target_date:
        return get_price_at(daily_hist, type_id, target_date, field)
    return get_latest_price(daily_hist, type_id, field)


# ── Main analysis ─────────────────────────────────────────────────────────────
def build_analyses(params, prod_pcts, inv, yields_map, daily_hist):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    d_7   = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
    d_30  = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')

    all_dates = []
    for hist in daily_hist.values():
        if hist:
            all_dates.append(min(hist.keys()))
    earliest = min(all_dates) if all_dates else d_30
    ref_30 = max(d_30, earliest) if d_30 < earliest else d_30

    def prod_jbv_at(date_str):
        return {pid: get_price_at(daily_hist, pid, date_str, 'jbv')
                for pid in ALL_PRODUCT_IDS}

    prod_jbv_now = prod_jbv_at(today)
    prod_jbv_7d  = prod_jbv_at(d_7)
    prod_jbv_30d = prod_jbv_at(ref_30)

    analyses = []

    for type_id in ICE_COMP:
        meta = inv.get(type_id)
        if not meta:
            continue
        name    = meta['name']
        volume  = meta['volume']
        portion = meta['portion']
        yields  = yields_map.get(type_id, [])
        family  = ore_family(type_id, name)
        quality = variant_label(name)

        ore_price_now = get_ore_buy_price(daily_hist, type_id, params['buy_basis'], today)
        ore_price_7d  = get_ore_buy_price(daily_hist, type_id, params['buy_basis'], d_7)
        ore_price_30d = get_ore_buy_price(daily_hist, type_id, params['buy_basis'], ref_30)

        ore_jsv_now = get_latest_price(daily_hist, type_id, 'jsv')
        ore_jbv_now = get_latest_price(daily_hist, type_id, 'jbv')

        margin_now, cost_now, val_now = calc_margin(
            ore_price_now, volume, portion, yields, prod_jbv_now, params, prod_pcts)
        margin_7d, _, _ = calc_margin(
            ore_price_7d, volume, portion, yields, prod_jbv_7d, params, prod_pcts)
        margin_30d, _, _ = calc_margin(
            ore_price_30d, volume, portion, yields, prod_jbv_30d, params, prod_pcts)

        chg_7d  = (margin_now - margin_7d)  if margin_now is not None and margin_7d  is not None else None
        chg_30d = (margin_now - margin_30d) if margin_now is not None and margin_30d is not None else None

        primary_driver = ''
        if yields and val_now > 0:
            best_contrib = 0.0
            for mat in yields:
                mid = mat['materialTypeID']
                qty = mat['quantity']
                jbv = prod_jbv_now.get(mid)
                if jbv and jbv > 0:
                    sp  = prod_pcts.get(mid, 0.95)
                    isk = qty * params['refine_eff'] * jbv * sp
                    if isk > best_contrib:
                        best_contrib   = isk
                        primary_driver = PRODUCT_NAME.get(mid, str(mid))

        sig = signal_for(margin_now, ore_jsv_now, ore_jbv_now, chg_30d)
        rc  = row_class(margin_now, ore_jsv_now, ore_jbv_now)

        product_breakdown = []
        for mat in yields:
            mid   = mat['materialTypeID']
            qty   = mat['quantity']
            pname = PRODUCT_NAME.get(mid, str(mid))
            jbv_n = prod_jbv_now.get(mid)
            jbv_7 = prod_jbv_7d.get(mid)
            jbv_3 = prod_jbv_30d.get(mid)
            sp    = prod_pcts.get(mid, 0.95)
            ref   = params['refine_eff']

            isk_contrib = (qty * ref * jbv_n * sp) if jbv_n else None
            pct_of_val  = (isk_contrib / val_now * 100) if (isk_contrib and val_now > 0) else None

            chg7  = ((jbv_n - jbv_7)  / jbv_7  * 100) if jbv_n and jbv_7  and jbv_7 > 0  else None
            chg30 = ((jbv_n - jbv_3)  / jbv_3  * 100) if jbv_n and jbv_3  and jbv_3 > 0  else None

            jbv_3_val     = prod_jbv_30d.get(mid)
            isk_30d       = (qty * ref * jbv_3_val * sp) if jbv_3_val else None
            isk_impact_30d = (isk_contrib - isk_30d) if (isk_contrib and isk_30d) else None

            product_breakdown.append({
                'id':           mid,
                'name':         pname,
                'qty':          qty,
                'jbv_now':      jbv_n,
                'chg7':         chg7,
                'chg14':        None,
                'chg30':        chg30,
                'isk_contrib':  isk_contrib,
                'pct_of_val':   pct_of_val,
                'isk_impact30': isk_impact_30d,
            })

        sparklines = {}
        for mat in yields:
            mid  = mat['materialTypeID']
            hist = daily_hist.get(mid, {})
            cutoff = ref_30
            days_sorted = sorted(d for d in hist if d >= cutoff)
            sparklines[mid] = [round(hist[d]['jbv'], 2) if hist[d]['jbv'] else None
                               for d in days_sorted]

        narrative = generate_ore_narrative(
            family, margin_now, yields,
            prod_jbv_now, prod_jbv_30d,
            prod_pcts, params['refine_eff'],
            cost_now, val_now
        )

        analyses.append({
            'type_id':    type_id,
            'name':       name,
            'family':     family,
            'quality':    quality,
            'volume':     volume,
            'portion':    portion,
            'ore_jsv':    ore_jsv_now,
            'ore_jbv':    ore_jbv_now,
            'current_margin': margin_now,
            'chg_7d':     chg_7d,
            'chg_30d':    chg_30d,
            'total_cost': cost_now,
            'prod_value': val_now,
            'primary_driver': primary_driver,
            'signal':     sig,
            'row_class':  rc,
            'product_breakdown': product_breakdown,
            'sparklines': sparklines,
            'narrative':  narrative,
        })

    return analyses, prod_jbv_now, prod_jbv_7d, prod_jbv_30d


# ── HTML helpers ──────────────────────────────────────────────────────────────
def fmt_isk(v, decimals=0):
    if v is None:
        return 'N/A'
    if abs(v) >= 1_000_000_000:
        return f'{v/1_000_000_000:.2f}B'
    if abs(v) >= 1_000_000:
        return f'{v/1_000_000:.2f}M'
    if abs(v) >= 1_000:
        return f'{v/1_000:.1f}K'
    return f'{v:.{decimals}f}'


def fmt_pct(v, plus=False):
    if v is None:
        return 'N/A'
    sign = '+' if (plus and v > 0) else ''
    return f'{sign}{v:.1f}%'


def chg_class(v):
    if v is None:
        return ''
    return 'pos' if v > 0 else ('neg' if v < 0 else 'neutral')


def signal_class(sig):
    return {
        'Strong Buy': 'sig-strong-buy',
        'Buy':        'sig-buy',
        'Watch':      'sig-watch',
        'Marginal':   'sig-marginal',
        'Avoid':      'sig-avoid',
        'Thin Market':'sig-thin',
        'No Data':    'sig-nodata',
    }.get(sig, '')


def build_html(analyses, exec_summary, prod_jbv_now, prod_jbv_7d, prod_jbv_30d,
               params, latest_ts, gen_ts):

    sorted_analyses = sorted(
        analyses,
        key=lambda a: (a['current_margin'] if a['current_margin'] is not None else -9999),
        reverse=True
    )

    # Group by family for section 3
    families = {}
    for a in analyses:
        fam = a['family']
        if fam not in families:
            families[fam] = []
        families[fam].append(a)

    # Sort families by FAMILY_ORDER
    def family_sort_key(fam):
        try:
            return FAMILY_ORDER.index(fam)
        except ValueError:
            return len(FAMILY_ORDER)
    sorted_families = sorted(families.keys(), key=family_sort_key)

    # Build Section 3 HTML
    sec3_html_parts = []
    for fam in sorted_families:
        members = families[fam]
        # Base ore first (no grade suffix)
        base_ores = [m for m in members if m['quality'] == 'Base']
        grade_ores = [m for m in members if m['quality'] != 'Base']
        base_ore = base_ores[0] if base_ores else (members[0] if members else None)
        if not base_ore:
            continue

        all_members = sorted(members, key=lambda a: (0 if a['quality'] == 'Base' else 1, a['quality']))

        margin_str = fmt_pct(base_ore['current_margin'])
        chg30_str  = fmt_pct(base_ore['chg_30d'], plus=True)

        # Variant sub-table rows
        variant_rows = ''
        for m in all_members:
            rc = row_class(m['current_margin'], m['ore_jsv'], m['ore_jbv'])
            variant_rows += (
                f"<tr class='{rc}'>"
                f"<td>{m['name']}</td>"
                f"<td>{m['quality']}</td>"
                f"<td class='num {chg_class(m['current_margin'])}'>{fmt_pct(m['current_margin'])}</td>"
                f"<td class='num'>{fmt_isk(m['ore_jsv'])}</td>"
                f"<td class='num'>{fmt_isk(m['ore_jbv'])}</td>"
                f"</tr>"
            )

        # Product breakdown table (use base ore)
        prod_rows = ''
        for pb in base_ore['product_breakdown']:
            chg14_class = chg_class(pb['chg14'])
            prod_rows += (
                f"<tr>"
                f"<td>{pb['name']}</td>"
                f"<td class='num'>{pb['qty']}</td>"
                f"<td class='num'>{fmt_isk(pb['jbv_now'])}</td>"
                f"<td class='num {chg_class(pb['chg7'])}'>{fmt_pct(pb['chg7'], plus=True)}</td>"
                f"<td class='num {chg14_class}'>{fmt_pct(pb['chg14'], plus=True)}</td>"
                f"<td class='num {chg_class(pb['chg30'])}'>{fmt_pct(pb['chg30'], plus=True)}</td>"
                f"<td class='num'>{fmt_isk(pb['isk_contrib'])}</td>"
                f"<td class='num'>{fmt_pct(pb['pct_of_val'])}</td>"
                f"<td class='num {chg_class(pb['isk_impact30'])}'>{fmt_isk(pb['isk_impact30'])}</td>"
                f"</tr>"
            )

        # Sparkline canvases + data
        spark_canvases = ''
        spark_scripts  = ''
        for pb in base_ore['product_breakdown']:
            mid       = pb['id']
            cid       = f"spark_{base_ore['type_id']}_{mid}"
            data      = base_ore['sparklines'].get(mid, [])
            data_json = json.dumps([d for d in data if d is not None])
            color     = '#00d9ff'
            spark_canvases += (
                f"<div class='spark-wrap'>"
                f"<div class='spark-label'>{pb['name']}</div>"
                f"<canvas id='{cid}' height='60'></canvas>"
                f"</div>"
            )
            spark_scripts += f"""
            (function() {{
                var ctx = document.getElementById('{cid}');
                if (!ctx) return;
                var data = {data_json};
                if (!data.length) {{ ctx.parentElement.style.opacity='0.3'; return; }}
                new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: data.map(function(_,i){{return i;}}),
                        datasets: [{{
                            data: data,
                            borderColor: '{color}',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            tension: 0.3,
                            fill: false
                        }}]
                    }},
                    options: {{
                        animation: false,
                        responsive: true,
                        plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }} }},
                        scales: {{
                            x: {{ display: false }},
                            y: {{ display: false }}
                        }}
                    }}
                }});
            }})();
"""

        sec3_html_parts.append(f"""
        <div class="family-card">
            <div class="family-header">
                <span class="family-name">{fam}</span>
                <span class="family-margin {chg_class(base_ore['current_margin'])}">{margin_str}</span>
                <span class="family-chg {chg_class(base_ore['chg_30d'])}">30d: {chg30_str}</span>
            </div>
            <p class="family-narrative">{base_ore['narrative']}</p>

            <h4 class="sub-heading">Product Breakdown (base ore per batch)</h4>
            <div class="table-scroll">
            <table class="data-table">
                <thead><tr>
                    <th>Product</th><th class="num">Qty/batch</th><th class="num">JBV now</th>
                    <th class="num">7d %</th><th class="num">14d %</th><th class="num">30d %</th>
                    <th class="num">ISK contrib</th><th class="num">% of value</th>
                    <th class="num">30d ISK impact</th>
                </tr></thead>
                <tbody>{prod_rows}</tbody>
            </table>
            </div>

            <h4 class="sub-heading">Variant Comparison</h4>
            <div class="table-scroll">
            <table class="data-table variant-table">
                <thead><tr>
                    <th>Ore</th><th>Grade</th><th class="num">Margin</th>
                    <th class="num">JSV</th><th class="num">JBV</th>
                </tr></thead>
                <tbody>{variant_rows}</tbody>
            </table>
            </div>

            <h4 class="sub-heading">30-Day Price Sparklines (JBV)</h4>
            <div class="sparkline-row">
                {spark_canvases}
            </div>
            <script>{spark_scripts}</script>
        </div>
""")

    sec3_html = '\n'.join(sec3_html_parts)

    # Section 4 — Product Market Overview
    prod_rows_s4 = ''
    prod_jbv_changes = []
    for pid, pname in ICE_PRODUCTS:
        jbv_n = prod_jbv_now.get(pid)
        jbv_7 = prod_jbv_7d.get(pid)
        jbv_3 = prod_jbv_30d.get(pid)
        c7  = ((jbv_n - jbv_7) / jbv_7 * 100)  if jbv_n and jbv_7  and jbv_7 > 0  else None
        c30 = ((jbv_n - jbv_3) / jbv_3 * 100)  if jbv_n and jbv_3  and jbv_3 > 0  else None

        if c30 is not None:
            prod_jbv_changes.append(c30)

        if c30 is None:
            trend = '—'
        elif c30 > 5:
            trend = '▲ Rising'
        elif c30 < -5:
            trend = '▼ Falling'
        else:
            trend = '→ Stable'

        prod_rows_s4 += (
            f"<tr>"
            f"<td>{pname}</td>"
            f"<td class='num'>{fmt_isk(jbv_n)}</td>"
            f"<td class='num {chg_class(c7)}'>{fmt_pct(c7, plus=True)}</td>"
            f"<td class='num'>N/A</td>"
            f"<td class='num {chg_class(c30)}'>{fmt_pct(c30, plus=True)}</td>"
            f"<td>{trend}</td>"
            f"</tr>"
        )

    if prod_jbv_changes:
        avg_chg = sum(prod_jbv_changes) / len(prod_jbv_changes)
        if avg_chg > 3:
            prod_summary = f"Ice products are trending upward on average ({avg_chg:+.1f}% over 30 days)."
        elif avg_chg < -3:
            prod_summary = f"Ice products are under selling pressure ({avg_chg:+.1f}% over 30 days)."
        else:
            prod_summary = f"Ice products have been broadly stable over the past 30 days (avg {avg_chg:+.1f}%)."
    else:
        prod_summary = "Insufficient data for ice product trend summary."

    sec4_html = f"""
        <div class="tier-section">
            <p class="tier-summary">{prod_summary}</p>
            <div class="table-scroll">
            <table class="data-table">
                <thead><tr>
                    <th>Product</th>
                    <th class="num">JBV now</th>
                    <th class="num">7d %</th>
                    <th class="num">14d %</th>
                    <th class="num">30d %</th>
                    <th>Trend</th>
                </tr></thead>
                <tbody>{prod_rows_s4}</tbody>
            </table>
            </div>
        </div>
"""

    # Rankings table rows
    ranking_rows = ''
    for a in sorted_analyses:
        rc  = a['row_class']
        sig = a['signal']
        sc  = signal_class(sig)
        ranking_rows += (
            f"<tr class='{rc}'>"
            f"<td>{a['name']}</td>"
            f"<td class='num {chg_class(a['current_margin'])}'>{fmt_pct(a['current_margin'])}</td>"
            f"<td class='num {chg_class(a['chg_7d'])}'>{fmt_pct(a['chg_7d'], plus=True)}</td>"
            f"<td class='num {chg_class(a['chg_30d'])}'>{fmt_pct(a['chg_30d'], plus=True)}</td>"
            f"<td>{a['primary_driver']}</td>"
            f"<td><span class='signal {sc}'>{sig}</span></td>"
            f"</tr>"
        )

    # Exec summary cards
    def stat_card(label, name, value, fmt_fn, color_class=''):
        if name is None:
            return f"<div class='stat-card'><div class='stat-label'>{label}</div><div class='stat-value nodata'>N/A</div></div>"
        return (
            f"<div class='stat-card'>"
            f"<div class='stat-label'>{label}</div>"
            f"<div class='stat-value {color_class}'>{fmt_fn(value)}</div>"
            f"<div class='stat-name'>{name}</div>"
            f"</div>"
        )

    es = exec_summary
    cards_html = (
        stat_card('Best Margin', es['best']['name'] if es['best'] else None,
                  es['best']['value'] if es['best'] else None, lambda v: f"{v:.1f}%", 'pos') +
        stat_card('Worst Margin', es['worst']['name'] if es['worst'] else None,
                  es['worst']['value'] if es['worst'] else None, lambda v: f"{v:.1f}%",
                  'neg' if (es['worst'] and es['worst']['value'] < 0) else '') +
        stat_card('Most Improved (30d)', es['improved']['name'] if es['improved'] else None,
                  es['improved']['value'] if es['improved'] else None,
                  lambda v: f"{v:+.1f} pp", 'pos') +
        stat_card('Biggest Decline (30d)', es['declined']['name'] if es['declined'] else None,
                  es['declined']['value'] if es['declined'] else None,
                  lambda v: f"{v:+.1f} pp", 'neg')
    )

    buy_basis_label = params['buy_basis']
    refine_eff_pct  = params['refine_eff'] * 100

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ice Ore Margin Report — LX-ZOJ</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg:      #0a1520;
    --bg2:     #0e1e30;
    --bg3:     #122540;
    --text:    #c8d8e8;
    --muted:   #7898a8;
    --cyan:    #00d9ff;
    --gold:    #ffd700;
    --green:   #00e676;
    --red:     #ff3d3d;
    --yellow:  #ffcc44;
    --border:  #1a3555;
  }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    line-height: 1.5;
  }}
  a {{ color: var(--cyan); text-decoration: none; }}

  .container {{ max-width: 1400px; margin: 0 auto; padding: 0 16px 40px; }}
  .report-header {{
    background: linear-gradient(135deg, #0e1e30 0%, #122540 100%);
    border-bottom: 2px solid var(--cyan);
    padding: 24px 16px 16px;
    margin-bottom: 24px;
  }}
  .report-header h1 {{
    font-size: 22px; font-weight: 700;
    color: var(--cyan);
    letter-spacing: 1px;
  }}
  .report-meta {{ color: var(--muted); font-size: 11px; margin-top: 6px; }}
  .report-params {{
    display: flex; flex-wrap: wrap; gap: 16px;
    margin-top: 10px; font-size: 11px; color: var(--muted);
  }}
  .report-params span {{ color: var(--text); }}

  .section-title {{
    font-size: 16px; font-weight: 700;
    color: var(--cyan);
    border-left: 3px solid var(--cyan);
    padding-left: 10px;
    margin: 28px 0 16px;
  }}
  .sub-heading {{
    font-size: 12px; font-weight: 600;
    color: var(--gold);
    margin: 14px 0 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  .stat-cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
  .stat-card {{
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 18px;
    min-width: 180px; flex: 1;
  }}
  .stat-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px; color: var(--muted); }}
  .stat-value {{ font-size: 22px; font-weight: 700; margin: 4px 0 2px; }}
  .stat-name  {{ font-size: 11px; color: var(--muted); }}

  .exec-para {{
    background: var(--bg2);
    border: 1px solid var(--border);
    border-left: 3px solid var(--gold);
    border-radius: 4px;
    padding: 14px 16px;
    margin-bottom: 20px;
    line-height: 1.7;
    font-size: 13px;
  }}

  .table-scroll {{ overflow-x: auto; }}
  .data-table {{
    width: 100%; border-collapse: collapse;
    font-size: 12px;
  }}
  .data-table th {{
    background: var(--bg3);
    color: var(--muted);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 10px;
    letter-spacing: 0.5px;
    padding: 8px 10px;
    text-align: left;
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 1;
  }}
  .data-table th.num {{ text-align: right; }}
  .data-table td {{
    padding: 7px 10px;
    border-bottom: 1px solid #0f2035;
  }}
  .data-table td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .data-table tr:hover {{ background: rgba(0,217,255,0.04); }}

  .row-green  {{ background: rgba(0,230,118,0.06); }}
  .row-yellow {{ background: rgba(255,204,68,0.06); }}
  .row-red    {{ background: rgba(255,61,61,0.07); }}
  .row-nodata {{ background: rgba(40,60,80,0.3); opacity: 0.6; }}

  .signal {{ display: inline-block; padding: 1px 7px; border-radius: 3px; font-size: 10px; font-weight: 700; }}
  .sig-strong-buy {{ background: #004a20; color: #00e676; }}
  .sig-buy        {{ background: #003520; color: #34d058; }}
  .sig-watch      {{ background: #3a2e00; color: #ffcc44; }}
  .sig-marginal   {{ background: #2a2000; color: #aa9900; }}
  .sig-avoid      {{ background: #3a0000; color: #ff3d3d; }}
  .sig-thin       {{ background: #202040; color: #aaaaff; }}
  .sig-nodata     {{ background: #1a2535; color: #5a7090; }}

  .pos     {{ color: var(--green); }}
  .neg     {{ color: var(--red); }}
  .neutral {{ color: var(--muted); }}
  .nodata  {{ color: var(--muted); font-style: italic; }}

  .filter-bar {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
  .filter-btn {{
    padding: 4px 14px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg3);
    color: var(--muted);
    cursor: pointer;
    font-size: 11px;
    font-weight: 600;
    transition: all 0.15s;
  }}
  .filter-btn:hover {{ border-color: var(--cyan); color: var(--cyan); }}
  .filter-btn.active {{ background: var(--cyan); color: #000; border-color: var(--cyan); }}

  .family-cards {{ display: flex; flex-direction: column; gap: 16px; }}
  .family-card {{
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 18px;
  }}
  .family-header {{
    display: flex; align-items: center; gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 10px;
  }}
  .family-name {{ font-size: 15px; font-weight: 700; color: var(--gold); }}
  .family-margin {{ font-size: 14px; font-weight: 700; }}
  .family-chg {{ font-size: 12px; }}

  .family-narrative {{
    font-size: 12px; color: var(--text);
    background: rgba(0,217,255,0.03);
    border-left: 2px solid var(--cyan);
    padding: 8px 12px;
    border-radius: 2px;
    margin-bottom: 10px;
  }}

  .sparkline-row {{
    display: flex; flex-wrap: wrap; gap: 12px;
    margin-top: 8px;
  }}
  .spark-wrap {{
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 6px 8px;
    min-width: 120px;
    flex: 1;
  }}
  .spark-label {{
    font-size: 10px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.5px;
    margin-bottom: 4px;
  }}

  .tier-section {{ margin-bottom: 24px; }}
  .tier-summary {{ font-size: 12px; color: var(--muted); margin-bottom: 10px; }}

  #rankings-table-container {{ max-height: 600px; overflow-y: auto; }}
  .variant-table td, .variant-table th {{ padding: 5px 8px; }}

  @media (max-width: 768px) {{
    .stat-card {{ min-width: 140px; }}
    .sparkline-row .spark-wrap {{ min-width: 100px; }}
  }}
</style>
</head>
<body>

<div class="report-header">
  <div class="container" style="padding-bottom:0;">
    <h1>Ice Ore Margin Report — LX-ZOJ</h1>
    <div class="report-meta">
      Generated: {gen_ts} &nbsp;|&nbsp;
      Price data through: {latest_ts[:19].replace('T',' ')} UTC
    </div>
    <div class="report-params">
      Buy basis: <span>{buy_basis_label}</span> &nbsp;
      Buy %: <span>{params['buy_pct']*100:.0f}%</span> &nbsp;
      Shipping: <span>{params['ship_rate']:.0f} ISK/m³</span> &nbsp;
      Collateral: <span>{params['collat_pct']*100:.1f}%</span> &nbsp;
      Refine eff: <span>{refine_eff_pct:.2f}%</span> &nbsp;
      Broker: <span>{'0% (JSV)' if 'JSV' in buy_basis_label else f"{params['broker_pct']*100:.1f}%"}</span>
    </div>
  </div>
</div>

<div class="container">

  <!-- Section 1: Executive Summary -->
  <h2 class="section-title">Executive Summary</h2>
  <div class="exec-para">{es['paragraph']}</div>
  <div class="stat-cards">
    {cards_html}
  </div>

  <!-- Section 2: Rankings Table -->
  <h2 class="section-title">Ice Ore Rankings</h2>
  <div id="rankings-table-container">
    <table class="data-table" id="rankings-table">
      <thead><tr>
        <th>Name</th>
        <th class="num">Margin</th>
        <th class="num">7d Chg</th>
        <th class="num">30d Chg</th>
        <th>Primary Driver</th>
        <th>Signal</th>
      </tr></thead>
      <tbody id="rankings-tbody">
        {ranking_rows}
      </tbody>
    </table>
  </div>

  <!-- Section 3: Family Cards -->
  <h2 class="section-title">Per-Family Analysis</h2>
  <div class="family-cards" id="family-cards-container">
    {sec3_html}
  </div>

  <!-- Section 4: Product Market Overview -->
  <h2 class="section-title">Ice Product Market Overview</h2>
  {sec4_html}

</div><!-- /container -->

</body>
</html>
"""
    return html


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print("Loading data from database...")
    params, prod_pcts, inv, yields_map, daily_hist, latest_ts = load_data()

    print("Computing margins and analyses...")
    analyses, prod_jbv_now, prod_jbv_7d, prod_jbv_30d = build_analyses(
        params, prod_pcts, inv, yields_map, daily_hist)

    # Patch chg14 for product breakdowns
    d14 = (datetime.now(timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%d')
    for a in analyses:
        for pb in a['product_breakdown']:
            mid    = pb['id']
            jbv_n  = prod_jbv_now.get(mid)
            jbv_14 = get_price_at(daily_hist, mid, d14, 'jbv')
            pb['chg14'] = ((jbv_n - jbv_14) / jbv_14 * 100
                           if jbv_n and jbv_14 and jbv_14 > 0 else None)

    print("Generating executive summary...")
    exec_summary = generate_exec_summary(analyses)

    gen_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print("Building HTML report...")
    html = build_html(analyses, exec_summary, prod_jbv_now, prod_jbv_7d, prod_jbv_30d,
                      params, latest_ts, gen_ts)

    print(f"Writing report to {OUT_PATH} ...")
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print("Done. Opening in browser...")
    webbrowser.open(f'file:///{OUT_PATH.replace(os.sep, "/")}')
    print(f"Report saved: {OUT_PATH}")


if __name__ == '__main__':
    main()
