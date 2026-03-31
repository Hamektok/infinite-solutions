"""
generate_moon_margin_report.py
Generates a standalone HTML moon ore margin analysis report for LX-ZOJ.
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
OUT_PATH = os.path.join(os.path.dirname(__file__), 'moon_margin_report.html')

# ── Type ID Constants ────────────────────────────────────────────────────────
MOON_COMP = [
    62454, 62457, 62455, 62458, 62461, 62464,
    62456, 62459, 62466, 62467, 62460, 62463,
    62474, 62471, 62468, 62477,
    62475, 62472, 62469, 62478,
    62476, 62473, 62470, 62479,
    62480, 62483, 62486, 62489,
    62481, 62484, 62487, 62490,
    62482, 62485, 62488, 62491,
    62492, 62501, 62498, 62495,
    62493, 62502, 62499, 62496,
    62494, 62503, 62500, 62497,
    62504, 62510, 62507, 62513,
    62505, 62511, 62508, 62514,
    62506, 62512, 62509, 62515,
]

PRODUCTS = {
    'R4':  [(16633, 'Hydrocarbons'),   (16634, 'Atmospheric Gases'),
            (16635, 'Evaporite Deposits'), (16636, 'Silicates')],
    'R8':  [(16637, 'Tungsten'),       (16638, 'Titanium'),
            (16639, 'Scandium'),        (16640, 'Cobalt')],
    'R16': [(16641, 'Chromium'),       (16642, 'Vanadium'),
            (16643, 'Cadmium'),         (16644, 'Platinum')],
    'R32': [(16646, 'Mercury'),        (16647, 'Caesium'),
            (16648, 'Hafnium'),         (16649, 'Technetium')],
    'R64': [(16650, 'Dysprosium'),     (16651, 'Neodymium'),
            (16652, 'Promethium'),      (16653, 'Thulium')],
}

ALL_PRODUCT_IDS = [pid for tier_list in PRODUCTS.values() for pid, _ in tier_list]
PRODUCT_NAME    = {pid: name for tier_list in PRODUCTS.values() for pid, name in tier_list}
PRODUCT_TIER    = {pid: tier for tier, tier_list in PRODUCTS.items() for pid, _ in tier_list}

# Ore family keywords — order matters (more specific first)
FAMILY_KEYWORDS = [
    'Loparite', 'Monazite', 'Xenotime', 'Ytterbite',
    'Carnotite', 'Cinnabar', 'Pollucite', 'Zircon',
    'Chromite', 'Otavite', 'Sperrylite', 'Vanadinite',
    'Cobaltite', 'Euxenite', 'Scheelite', 'Titanite',
    'Bitumens', 'Coesite', 'Sylvite', 'Zeolites',
]

# Variant quality markers (prefix words after "Compressed")
VARIANT_BASE    = {''}
VARIANT_MID     = {'Bountiful', 'Copious', 'Lavish', 'Replete', 'Brimful'}
VARIANT_HIGH    = {'Shining', 'Glowing', 'Twinkling', 'Shimmering', 'Glistening'}

TIER_ORDER = {'R4': 0, 'R8': 1, 'R16': 2, 'R32': 3, 'R64': 4}


# ── Helper: ore family extraction ────────────────────────────────────────────
def ore_family(name: str) -> str:
    """Extract family name from full ore name like 'Compressed Bountiful Loparite'."""
    for kw in FAMILY_KEYWORDS:
        if kw.lower() in name.lower():
            return kw
    return name.replace('Compressed ', '')


def ore_variant_quality(name: str) -> int:
    """Return variant quality tier: 0=base, 1=mid, 2=high."""
    parts = name.replace('Compressed ', '').split()
    if len(parts) >= 2:
        qualifier = parts[0]
        if qualifier in VARIANT_HIGH:
            return 2
        if qualifier in VARIANT_MID:
            return 1
    return 0


def get_tier(yields: list) -> str:
    """Return highest R-tier present in the ore's yields."""
    best = 'R4'
    for mat in yields:
        mat_id = mat['materialTypeID']
        tier = PRODUCT_TIER.get(mat_id)
        if tier and TIER_ORDER.get(tier, 0) > TIER_ORDER.get(best, 0):
            best = tier
    return best


