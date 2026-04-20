"""
==========================================
FETCH HIGH-SEC GANK CANDIDATES
==========================================
Queries zKillboard using exact victim ship type IDs.
Uses /shipTypeID/{id}/victims/ which returns ONLY kills
where that ship was the victim — no group-level page grinding.

Entity hierarchy per attacker:
  - Alliance if present
  - Corporation if no alliance and not NPC corp (ID >= 2,000,000)
  - Character only if in an NPC corp

Processed killmail IDs are tracked so daily runs skip already-seen kills.

Also detects cyno alts: attackers using cyno weapons in low-sec.
==========================================
"""

import requests
import sqlite3
import os
import time
from datetime import datetime, timezone

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')

ESI_BASE    = 'https://esi.evetech.net/latest'
ZKILL_BASE  = 'https://zkillboard.com/api'
DELAY       = 1.0   # seconds between zKillboard requests (required)
ESI_TIMEOUT = 8     # seconds per ESI call

HEADERS = {'User-Agent': 'EVE Market Tool / Hamektok Hakaari'}

# Verified against ESI + Adam4Eve 2026-04-14
HAULER_SHIPS = {
    # T1 Industrials
    648:   'Badger',
    1944:  'Bestower',
    655:   'Epithal',
    651:   'Hoarder',
    657:   'Iteron Mark V',
    654:   'Kryos',
    652:   'Mammoth',
    656:   'Miasmos',
    650:   'Nereus',
    19744: 'Sigil',
    649:   'Tayra',
    653:   'Wreathe',
    # Freighters
    20185: 'Charon',
    20189: 'Fenrir',
    20187: 'Obelisk',
    20183: 'Providence',
    34328: 'Bowhead',
    81040: 'Avalanche',
    # Jump Freighters
    28844: 'Rhea',
    28848: 'Anshar',
    28850: 'Ark',
    28846: 'Nomad',
    # Deep Space Transports
    12753: 'Impel',
    12731: 'Bustard',
    12745: 'Occator',
    12747: 'Mastodon',
    # Blockade Runners
    12729: 'Crane',
    12733: 'Prorator',
    12743: 'Viator',
    12735: 'Prowler',
    # Expedition Frigates (mining/exploration)
    32880: 'Venture',
    89648: 'Venture Consortium Issue',
    33697: 'Prospect',
    37135: 'Endurance',
    89240: 'Pioneer',
    89647: 'Pioneer Consortium Issue',
    91174: 'Perseverance',
    89649: 'Outrider',
    # Mining Barges
    17480: 'Procurer',
    17478: 'Retriever',
    17476: 'Covetor',
    # Exhumers
    22546: 'Skiff',
    22548: 'Mackinaw',
    22544: 'Hulk',
    # Industrial Command Ships
    42244: 'Porpoise',
    28606: 'Orca',
    # Salvager / Misc
    2998:  'Noctis',
    # New-era industrials
    81008: 'Squall',
    81046: 'Deluge',
    81047: 'Torrent',
}

# Covert-cyno-capable ship types.
# A character in an NPC corp flying one of these on a hauler kill is almost
# certainly a cyno scout / tackle alt.
#
# Group 830 — Covert Ops frigates
COVERT_OPS = {11176, 11184, 11188, 11192}          # Cheetah, Anathema, Helios, Buzzard
# Group 906 — Recon Ships (all; Force Recons have covert cyno, Combat Recons don't,
#             but an NPC-corp Recon on a hauler kill is suspicious either way)
RECON_SHIPS = {11957, 11959, 11961, 11963, 11967, 11969, 11971, 11978}
#              Falcon, Arazu, Curse, Rook, Lachesis, Pilgrim, Huginn, Rapier
# Group 898 — Black Ops battleships
BLACK_OPS   = {22428, 22430, 22436, 22440}          # Sin, Redeemer, Widow, Panther
# Sisters of Eve ships that can also fit covert cynos
SOE_SHIPS   = {33468, 33470}                        # Astero, Stratios

CYNO_CAPABLE_SHIPS = COVERT_OPS | RECON_SHIPS | BLACK_OPS | SOE_SHIPS

# Ships that arrive via cyno — required co-presence on the killmail to confirm
# this was a coordinated cyno drop and not just a roaming Recon.
#
# Group 831 — Stealth Bombers (bridge through Black Ops covert cyno)
STEALTH_BOMBERS = {11379, 12034, 11387, 12032}   # Hound, Purifier, Manticore, Nemesis
# Group 963 — T3 Cruisers (can use covert cynos)
T3_CRUISERS     = {29984, 29986, 29988, 29990}   # Tengu, Legion, Proteus, Loki
# Dreadnoughts (group 547)
DREADS          = {19720, 19722, 19724, 19726}   # Revelation, Naglfar, Moros, Phoenix
# Carriers (group 485)
CARRIERS        = {23911, 23915, 23917, 23919}   # Thanatos, Archon, Nidhoggur, Chimera
# Force Auxiliaries (group 1538)
FAX             = {37604, 37605, 37606, 37607}   # Apostle, Lif, Minokawa, Ninazu

