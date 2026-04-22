"""
Analyze existing gank_kill_log entries for Faction Warfare kills.
Fetches each killmail from zKillboard + ESI, runs is_fw_kill(), reports contaminated entities.
"""

import sqlite3
import json
import time
import urllib.request
import urllib.error
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mydatabase.db')

FW_OPPOSING = {
    500001: {500004, 500010},  # Caldari vs Gallente + Guristas
    500004: {500001, 500010},  # Gallente vs Caldari + Guristas
    500010: {500001, 500004},  # Guristas vs Caldari + Gallente
    500003: {500002, 500011},  # Amarr vs Minmatar + Angel Cartel
    500002: {500003, 500011},  # Minmatar vs Amarr + Angel Cartel
    500011: {500003, 500002},  # Angel Cartel vs Amarr + Minmatar
}

FACTION_NAMES = {
    500001: 'Caldari State',
    500002: 'Minmatar Republic',
    500003: 'Amarr Empire',
    500004: 'Gallente Federation',
    500010: 'Guristas Pirates',
    500011: 'Angel Cartel',
}

def is_fw_kill(esi):
    victim_faction = esi.get('victim', {}).get('faction_id')
    if not victim_faction:
        return False, None, None
    opposing = FW_OPPOSING.get(victim_faction)
    if not opposing:
        return False, None, None
    attacker_faction = next(
        (a.get('faction_id') for a in esi.get('attackers', [])
         if a.get('faction_id') in opposing and a.get('character_id', 0) > 0),
        None
    )
    if attacker_faction:
        return True, FACTION_NAMES.get(victim_faction, str(victim_faction)), FACTION_NAMES.get(attacker_faction, str(attacker_faction))
    return False, None, None

def fetch_zkb(kill_id, retries=3):
    url = f'https://zkillboard.com/api/kills/killID/{kill_id}/'
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'InfiniteSolutions-GankAnalysis/1.0 (contact: Hamektok Hakaari)',
                'Accept': 'application/json',
            })
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            if data and isinstance(data, list) and data and 'zkb' in data[0]:
                return data[0]['zkb'].get('hash')
            return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f'  Rate limited on {kill_id}, sleeping 10s...')
                time.sleep(10)
            else:
                print(f'  HTTP {e.code} for kill {kill_id}')
                return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                print(f'  Error fetching zKB for {kill_id}: {e}')
                return None
    return None

def fetch_esi_killmail(kill_id, kill_hash, retries=3):
    url = f'https://esi.evetech.net/latest/killmails/{kill_id}/{kill_hash}/'
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'InfiniteSolutions-GankAnalysis/1.0',
                'Accept': 'application/json',
            })
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 420 or e.code == 429:
                print(f'  ESI rate limited on {kill_id}, sleeping 10s...')
                time.sleep(10)
            else:
                print(f'  ESI HTTP {e.code} for kill {kill_id}')
                return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                print(f'  ESI error for {kill_id}: {e}')
                return None
    return None