def price_near(daily_hist: dict, target_date: str) -> float | None:
    """Find closest available daily price at or before target_date."""
    if not daily_hist:
        return None
    candidates = [d for d in daily_hist if d <= target_date]
    if not candidates:
        # fallback: earliest available
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
    """
    Generate executive summary dict with:
      - paragraph (str)
      - best_ore, worst_ore, most_improved, biggest_decline (each with name+value)
    """
    valid = [a for a in analyses if a['current_margin'] is not None]
    if not valid:
        return {'paragraph': 'Insufficient data for executive summary.',
                'best': None, 'worst': None, 'improved': None, 'declined': None}

    improving = sum(1 for a in valid if a.get('chg_30d') and a['chg_30d'] > 0)
    declining = sum(1 for a in valid if a.get('chg_30d') and a['chg_30d'] < 0)
    mixed     = len(valid) - improving - declining

    r64_ores   = [a for a in valid if a['tier'] == 'R64']
    r64_avg    = (sum(a['current_margin'] for a in r64_ores) / len(r64_ores)
                  if r64_ores else None)

    best  = max(valid, key=lambda a: a['current_margin'])
    worst = min(valid, key=lambda a: a['current_margin'])

    movers = [a for a in valid if a.get('chg_30d') is not None]
    most_improved  = max(movers, key=lambda a: a['chg_30d']) if movers else None
    biggest_decline = min(movers, key=lambda a: a['chg_30d']) if movers else None

    # Overall trend description
    if improving > declining + mixed:
        trend_word = "improving broadly"
    elif declining > improving + mixed:
        trend_word = "declining across most ores"
    else:
        trend_word = "mixed"

    para_parts = [
        f"Moon ore margins are {trend_word} — "
        f"{improving} ores trending up, {declining} down, {mixed} flat over 30 days."
    ]

    if r64_avg is not None:
        # Find R64 primary driver by highest avg product JBV contribution
        para_parts.append(
            f"R64 ores average {r64_avg:.1f}% ROI."
        )

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
    for pid in ALL_PRODUCT_IDS:
        key = f'ore_pct_{pid}'
        prod_pcts[pid] = float(cfg.get(key, '95')) / 100.0

    # ── Inventory metadata ───────────────────────────────────────────────────
    all_ids = MOON_COMP + ALL_PRODUCT_IDS
    ph = ','.join('?' * len(all_ids))
    cur.execute(
        f"SELECT type_id, type_name, volume, portion_size FROM inv_types WHERE type_id IN ({ph})",
        all_ids)
    inv = {r['type_id']: {'name': r['type_name'], 'volume': r['volume'],
                           'portion': r['portion_size']}
           for r in cur.fetchall()}

    # ── Type materials (yields) ──────────────────────────────────────────────
    ph2 = ','.join('?' * len(MOON_COMP))
    cur.execute(f"SELECT type_id, materials_json FROM type_materials WHERE type_id IN ({ph2})",
                MOON_COMP)
    yields_map = {r['type_id']: json.loads(r['materials_json']) for r in cur.fetchall()}

    # ── Daily price history ──────────────────────────────────────────────────
    # For all relevant type_ids (ores + products)
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

    # daily_hist[type_id] = {date_str: {'jbv': float, 'jsv': float}}
    daily_hist: dict[int, dict[str, dict]] = {}
    for r in cur.fetchall():
        tid = r['type_id']
        if tid not in daily_hist:
            daily_hist[tid] = {}
        daily_hist[tid][r['day']] = {'jbv': r['jbv'], 'jsv': r['jsv']}

    # Latest data timestamp
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
    """Return ore price based on buy basis setting."""
    is_jsv = 'JSV' in buy_basis
    field  = 'jsv' if is_jsv else 'jbv'
    if target_date:
        return get_price_at(daily_hist, type_id, target_date, field)
    return get_latest_price(daily_hist, type_id, field)