# Full set: a cyno_alt candidate is only flagged if at least one of these
# is also present on the kill (confirming the cyno was actually used)
CYNO_JUMPER_SHIPS = STEALTH_BOMBERS | T3_CRUISERS | BLACK_OPS | DREADS | CARRIERS | FAX

NPC_CORP_THRESHOLD  = 2_000_000

# Faction Warfare militia factions and their opposing counterpart.
# A kill where the victim is enlisted in one FW faction and an attacker
# is enlisted in the opposing faction is legitimate militia combat — not a gank.
FW_OPPOSING = {
    500001: 500004,  # Caldari State  vs Gallente Federation
    500004: 500001,  # Gallente Federation vs Caldari State
    500003: 500002,  # Amarr Empire   vs Minmatar Republic
    500002: 500003,  # Minmatar Republic vs Amarr Empire
}


def is_fw_kill(esi):
    """Return True if this is a faction-warfare combat kill (not a gank)."""
    victim_faction = esi.get('victim', {}).get('faction_id')
    if not victim_faction:
        return False
    opposing = FW_OPPOSING.get(victim_faction)
    if not opposing:
        return False
    return any(
        a.get('faction_id') == opposing and a.get('character_id', 0) > 0
        for a in esi.get('attackers', [])
    )


# ── DB setup ──────────────────────────────────────────────────────────────────

def ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS system_security_cache (
            solar_system_id INTEGER PRIMARY KEY,
            security_status REAL NOT NULL,
            system_name     TEXT,
            fetched_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gank_watchlist (
            entity_id   INTEGER NOT NULL,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('character','corporation','alliance')),
            entity_name TEXT,
            kill_count  INTEGER DEFAULT 1,
            tag         TEXT DEFAULT 'ganker',
            added_by    TEXT DEFAULT 'auto',
            added_at    TEXT NOT NULL,
            PRIMARY KEY (entity_id, entity_type)
        );

        CREATE TABLE IF NOT EXISTS gank_kill_log (
            killmail_id      INTEGER PRIMARY KEY,
            killmail_time    TEXT,
            solar_system_id  INTEGER,
            system_name      TEXT,
            victim_ship_name TEXT,
            entity_id        INTEGER,
            entity_type      TEXT,
            entity_name      TEXT,
            tag              TEXT,
            logged_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS gank_processed_kills (
            killmail_id  INTEGER PRIMARY KEY,
            processed_at TEXT NOT NULL
        );
    """)
    conn.commit()


# ── ESI helpers ───────────────────────────────────────────────────────────────

def get_system_info(conn, solar_system_id):
    """Returns (security_status, system_name), caches result."""
    row = conn.execute(
        'SELECT security_status, system_name FROM system_security_cache WHERE solar_system_id = ?',
        (solar_system_id,)
    ).fetchone()
    if row:
        return row[0], row[1] or ''
    try:
        r = requests.get(f'{ESI_BASE}/universe/systems/{solar_system_id}/',
                         headers=HEADERS, timeout=ESI_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            sec  = data.get('security_status', -1.0)
            name = data.get('name', '')
            conn.execute(
                'INSERT OR REPLACE INTO system_security_cache VALUES (?, ?, ?, ?)',
                (solar_system_id, sec, name, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            return sec, name
    except Exception:
        pass
    return -1.0, ''


def get_esi_killmail(killmail_id, killmail_hash):
    try:
        r = requests.get(f'{ESI_BASE}/killmails/{killmail_id}/{killmail_hash}/',
                         headers=HEADERS, timeout=ESI_TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def resolve_names(entity_ids):
    if not entity_ids:
        return {}
    try:
        r = requests.post(f'{ESI_BASE}/universe/names/',
                          json=list(entity_ids), headers=HEADERS, timeout=ESI_TIMEOUT)
        if r.status_code == 200:
            return {item['id']: item['name'] for item in r.json()}
    except Exception:
        pass
    return {}


def fetch_zkill(url, progress_cb=None):
    if progress_cb:
        progress_cb(f'GET {url}')
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


# ── Entity hierarchy ──────────────────────────────────────────────────────────

def top_entity(attacker):
    """Return (entity_id, entity_type) for highest-level non-NPC entity."""
    alli_id = attacker.get('alliance_id')
    if alli_id:
        return alli_id, 'alliance'
    corp_id = attacker.get('corporation_id')
    if corp_id and corp_id >= NPC_CORP_THRESHOLD:
        return corp_id, 'corporation'
    char_id = attacker.get('character_id')
    if char_id:
        return char_id, 'character'
    return None, None


# ── DB write helpers ──────────────────────────────────────────────────────────

def upsert_entity(conn, entity_id, entity_type, name, tag):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO gank_watchlist
            (entity_id, entity_type, entity_name, kill_count, tag, added_by, added_at)
        VALUES (?, ?, ?, 1, ?, 'auto', ?)
        ON CONFLICT(entity_id, entity_type) DO UPDATE SET
            kill_count  = kill_count + 1,
            entity_name = COALESCE(excluded.entity_name, entity_name),
            tag         = CASE WHEN gank_watchlist.added_by = 'manual'
                               THEN gank_watchlist.tag
                               ELSE excluded.tag END
    """, (entity_id, entity_type, name, tag, now))


