"""
BOM expansion engine — shared by admin dashboard and Flask app.
Recursively expands a manufacturing BOM using blueprints.jsonl and
prices from market_price_snapshots (local) + adjusted_prices (ESI fallback).
"""
import json
import math
import os
import sqlite3
from collections import defaultdict

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR  = os.path.dirname(SCRIPT_DIR)
BLUEPRINTS_PATH = os.path.join(PROJECT_DIR, 'sde', 'blueprints.jsonl')

# Module-level cache so blueprints are loaded once per process
_blueprints_by_product = None


def _load_blueprints():
    global _blueprints_by_product
    if _blueprints_by_product is not None:
        return _blueprints_by_product
    _blueprints_by_product = {}
    with open(BLUEPRINTS_PATH) as f:
        for line in f:
            bp = json.loads(line)
            if 'activities' in bp and 'manufacturing' in bp['activities']:
                for p in bp['activities']['manufacturing'].get('products', []):
                    _blueprints_by_product[p['typeID']] = bp
    return _blueprints_by_product


def expand_bom(type_id, qty, db_path, bp_me=10, max_depth=5):
    """
    Recursively expand the manufacturing BOM for `type_id` × `qty`.

    ME/rig bonuses applied per memory spec:
      L0 hull job:   rig_me = mfg_rig_ship_me  (2.4%)
      L1+ comp jobs: rig_me = mfg_rig_comp_me  (2.0%)

    EIV for job cost calculation always uses JSV (best sell / ESI average).

    Returns a dict:
    {
        'ok':        bool,
        'error':     str or None,
        'item_name': str,
        'qty':       int,
        'materials': [ {type_id, name, qty, jbv, jsv, basis, pct, has_local_price}, ... ],
        'jobs':      [ {type_id, name, runs, depth, eiv, job_cost}, ... ],
        'config':    { sci, fac_tax, rig_hull, rig_comp },
    }
    """
    blueprints = _load_blueprints()

    if type_id not in blueprints:
        return {'ok': False, 'error': f'No manufacturing blueprint found for type_id {type_id}',
                'materials': [], 'jobs': [], 'item_name': '', 'qty': qty, 'config': {}}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── Config ────────────────────────────────────────────────────────────
    cur.execute("SELECT key, value FROM site_config WHERE key LIKE 'mfg_%'")
    _cfg = {}
    for r in cur.fetchall():
        try:
            _cfg[r['key']] = float(r['value'])
        except (ValueError, TypeError):
            _cfg[r['key']] = r['value']

    sci      = _cfg.get('mfg_sci',          5.74)
    fac_tax  = _cfg.get('mfg_facility_tax', 0.5)
    rig_hull = _cfg.get('mfg_rig_ship_me',  2.4)
    rig_comp = _cfg.get('mfg_rig_comp_me',  2.0)

    # ── Prices ────────────────────────────────────────────────────────────
    cur.execute('SELECT type_id, best_sell, best_buy FROM market_price_snapshots')
    local_prices = {}
    for r in cur.fetchall():
        local_prices[r['type_id']] = {
            'sell': r['best_sell'] or 0,
            'buy':  r['best_buy']  or 0,
        }

    cur.execute('SELECT type_id, adjusted_price, average_price FROM adjusted_prices')
    adj_prices = {r['type_id']: {'adj': r['adjusted_price'] or 0,
                                  'avg': r['average_price']  or 0}
                  for r in cur.fetchall()}

    # ── Type info ─────────────────────────────────────────────────────────
    cur.execute('SELECT type_id, type_name FROM inv_types')
    names = {r['type_id']: r['type_name'] for r in cur.fetchall()}

    item_name = names.get(type_id, f'ID:{type_id}')
    conn.close()

    # ── Price helpers ──────────────────────────────────────────────────────
    def jsv(tid):
        p = local_prices.get(tid)
        if p and p['sell'] > 0:
            return p['sell']
        ap = adj_prices.get(tid)
        if ap and ap['avg'] > 0:
            return ap['avg']
        return 0

    def jbv(tid):
        p = local_prices.get(tid)
        if p and p['buy'] > 0:
            return p['buy']
        return 0

    def has_local(tid):
        p = local_prices.get(tid)
        return bool(p and p['buy'] > 0)

    # ── Recursive expansion ────────────────────────────────────────────────
    buy_items = defaultdict(int)
    job_list  = []

    def expand(tid, need_qty, depth=0, rig_me=None):
        if rig_me is None:
            rig_me = rig_hull if depth == 0 else rig_comp
        bp = blueprints.get(tid)
        if not bp or depth >= max_depth:
            buy_items[tid] += need_qty
            return
        mfg      = bp['activities']['manufacturing']
        prod_qty = next(p['quantity'] for p in mfg.get('products', []) if p['typeID'] == tid)
        runs     = math.ceil(need_qty / prod_qty)
        mats     = mfg.get('materials', [])
        # EIV uses JSV for all inputs
        eiv      = sum(m['quantity'] * runs * jsv(m['typeID']) for m in mats)
        jc       = eiv * (sci / 100) * (1 + fac_tax / 100)
        job_list.append({
            'type_id':  tid,
            'name':     names.get(tid, f'ID:{tid}'),
            'runs':     runs,
            'depth':    depth,
            'eiv':      eiv,
            'job_cost': jc,
        })
        for m in mats:
            mid   = m['typeID']
            base  = m['quantity']
            after_bp  = math.ceil(base * (1 - bp_me / 100))
            final_qty = max(1, math.ceil(after_bp * (1 - rig_me / 100))) * runs
            child_rig = rig_comp   # all sub-jobs use component rig
            if blueprints.get(mid) and depth < max_depth - 1:
                expand(mid, final_qty, depth + 1, child_rig)
            else:
                buy_items[mid] += final_qty

    expand(type_id, qty)

    # ── Build material list ────────────────────────────────────────────────
    materials = []
    for tid, need_qty in sorted(buy_items.items(), key=lambda x: names.get(x[0], '')):
        j = jsv(tid)
        b = jbv(tid)
        local = has_local(tid)
        materials.append({
            'type_id':        tid,
            'name':           names.get(tid, f'ID:{tid}'),
            'qty':            need_qty,
            'jbv':            b,
            'jsv':            j,
            'basis':          'JBV' if local else 'JSV',
            'pct':            100,
            'has_local_price': local,
            'has_price':      j > 0 or b > 0,
        })

    return {
        'ok':        True,
        'error':     None,
        'item_name': item_name,
        'qty':       qty,
        'materials': materials,
        'jobs':      job_list,
        'config':    {
            'sci':      sci,
            'fac_tax':  fac_tax,
            'rig_hull': rig_hull,
            'rig_comp': rig_comp,
        },
    }


def calc_totals(materials, jobs):
    """
    Given a materials list (with current basis/pct) and jobs list,
    return a totals dict.
    """
    jbv_mat = 0.0
    jsv_mat = 0.0
    for m in materials:
        price     = m['jbv'] if m['basis'] == 'JBV' else m['jsv']
        effective = price * (m['pct'] / 100)
        line      = m['qty'] * effective
        if m['basis'] == 'JBV':
            jbv_mat += line
        else:
            jsv_mat += line
    job_total = sum(j['job_cost'] for j in jobs)
    subtotal  = jbv_mat + jsv_mat + job_total
    return {
        'jbv_mat':  jbv_mat,
        'jsv_mat':  jsv_mat,
        'job_cost': job_total,
        'subtotal': subtotal,
    }