# ── Main analysis ─────────────────────────────────────────────────────────────
def build_analyses(params, prod_pcts, inv, yields_map, daily_hist):
    today      = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    d_7        = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
    d_30       = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')

    # Determine earliest available date across all data
    all_dates = []
    for hist in daily_hist.values():
        if hist:
            all_dates.append(min(hist.keys()))
    earliest = min(all_dates) if all_dates else d_30

    # Use earliest if 30 days ago is before earliest available
    ref_30 = max(d_30, earliest) if d_30 < earliest else d_30

    # Product JBV at each timepoint
    def prod_jbv_at(date_str):
        return {pid: get_price_at(daily_hist, pid, date_str, 'jbv')
                for pid in ALL_PRODUCT_IDS}

    prod_jbv_now  = prod_jbv_at(today)
    prod_jbv_7d   = prod_jbv_at(d_7)
    prod_jbv_30d  = prod_jbv_at(ref_30)

    analyses = []

    for type_id in MOON_COMP:
        meta = inv.get(type_id)
        if not meta:
            continue
        name    = meta['name']
        volume  = meta['volume']
        portion = meta['portion']
        yields  = yields_map.get(type_id, [])
        tier    = get_tier(yields)
        family  = ore_family(name)
        quality = ore_variant_quality(name)

        # Ore buy price
        ore_price_now = get_ore_buy_price(daily_hist, type_id, params['buy_basis'], today)
        ore_price_7d  = get_ore_buy_price(daily_hist, type_id, params['buy_basis'], d_7)
        ore_price_30d = get_ore_buy_price(daily_hist, type_id, params['buy_basis'], ref_30)

        ore_jsv_now   = get_latest_price(daily_hist, type_id, 'jsv')
        ore_jbv_now   = get_latest_price(daily_hist, type_id, 'jbv')

        # Margins at each time point
        margin_now, cost_now, val_now = calc_margin(
            ore_price_now, volume, portion, yields, prod_jbv_now, params, prod_pcts)
        margin_7d, _, _ = calc_margin(
            ore_price_7d, volume, portion, yields, prod_jbv_7d, params, prod_pcts)
        margin_30d, _, _ = calc_margin(
            ore_price_30d, volume, portion, yields, prod_jbv_30d, params, prod_pcts)

        chg_7d  = ((margin_now - margin_7d)  if margin_now is not None and margin_7d  is not None else None)
        chg_30d = ((margin_now - margin_30d) if margin_now is not None and margin_30d is not None else None)

        # Primary driver (product with highest ISK contribution)
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
                        best_contrib  = isk
                        primary_driver = PRODUCT_NAME.get(mid, str(mid))

        sig = signal_for(margin_now, ore_jsv_now, ore_jbv_now, chg_30d)
        rc  = row_class(margin_now, ore_jsv_now, ore_jbv_now)

        # Per-product breakdown for family card
        product_breakdown = []
        for mat in yields:
            mid  = mat['materialTypeID']
            qty  = mat['quantity']
            pname = PRODUCT_NAME.get(mid, str(mid))
            jbv_n = prod_jbv_now.get(mid)
            jbv_7 = prod_jbv_7d.get(mid)
            jbv_3 = prod_jbv_30d.get(mid)
            sp    = prod_pcts.get(mid, 0.95)
            ref   = params['refine_eff']

            isk_contrib = (qty * ref * jbv_n * sp) if jbv_n else None
            pct_of_val  = (isk_contrib / val_now * 100) if (isk_contrib and val_now > 0) else None

            chg7  = ((jbv_n - jbv_7)  / jbv_7  * 100) if jbv_n and jbv_7  and jbv_7 > 0  else None
            chg14 = None  # could compute from 14d ago; skipping for now
            chg30 = ((jbv_n - jbv_3)  / jbv_3  * 100) if jbv_n and jbv_3  and jbv_3 > 0  else None

            # 30d ISK impact: isk_now vs isk_30d
            jbv_3_val = prod_jbv_30d.get(mid)
            isk_30d = (qty * ref * jbv_3_val * sp) if jbv_3_val else None
            isk_impact_30d = ((isk_contrib - isk_30d) if (isk_contrib and isk_30d) else None)

            product_breakdown.append({
                'id':           mid,
                'name':         pname,
                'qty':          qty,
                'jbv_now':      jbv_n,
                'chg7':         chg7,
                'chg14':        chg14,
                'chg30':        chg30,
                'isk_contrib':  isk_contrib,
                'pct_of_val':   pct_of_val,
                'isk_impact30': isk_impact_30d,
                'tier':         PRODUCT_TIER.get(mid, '?'),
            })

        # 30-day sparkline data for each product (JBV by day)
        sparklines = {}
        for mat in yields:
            mid  = mat['materialTypeID']
            hist = daily_hist.get(mid, {})
            # Get last 30 days
            cutoff = ref_30
            days_sorted = sorted(d for d in hist if d >= cutoff)
            sparklines[mid] = [round(hist[d]['jbv'], 2) if hist[d]['jbv'] else None
                               for d in days_sorted]

        # Narrative
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
            'tier':       tier,
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