def log_kill(conn, killmail_id, killmail_time, sys_id, sys_name,
             ship_name, entity_id, entity_type, entity_name, tag):
    conn.execute("""
        INSERT OR IGNORE INTO gank_kill_log
            (killmail_id, killmail_time, solar_system_id, system_name,
             victim_ship_name, entity_id, entity_type, entity_name, tag, logged_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (killmail_id, killmail_time, sys_id, sys_name,
          ship_name, entity_id, entity_type, entity_name, tag,
          datetime.now(timezone.utc).isoformat()))


def mark_processed(conn, killmail_id):
    conn.execute(
        'INSERT OR IGNORE INTO gank_processed_kills VALUES (?, ?)',
        (killmail_id, datetime.now(timezone.utc).isoformat())
    )


def is_processed(conn, killmail_id):
    return conn.execute(
        'SELECT 1 FROM gank_processed_kills WHERE killmail_id = ?',
        (killmail_id,)
    ).fetchone() is not None


# ── Ganker pass ───────────────────────────────────────────────────────────────

def run_fetch_pass(conn, max_pages=5, cutoff=None, progress_cb=None):
    """
    Single pass for all 50 hauler/miner ship types.

    For each kill in losses/shipTypeID/{id}/ (victim-only, newest-first):
      - High-sec + no war + human attackers  → tag attackers as 'ganker'
      - Low-sec + any attacker used a cyno   → tag those attackers as 'cyno_alt'

    The same kill can produce both ganker and cyno_alt entries if applicable.
    """
    g_processed = 0
    g_added     = 0
    c_processed = 0
    c_added     = 0
    total       = len(HAULER_SHIPS)

    for idx, (type_id, type_name) in enumerate(HAULER_SHIPS.items(), 1):
        if progress_cb:
            progress_cb(f'[{idx}/{total}] {type_name}…')

        for page in range(1, max_pages + 1):
            # losses/ = this ship as VICTIM only, sorted newest-first
            url  = f'{ZKILL_BASE}/losses/shipTypeID/{type_id}/page/{page}/'
            data = fetch_zkill(url, progress_cb)
            if not data:
                break

            stop_ship = False
            for entry in data:
                km_id   = entry.get('killmail_id')
                zkb     = entry.get('zkb', {})
                km_hash = zkb.get('hash')
                if not km_id or not km_hash:
                    continue

                if is_processed(conn, km_id):
                    stop_ship = True
                    break

                # NPC-only: skip immediately
                if zkb.get('npc'):
                    mark_processed(conn, km_id)
                    continue

                # Pre-filter: only bother with ESI for highsec OR unlabelled
                # (lowsec kills may have cyno alts — don't skip them blindly)
                labels     = zkb.get('labels', [])
                loc_labels = [l for l in labels if l.startswith('loc:')]
                is_highsec_label = 'loc:highsec' in loc_labels
                is_lowsec_label  = 'loc:lowsec'  in loc_labels

                # Skip null/wh/pochven
                if loc_labels and not is_highsec_label and not is_lowsec_label:
                    mark_processed(conn, km_id)
                    continue

                # ── ESI fetch ──
                esi = get_esi_killmail(km_id, km_hash)
                if not esi:
                    mark_processed(conn, km_id)
                    continue

                # Date cutoff — newest-first so stop whole ship on first old kill
                if cutoff:
                    km_time_str = esi.get('killmail_time', '')
                    if km_time_str:
                        km_dt = datetime.strptime(km_time_str[:19], '%Y-%m-%dT%H:%M:%S')
                        km_dt = km_dt.replace(tzinfo=timezone.utc)
                        if km_dt < cutoff:
                            stop_ship = True
                            mark_processed(conn, km_id)
                            break

                sys_id = esi.get('solar_system_id')
                if not sys_id:
                    mark_processed(conn, km_id)
                    continue
                sec, sys_name = get_system_info(conn, sys_id)

                victim_type = esi.get('victim', {}).get('ship_type_id', 0)
                km_time     = esi.get('killmail_time', '')
                ship_name   = HAULER_SHIPS.get(victim_type, f'Ship [{victim_type}]')
                human_atk   = [a for a in esi.get('attackers', [])
                               if a.get('character_id', 0) > 0]

                # ── Path A: high-sec gank ──────────────────────────────────
                if (sec >= 0.45 and not esi.get('war_id') and not is_fw_kill(esi)
                        and victim_type in HAULER_SHIPS and human_atk):
                    g_processed += 1
                    seen = set()
                    for a in human_atk:
                        eid, etype = top_entity(a)
                        if eid and (eid, etype) not in seen:
                            seen.add((eid, etype))
                    names = resolve_names({eid for eid, _ in seen})
                    for eid, etype in seen:
                        ename = names.get(eid)
                        upsert_entity(conn, eid, etype, ename, 'ganker')
                        log_kill(conn, km_id, km_time, sys_id, sys_name,
                                 ship_name, eid, etype, ename, 'ganker')
                        g_added += 1

                # ── Path B: low-sec cyno scout kill ───────────────────────
                # Two-part signal:
                # 1. At least one attacker is in an NPC corp flying a covert-
                #    cyno-capable ship (Covert Ops, Recon, Black Ops, SoE).
                # 2. At least one OTHER attacker flew a ship that would arrive
                #    via cyno (Stealth Bomber, T3C, Black Ops, Dread, Carrier,
                #    FAX). This confirms it was a coordinated drop, not just a
                #    roaming Recon solo-killing a cheap hauler.
                elif 0.0 <= sec < 0.45:
                    cyno_atk = [
                        a for a in human_atk
                        if a.get('ship_type_id') in CYNO_CAPABLE_SHIPS
                        and a.get('corporation_id', NPC_CORP_THRESHOLD) < NPC_CORP_THRESHOLD
                    ]
                    has_jumper = any(
                        a.get('ship_type_id') in CYNO_JUMPER_SHIPS
                        for a in human_atk
                    )
                    if cyno_atk and has_jumper:
                        c_processed += 1
                        seen = set()
                        for a in cyno_atk:
                            # These alts are in NPC corps — store the character,
                            # not the corp (NPC corps aren't useful to flag).
                            char_id = a.get('character_id')
                            if char_id:
                                seen.add((char_id, 'character'))
                        names = resolve_names({eid for eid, _ in seen})
                        for eid, etype in seen:
                            ename = names.get(eid)
                            upsert_entity(conn, eid, etype, ename, 'cyno_alt')
                            log_kill(conn, km_id, km_time, sys_id, sys_name,
                                     ship_name, eid, etype, ename, 'cyno_alt')
                            c_added += 1

                mark_processed(conn, km_id)
                conn.commit()

            if stop_ship:
                break

            time.sleep(DELAY)

    if progress_cb:
        progress_cb(f'Done — gankers: {g_processed} kills, {g_added} upserts | '
                    f'cyno alts: {c_processed} kills, {c_added} upserts')
    return g_processed, g_added, c_processed, c_added

# ── Main ──────────────────────────────────────────────────────────────────────

def run(past_seconds=None, max_pages=5, hours=None, progress_cb=None):
    """Entry point — called standalone or from admin dashboard.

    hours: if set, only process kills from the last N hours (e.g. 24 or 48).
    """
    conn = sqlite3.connect(DB_PATH)
    ensure_tables(conn)

    cutoff = None
    if hours:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        if progress_cb:
            progress_cb(f'Date cutoff: {cutoff.strftime("%Y-%m-%d %H:%M UTC")} ({hours}h lookback)')

    g_kills, g_added, c_kills, c_added = run_fetch_pass(conn, max_pages, cutoff, progress_cb)

    conn.close()

    summary = (f'Done — gankers: {g_kills} kills, {g_added} upserts; '
               f'cyno alts: {c_kills} kills, {c_added} upserts')
    if progress_cb:
        progress_cb(summary)
    return summary


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=5,
                        help='Max pages per ship type (default 5)')
    parser.add_argument('--hours', type=int, default=None,
                        help='Only process kills from last N hours (e.g. 24)')
    args = parser.parse_args()
    print(f'Fetching up to {args.pages} pages per ship type ({len(HAULER_SHIPS)} ships)...\n')
    result = run(max_pages=args.pages, hours=args.hours, progress_cb=print)
    print(f'\n{result}')