def main():
    conn = sqlite3.connect(DB_PATH)

    # Get all kills with their associated attacker entities
    rows = conn.execute("""
        SELECT DISTINCT k.killmail_id, k.entity_id, k.entity_name, k.entity_type
        FROM gank_kill_log k
        ORDER BY k.killmail_id
    """).fetchall()

    # Build kill_id -> list of (entity_id, entity_name, entity_type)
    kill_attackers = {}
    for kill_id, att_id, att_name, att_type in rows:
        kill_attackers.setdefault(kill_id, []).append((att_id, att_name, att_type))

    kill_ids = list(kill_attackers.keys())
    total = len(kill_ids)
    print(f'Analyzing {total} kills...')
    print('This will take ~{:.0f} minutes (1 req/sec ZKB + ESI calls).'.format(total / 40))
    print()

    fw_kills = {}       # kill_id -> (victim_faction, attacker_faction)
    hash_errors = []
    esi_errors = []
    not_fw = 0

    for i, kill_id in enumerate(kill_ids):
        if i % 50 == 0 and i > 0:
            print(f'  Progress: {i}/{total} ({not_fw} clean, {len(fw_kills)} FW)')

        # Fetch hash from zKillboard
        kill_hash = fetch_zkb(kill_id)
        time.sleep(1.1)  # zKB rate limit

        if not kill_hash:
            hash_errors.append(kill_id)
            continue

        # Fetch ESI killmail
        esi = fetch_esi_killmail(kill_id, kill_hash)
        time.sleep(0.3)

        if not esi:
            esi_errors.append(kill_id)
            continue

        is_fw, vf, af = is_fw_kill(esi)
        if is_fw:
            fw_kills[kill_id] = (vf, af)
        else:
            not_fw += 1

    conn.close()

    print()
    print('=' * 60)
    print(f'RESULTS: {total} kills analyzed')
    print(f'  Clean kills:   {not_fw}')
    print(f'  FW kills:      {len(fw_kills)}')
    print(f'  Hash errors:   {len(hash_errors)}')
    print(f'  ESI errors:    {len(esi_errors)}')
    print()

    if fw_kills:
        print('FW KILL DETAILS:')
        # Group by entity
        entity_fw_kills = {}
        for kill_id, (vf, af) in fw_kills.items():
            for att_id, att_name, att_type in kill_attackers[kill_id]:
                key = (att_name, att_type, att_id)
                entity_fw_kills.setdefault(key, []).append((kill_id, vf, af))

        # Sort by number of FW kills desc
        sorted_entities = sorted(entity_fw_kills.items(), key=lambda x: len(x[1]), reverse=True)

        print(f'{"Entity":<35} {"Type":<12} {"FW Kills":<10} {"Example Matchup"}')
        print('-' * 80)
        for (name, etype, eid), kills_list in sorted_entities:
            example_vf, example_af = kills_list[0][1], kills_list[0][2]
            matchup = f'{example_vf} vs {example_af}'
            print(f'{name:<35} {etype:<12} {len(kills_list):<10} {matchup}')

        print()
        print('ENTITIES TO REVIEW (in gank_watchlist):')
        # Only show entities that are in the watchlist
        conn2 = sqlite3.connect(DB_PATH)
        watchlist_ids = {r[0]: r[1] for r in conn2.execute(
            'SELECT entity_id, entity_name FROM gank_watchlist'
        ).fetchall()}
        conn2.close()

        in_watchlist = [(name, etype, eid, kills_list)
                        for (name, etype, eid), kills_list in sorted_entities
                        if eid in watchlist_ids]
        only_fw = []   # entities whose ALL kills are FW
        mixed = []     # entities with some FW, some real

        conn3 = sqlite3.connect(DB_PATH)
        for name, etype, eid, kills_list in in_watchlist:
            total_kills = conn3.execute(
                'SELECT COUNT(*) FROM gank_kill_log WHERE entity_id=?', (eid,)
            ).fetchone()[0]
            fw_count = len(kills_list)
            if fw_count >= total_kills:
                only_fw.append((name, etype, eid, fw_count, total_kills))
            else:
                mixed.append((name, etype, eid, fw_count, total_kills))
        conn3.close()

        if only_fw:
            print()
            print('  LIKELY FALSE POSITIVES (all kills are FW):')
            for name, etype, eid, fw_count, total_kills in only_fw:
                print(f'    [{eid}] {name} ({etype}) — {fw_count}/{total_kills} kills are FW')

        if mixed:
            print()
            print('  MIXED (some FW, some real gank kills):')
            for name, etype, eid, fw_count, total_kills in mixed:
                real = total_kills - fw_count
                print(f'    [{eid}] {name} ({etype}) — {fw_count} FW + {real} real kills')

    if hash_errors:
        print(f'\nKills where zKB hash could not be fetched ({len(hash_errors)}):')
        print(', '.join(str(k) for k in hash_errors[:20]))
        if len(hash_errors) > 20:
            print(f'  ... and {len(hash_errors) - 20} more')

    # Save results to a JSON file for review
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'fw_kill_analysis.json')
    output = {
        'total_kills': total,
        'fw_kill_count': len(fw_kills),
        'clean_kill_count': not_fw,
        'fw_kills': {str(k): {'victim_faction': v[0], 'attacker_faction': v[1]}
                     for k, v in fw_kills.items()},
        'hash_errors': hash_errors,
        'esi_errors': esi_errors,
    }
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f'\nFull results saved to: {out_path}')

if __name__ == '__main__':
    import sys
    if '--test' in sys.argv:
        # Quick sanity check: run only the first 5 kills
        _conn = sqlite3.connect(DB_PATH)
        _ids = [r[0] for r in _conn.execute(
            'SELECT DISTINCT killmail_id FROM gank_kill_log LIMIT 5'
        ).fetchall()]
        _conn.close()
        print(f'TEST MODE — checking kills: {_ids}')
        for kid in _ids:
            h = fetch_zkb(kid)
            time.sleep(1.1)
            if not h:
                print(f'  {kid}: NO HASH')
                continue
            esi = fetch_esi_killmail(kid, h)
            time.sleep(0.3)
            if not esi:
                print(f'  {kid}: NO ESI DATA')
                continue
            fw, vf, af = is_fw_kill(esi)
            print(f'  {kid}: FW={fw}  victim_faction={esi.get("victim",{}).get("faction_id")}  vf={vf}  af={af}')
    else:
        main()