# ── HTML generation ───────────────────────────────────────────────────────────
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

    # Prepare serializable data for JS
    js_data = []
    for a in sorted_analyses:
        js_data.append({
            'type_id':    a['type_id'],
            'name':       a['name'],
            'family':     a['family'],
            'tier':       a['tier'],
            'quality':    a['quality'],
            'ore_jsv':    a['ore_jsv'],
            'ore_jbv':    a['ore_jbv'],
            'margin':     a['current_margin'],
            'chg7':       a['chg_7d'],
            'chg30':      a['chg_30d'],
            'primary_driver': a['primary_driver'],
            'signal':     a['signal'],
            'row_class':  a['row_class'],
        })

    # Group by family for section 3
    families = {}
    for a in analyses:
        fam = a['family']
        if fam not in families:
            families[fam] = []
        families[fam].append(a)

    # Sort families by tier then name
    def family_sort_key(fam):
        members = families[fam]
        tier = min((TIER_ORDER.get(m['tier'], 0) for m in members), default=0)
        return (tier, fam)
    sorted_families = sorted(families.keys(), key=family_sort_key)

    # Build Section 3 HTML
    sec3_html_parts = []
    for fam in sorted_families:
        members = sorted(families[fam], key=lambda a: a['quality'])
        base_ore = members[0] if members else None
        if not base_ore:
            continue

        margin_str  = fmt_pct(base_ore['current_margin'])
        chg30_str   = fmt_pct(base_ore['chg_30d'], plus=True)
        tier_label  = base_ore['tier']

        # Variant sub-table rows
        variant_rows = ''
        for m in members:
            qual_labels = {0: 'Base', 1: 'Mid', 2: 'High'}
            qlabel = qual_labels.get(m['quality'], '?')
            rc = row_class(m['current_margin'], m['ore_jsv'], m['ore_jbv'])
            variant_rows += (
                f"<tr class='{rc}'>"
                f"<td>{m['name']}</td>"
                f"<td>{qlabel}</td>"
                f"<td class='{chg_class(m['current_margin'])}'>{fmt_pct(m['current_margin'])}</td>"
                f"<td>{fmt_isk(m['ore_jsv'])}</td>"
                f"<td>{fmt_isk(m['ore_jbv'])}</td>"
                f"</tr>"
            )

        # Product breakdown table (use base ore)
        prod_rows = ''
        for pb in base_ore['product_breakdown']:
            prod_rows += (
                f"<tr>"
                f"<td>{pb['name']}</td>"
                f"<td class='num'>{pb['qty']}</td>"
                f"<td class='num'>{fmt_isk(pb['jbv_now'])}</td>"
                f"<td class='num {chg_class(pb['chg7'])}'>{fmt_pct(pb['chg7'], plus=True)}</td>"
                f"<td class='num {chg_class(pb['chg14'])}'>{fmt_pct(pb['chg14'], plus=True)}</td>"
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
            mid   = pb['id']
            cid   = f"spark_{base_ore['type_id']}_{mid}"
            data  = base_ore['sparklines'].get(mid, [])
            data_json = json.dumps([d for d in data if d is not None])
            color = '#00d9ff'
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
        <div class="family-card" data-tier="{tier_label}">
            <div class="family-header">
                <span class="family-name">{fam}</span>
                <span class="family-tier badge-{tier_label.lower()}">{tier_label}</span>
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
                    <th>Ore</th><th>Quality</th><th class="num">Margin</th>
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
    sec4_html_parts = []
    for tier, tier_products in PRODUCTS.items():
        prod_rows_s4 = ''
        tier_jbv_changes = []
        for pid, pname in tier_products:
            jbv_n = prod_jbv_now.get(pid)
            jbv_7 = prod_jbv_7d.get(pid)
            jbv_3 = prod_jbv_30d.get(pid)
            c7  = ((jbv_n - jbv_7) / jbv_7 * 100)  if jbv_n and jbv_7  and jbv_7 > 0  else None
            c30 = ((jbv_n - jbv_3) / jbv_3 * 100)  if jbv_n and jbv_3  and jbv_3 > 0  else None
            # 14d
            d14 = (datetime.now(timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%d')
            jbv_14 = get_price_at({}, pid, d14, 'jbv')  # placeholder — compute below
            # recompute from daily_hist placeholder
            c14 = None

            if c30 is not None:
                tier_jbv_changes.append(c30)

            # Trend arrow
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

        # Tier summary sentence
        if tier_jbv_changes:
            avg_chg = sum(tier_jbv_changes) / len(tier_jbv_changes)
            if avg_chg > 3:
                tier_summary = f"{tier} products are trending upward on average ({avg_chg:+.1f}% over 30 days)."
            elif avg_chg < -3:
                tier_summary = f"{tier} products are under selling pressure ({avg_chg:+.1f}% over 30 days)."
            else:
                tier_summary = f"{tier} products have been broadly stable over the past 30 days (avg {avg_chg:+.1f}%)."
        else:
            tier_summary = f"Insufficient data for {tier} trend summary."

        sec4_html_parts.append(f"""
        <div class="tier-section">
            <h3 class="tier-heading badge-{tier.lower()}">{tier} Materials</h3>
            <p class="tier-summary">{tier_summary}</p>
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
""")

    sec4_html = '\n'.join(sec4_html_parts)

    # Rankings table rows
    ranking_rows = ''
    for a in sorted_analyses:
        rc  = a['row_class']
        sig = a['signal']
        sc  = signal_class(sig)
        ranking_rows += (
            f"<tr class='{rc}' data-tier='{a['tier']}'>"
            f"<td>{a['name']}</td>"
            f"<td><span class='badge-{a['tier'].lower()}'>{a['tier']}</span></td>"
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
<title>Moon Ore Margin Report — LX-ZOJ</title>
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
    --r4-col:  #4a9eff;
    --r8-col:  #34d058;
    --r16-col: #f4a700;
    --r32-col: #d97bff;
    --r64-col: #ff6b6b;
  }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    line-height: 1.5;
  }}
  a {{ color: var(--cyan); text-decoration: none; }}

  /* ── Layout ── */
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
  .report-meta {{
    color: var(--muted); font-size: 11px; margin-top: 6px;
  }}
  .report-params {{
    display: flex; flex-wrap: wrap; gap: 16px;
    margin-top: 10px; font-size: 11px; color: var(--muted);
  }}
  .report-params span {{ color: var(--text); }}

  /* ── Section headings ── */
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

  /* ── Stat cards ── */
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

  /* ── Exec summary paragraph ── */
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

  /* ── Tables ── */
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

  /* ── Tier badges ── */
  .badge-r4  {{ color: var(--r4-col);  font-weight: 700; }}
  .badge-r8  {{ color: var(--r8-col);  font-weight: 700; }}
  .badge-r16 {{ color: var(--r16-col); font-weight: 700; }}
  .badge-r32 {{ color: var(--r32-col); font-weight: 700; }}
  .badge-r64 {{ color: var(--r64-col); font-weight: 700; }}

  /* ── Signal badges ── */
  .signal {{ display: inline-block; padding: 1px 7px; border-radius: 3px; font-size: 10px; font-weight: 700; }}
  .sig-strong-buy {{ background: #004a20; color: #00e676; }}
  .sig-buy        {{ background: #003520; color: #34d058; }}
  .sig-watch      {{ background: #3a2e00; color: #ffcc44; }}
  .sig-marginal   {{ background: #2a2000; color: #aa9900; }}
  .sig-avoid      {{ background: #3a0000; color: #ff3d3d; }}
  .sig-thin       {{ background: #202040; color: #aaaaff; }}
  .sig-nodata     {{ background: #1a2535; color: #5a7090; }}

  /* ── Positive/negative colors ── */
  .pos     {{ color: var(--green); }}
  .neg     {{ color: var(--red); }}
  .neutral {{ color: var(--muted); }}
  .nodata  {{ color: var(--muted); font-style: italic; }}

  /* ── Filter buttons ── */
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

  /* ── Family cards ── */
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
  .family-tier {{ font-size: 12px; font-weight: 700; }}
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

  /* ── Sparklines ── */
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

  /* ── Tier section ── */
  .tier-section {{ margin-bottom: 24px; }}
  .tier-heading {{
    font-size: 14px; font-weight: 700;
    margin-bottom: 6px;
    padding: 4px 10px;
    background: var(--bg3);
    border-radius: 4px;
    display: inline-block;
  }}
  .tier-summary {{
    font-size: 12px; color: var(--muted);
    margin-bottom: 10px;
  }}

  /* ── Rankings table container ── */
  #rankings-table-container {{ max-height: 600px; overflow-y: auto; }}
  .variant-table td, .variant-table th {{ padding: 5px 8px; }}

  /* ── Responsive ── */
  @media (max-width: 768px) {{
    .stat-card {{ min-width: 140px; }}
    .sparkline-row .spark-wrap {{ min-width: 100px; }}
  }}
</style>
</head>
<body>

<div class="report-header">
  <div class="container" style="padding-bottom:0;">
    <h1>Moon Ore Margin Report — LX-ZOJ</h1>
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

  <!-- ── Section 1: Executive Summary ── -->
  <h2 class="section-title">Executive Summary</h2>
  <div class="exec-para">{es['paragraph']}</div>
  <div class="stat-cards">
    {cards_html}
  </div>

  <!-- ── Section 2: Rankings Table ── -->
  <h2 class="section-title">Ore Rankings</h2>
  <div class="filter-bar">
    <button class="filter-btn active" onclick="filterRankings('all')">All</button>
    <button class="filter-btn badge-r4"  onclick="filterRankings('R4')">R4</button>
    <button class="filter-btn badge-r8"  onclick="filterRankings('R8')">R8</button>
    <button class="filter-btn badge-r16" onclick="filterRankings('R16')">R16</button>
    <button class="filter-btn badge-r32" onclick="filterRankings('R32')">R32</button>
    <button class="filter-btn badge-r64" onclick="filterRankings('R64')">R64</button>
  </div>
  <div id="rankings-table-container">
    <table class="data-table" id="rankings-table">
      <thead><tr>
        <th>Name</th>
        <th>Tier</th>
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

  <!-- ── Section 3: Family Cards ── -->
  <h2 class="section-title">Per-Ore Family Analysis</h2>
  <div class="filter-bar" id="family-filter-bar">
    <button class="filter-btn active" onclick="filterFamilies('all', this)">All Tiers</button>
    <button class="filter-btn badge-r4"  onclick="filterFamilies('R4',  this)">R4</button>
    <button class="filter-btn badge-r8"  onclick="filterFamilies('R8',  this)">R8</button>
    <button class="filter-btn badge-r16" onclick="filterFamilies('R16', this)">R16</button>
    <button class="filter-btn badge-r32" onclick="filterFamilies('R32', this)">R32</button>
    <button class="filter-btn badge-r64" onclick="filterFamilies('R64', this)">R64</button>
  </div>
  <div class="family-cards" id="family-cards-container">
    {sec3_html}
  </div>

  <!-- ── Section 4: Product Market Overview ── -->
  <h2 class="section-title">Product Market Overview</h2>
  {sec4_html}

</div><!-- /container -->

<script>
// ── Filter: Rankings Table ──────────────────────────────────────────────────
function filterRankings(tier) {{
  var rows  = document.querySelectorAll('#rankings-tbody tr');
  var btns  = document.querySelectorAll('.filter-bar .filter-btn');
  // deactivate all ranking filter buttons (first filter-bar only)
  document.querySelector('.filter-bar').querySelectorAll('.filter-btn').forEach(function(b) {{
    b.classList.remove('active');
  }});
  event.target.classList.add('active');

  rows.forEach(function(r) {{
    if (tier === 'all' || r.dataset.tier === tier) {{
      r.style.display = '';
    }} else {{
      r.style.display = 'none';
    }}
  }});
}}

// ── Filter: Family Cards ────────────────────────────────────────────────────
function filterFamilies(tier, btn) {{
  document.querySelectorAll('#family-filter-bar .filter-btn').forEach(function(b) {{
    b.classList.remove('active');
  }});
  btn.classList.add('active');
  document.querySelectorAll('#family-cards-container .family-card').forEach(function(card) {{
    if (tier === 'all' || card.dataset.tier === tier) {{
      card.style.display = '';
    }} else {{
      card.style.display = 'none';
    }}
  }});
}}
</script>

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

    # Compute 14d product JBV for Section 4 (inject into prod_jbv dicts)
    d14 = (datetime.now(timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%d')
    prod_jbv_14d = {}
    for pid in ALL_PRODUCT_IDS:
        prod_jbv_14d[pid] = get_price_at(daily_hist, pid, d14, 'jbv')

    # Recompute section 4 14d changes — patch the product_breakdown chg14
    for a in analyses:
        for pb in a['product_breakdown']:
            mid   = pb['id']
            jbv_n = prod_jbv_now.get(mid)
            jbv_14 = prod_jbv_14d.get(mid)
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

    print(f"Done. Opening in browser...")
    webbrowser.open(f'file:///{OUT_PATH.replace(os.sep, "/")}')
    print(f"Report saved: {OUT_PATH}")


if __name__ == '__main__':
    main()
