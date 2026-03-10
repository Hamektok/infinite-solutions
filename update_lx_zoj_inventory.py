"""
Update LX-ZOJ Inventory
Fetches inventory from LX-ZOJ citadel via ESI, stores snapshot in database,
and updates index.html with current stock levels.
"""
import requests
import sqlite3
import os
import sys
from datetime import datetime, timezone

# Add scripts directory to path for imports
SCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
sys.path.insert(0, SCRIPT_DIR)

# Import token manager and script utils
from token_manager import get_token

# ============================================
# CONFIGURATION
# ============================================
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')
HTML_PATH = os.path.join(PROJECT_DIR, 'index.html')
HTML_BACKUP_PATH = os.path.join(PROJECT_DIR, 'index.backup.html')

ESI_BASE_URL = 'https://esi.evetech.net/latest'

# Your character ID
CHARACTER_ID = 2114278577

# LX-ZOJ Structure ID
LX_ZOJ_STRUCTURE_ID = 1027625808467

# EVE container type IDs (Secure Containers, GSCs, etc.)
CONTAINER_TYPE_IDS = {3462, 3463, 3464, 3465, 3466, 11489, 17366, 33003, 33005, 33007, 33009, 33011}

# ============================================
# FUNCTIONS
# ============================================

def get_authenticated_headers():
    """Get headers with authentication token."""
    try:
        token = get_token()
        return {'Authorization': f'Bearer {token}'}
    except Exception as e:
        print(f"[ERROR] Failed to get access token: {e}")
        return None

def get_character_assets(headers):
    """Get all character assets from ESI."""
    all_assets = []
    page = 1

    print("Fetching character assets from ESI...")

    while True:
        url = f'{ESI_BASE_URL}/characters/{CHARACTER_ID}/assets/'
        params = {'page': page}

        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            assets = response.json()

            if not assets:
                break

            all_assets.extend(assets)
            print(f"  Page {page}: {len(assets)} assets")
            page += 1

        elif response.status_code == 404:
            break
        else:
            print(f"[ERROR] Fetching assets page {page}: {response.status_code}")
            break

    print(f"[OK] Total assets fetched: {len(all_assets)}")
    return all_assets

def filter_lx_zoj_items(assets):
    """Filter assets to LX-ZOJ structure hangar, including contents of containers.

    Each returned asset gets a '_container_item_id' key set to the item_id of
    the top-level hangar container it lives in (or None if directly in the hangar).
    """
    # Build a fast lookup: location_id -> [assets at that location]
    by_location = {}
    for asset in assets:
        loc = asset.get('location_id')
        if loc not in by_location:
            by_location[loc] = []
        by_location[loc].append(asset)

    # Start with items directly in the LX-ZOJ hangar.
    # Seed queue as (item, top_container_id) — top-level items have None.
    result = []
    visited_ids = set()
    queue = [(a, None) for a in by_location.get(LX_ZOJ_STRUCTURE_ID, [])
             if a.get('location_flag') == 'Hangar']

    # BFS: walk into any containers found in the hangar
    while queue:
        batch, queue = queue, []
        for item, top_cid in batch:
            item_id = item.get('item_id')
            if item_id in visited_ids:
                continue
            visited_ids.add(item_id)
            # Annotate with the inherited (or self-assigned) top-level container id
            item = dict(item)  # copy so we don't mutate the original ESI data
            item['_container_item_id'] = top_cid
            result.append(item)
            # If this item is itself a container, its children inherit item_id as top_cid
            child_top = item_id if top_cid is None else top_cid
            for child in by_location.get(item_id, []):
                queue.append((child, child_top))

    direct = sum(1 for a in result if a.get('location_id') == LX_ZOJ_STRUCTURE_ID)
    in_containers = len(result) - direct
    print(f"[OK] LX-ZOJ hangar: {direct} direct, {in_containers} in containers ({len(result)} total)")
    return result


def fetch_container_names_from_esi(headers, item_ids):
    """
    POST to ESI assets/names/ to retrieve custom container names.
    Returns a dict {item_id: name} for items that have custom names.
    ESI only returns entries for items that have been given custom names in-game.
    """
    if not item_ids:
        return {}

    url = f'{ESI_BASE_URL}/characters/{CHARACTER_ID}/assets/names/'
    try:
        response = requests.post(url, headers=headers, json=list(item_ids))
        if response.status_code == 200:
            names = {entry['item_id']: entry['name'] for entry in response.json()}
            print(f"[OK] Fetched {len(names)} custom container name(s) from ESI")
            return names
        else:
            print(f"[WARN] ESI names endpoint returned {response.status_code} — using fallback names")
            return {}
    except Exception as e:
        print(f"[WARN] Could not fetch container names from ESI: {e}")
        return {}


def store_container_snapshot(conn, lx_zoj_items, tracked_items, snapshot_time):
    """
    Store per-container inventory data in lx_zoj_container_snapshot.
    Groups tracked items by their _container_item_id (None = direct hangar).
    """
    from collections import defaultdict

    # Aggregate: {container_item_id: {type_id: qty}}
    container_qty = defaultdict(lambda: defaultdict(int))
    for asset in lx_zoj_items:
        type_id = asset.get('type_id')
        if type_id not in tracked_items:
            continue
        cid = asset.get('_container_item_id')  # None for direct hangar items
        container_qty[cid][type_id] += asset.get('quantity', 1)

    cursor = conn.cursor()
    rows_inserted = 0
    for cid, type_qtys in container_qty.items():
        if cid is None:
            continue  # Skip direct hangar items (not in any container)
        for type_id, qty in type_qtys.items():
            type_name = tracked_items.get(type_id, str(type_id))
            cursor.execute('''
                INSERT INTO lx_zoj_container_snapshot
                    (snapshot_timestamp, container_item_id, type_id, type_name, quantity)
                VALUES (?, ?, ?, ?, ?)
            ''', (snapshot_time, cid, type_id, type_name, qty))
            rows_inserted += 1

    conn.commit()
    print(f"[OK] Container snapshot stored: {rows_inserted} item-container rows")


def sync_consignor_quantities(conn):
    """
    Update consignors.current_qty from the latest lx_zoj_container_snapshot
    using the consignor_containers mapping table.
    """
    cursor = conn.cursor()

    # Get the latest snapshot timestamp
    ts_row = cursor.execute(
        "SELECT MAX(snapshot_timestamp) FROM lx_zoj_container_snapshot"
    ).fetchone()
    if not ts_row or not ts_row[0]:
        print("[INFO] No container snapshots found — skipping consignor qty sync")
        return

    latest_ts = ts_row[0]

    # For each container assignment, sum up the matching type_id in the latest snapshot
    assignments = cursor.execute("""
        SELECT cc.consignor_id, cc.container_item_id, c.item_type_id
        FROM consignor_containers cc
        JOIN consignors c ON c.id = cc.consignor_id
        WHERE c.item_type_id IS NOT NULL
    """).fetchall()

    updated = 0
    for consignor_id, container_item_id, item_type_id in assignments:
        row = cursor.execute("""
            SELECT quantity FROM lx_zoj_container_snapshot
            WHERE snapshot_timestamp = ? AND container_item_id = ? AND type_id = ?
        """, (latest_ts, container_item_id, item_type_id)).fetchone()

        qty = row[0] if row else 0
        cursor.execute(
            "UPDATE consignors SET current_qty = ? WHERE id = ?",
            (qty, consignor_id)
        )
        updated += 1

    conn.commit()
    print(f"[OK] Synced current_qty for {updated} consignor(s) from container snapshot")

def get_tracked_items(conn):
    """Get list of tracked item type_ids from database."""
    cursor = conn.cursor()
    cursor.execute('SELECT type_id, type_name FROM tracked_market_items')
    tracked = {row[0]: row[1] for row in cursor.fetchall()}
    print(f"[OK] Loaded {len(tracked)} tracked items from database")
    return tracked

def match_tracked_inventory(lx_zoj_items, tracked_items):
    """
    Match LX-ZOJ items against tracked items.
    Returns dict: {type_id: quantity}
    """
    inventory = {}

    for asset in lx_zoj_items:
        type_id = asset.get('type_id')
        quantity = asset.get('quantity', 1)

        if type_id in tracked_items:
            # Aggregate quantities for same type
            if type_id in inventory:
                inventory[type_id] += quantity
            else:
                inventory[type_id] = quantity

    print(f"[OK] Matched {len(inventory)} tracked items in LX-ZOJ")
    return inventory

def store_inventory_snapshot(conn, inventory, tracked_items):
    """Store inventory snapshot in lx_zoj_inventory table."""
    cursor = conn.cursor()
    snapshot_time = datetime.now(timezone.utc).isoformat()

    print(f"\n>>> Storing inventory snapshot...")

    items_inserted = 0

    for type_id, quantity in inventory.items():
        type_name = tracked_items[type_id]

        cursor.execute('''
            INSERT INTO lx_zoj_inventory (
                snapshot_timestamp, type_id, type_name,
                quantity, location_id, location_name
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            snapshot_time,
            type_id,
            type_name,
            quantity,
            LX_ZOJ_STRUCTURE_ID,
            'LX-ZOJ'
        ))

        items_inserted += 1

    # Insert 0 quantities for tracked items not in inventory
    for type_id, type_name in tracked_items.items():
        if type_id not in inventory:
            cursor.execute('''
                INSERT INTO lx_zoj_inventory (
                    snapshot_timestamp, type_id, type_name,
                    quantity, location_id, location_name
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                snapshot_time,
                type_id,
                type_name,
                0,
                LX_ZOJ_STRUCTURE_ID,
                'LX-ZOJ'
            ))
            items_inserted += 1

    conn.commit()
    print(f"[OK] Snapshot stored: {items_inserted} items at {snapshot_time}")

    return snapshot_time

def get_current_inventory_from_db(conn):
    """Get the latest inventory snapshot from database."""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT type_id, type_name, quantity
        FROM lx_zoj_current_inventory
    ''')

    inventory = {row[1]: row[2] for row in cursor.fetchall()}  # {type_name: quantity}
    return inventory

def update_html_inventory(inventory):
    """Update index.html with current inventory quantities by calling update_html_data.py."""
    print(f"\n>>> Updating HTML file...")

    import subprocess

    try:
        # Run update_html_data.py to regenerate HTML with fresh data from database
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_DIR, 'update_html_data.py')],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            # Count how many lines mention "SUCCESS" or similar indicators
            if 'SUCCESS' in result.stdout or 'updated successfully' in result.stdout:
                print(f"[OK] HTML regenerated successfully from database")
                print(f"[OK] index_final.html updated with latest inventory")

                # Copy index_final.html to index.html
                import shutil
                shutil.copy2(
                    os.path.join(PROJECT_DIR, 'index_final.html'),
                    os.path.join(PROJECT_DIR, 'index.html')
                )
                print(f"[OK] Copied to index.html")

                return True
            else:
                print(f"[WARNING] HTML update completed but with unexpected output")
                print(f"Output: {result.stdout}")
                return True
        else:
            print(f"[ERROR] HTML update failed with return code {result.returncode}")
            print(f"Error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[ERROR] HTML update timed out")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to update HTML: {e}")
        return False

def commit_and_push_to_github(snapshot_time):
    """Commit and push index.html changes to GitHub."""
    import subprocess

    print(f"\n>>> Pushing to GitHub...")

    try:
        # Check if there are changes to index.html
        result = subprocess.run(
            ['git', 'diff', '--quiet', 'index.html'],
            cwd=PROJECT_DIR,
            capture_output=True
        )

        if result.returncode == 0:
            print("[!] No changes to commit (inventory unchanged)")
            return True

        # Add index.html
        subprocess.run(
            ['git', 'add', 'index.html'],
            cwd=PROJECT_DIR,
            check=True,
            capture_output=True
        )
        print("[OK] Staged index.html")

        # Create commit message
        commit_msg = f"Auto-update inventory - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # Commit
        subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            cwd=PROJECT_DIR,
            check=True,
            capture_output=True
        )
        print(f"[OK] Committed: {commit_msg}")

        # Push to GitHub
        result = subprocess.run(
            ['git', 'push'],
            cwd=PROJECT_DIR,
            check=True,
            capture_output=True,
            text=True
        )
        print("[OK] Pushed to GitHub")
        print("     GitHub Pages will update in 1-2 minutes")

        return True

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Git operation failed: {e}")
        if e.output:
            print(f"        Output: {e.output}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error during git push: {e}")
        return False

# ============================================
# MAIN SCRIPT
# ============================================

def ensure_main_branch():
    """Switch to main branch before making any changes (GitHub Pages builds from main).
    Returns the original branch name so the caller can restore it afterward."""
    import subprocess
    try:
        current_branch = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True
        )
        branch_name = current_branch.stdout.strip()

        if branch_name != 'main':
            print(f"[!] Currently on '{branch_name}' branch, switching to main...")
            subprocess.run(
                ['git', 'checkout', 'main'],
                cwd=PROJECT_DIR,
                check=True,
                capture_output=True
            )
            print("[OK] Switched to main branch")
        else:
            print("[OK] Already on main branch")
        return branch_name
    except Exception as e:
        print(f"[ERROR] Could not switch to main branch: {e}")
        return 'main'


def restore_branch(original_branch):
    """Switch back to the branch that was active before ensure_main_branch()."""
    import subprocess
    if original_branch and original_branch != 'main':
        try:
            subprocess.run(
                ['git', 'checkout', original_branch],
                cwd=PROJECT_DIR,
                check=True,
                capture_output=True
            )
            print(f"[OK] Restored to '{original_branch}' branch")
        except Exception as e:
            print(f"[WARN] Could not restore branch '{original_branch}': {e}")

def _update_container_names_in_db(conn, esi_names):
    """
    Update container_name in consignor_containers for any containers
    that have a known ESI name. Containers without a custom in-game name
    keep whatever name was last stored (or NULL if brand new).
    """
    if not esi_names:
        return
    cursor = conn.cursor()
    for item_id, name in esi_names.items():
        cursor.execute(
            "UPDATE consignor_containers SET container_name = ? WHERE container_item_id = ?",
            (name, item_id)
        )
    conn.commit()
    print(f"[OK] Updated {len(esi_names)} container name(s) in DB")


def update_known_containers(conn, all_assets, esi_names, snapshot_time):
    """
    Upsert all container-type items found in the LX-ZOJ hangar into known_containers.
    Includes empty containers (not just those with items inside).
    Preserves the 'ignored' flag — never resets it.
    """
    all_item_ids = {a['item_id'] for a in all_assets}
    items_with_children = {
        a['location_id'] for a in all_assets
        if a.get('location_id') in all_item_ids
    }

    hangar_containers = [
        a for a in all_assets
        if (a.get('location_id') == LX_ZOJ_STRUCTURE_ID
            and a.get('location_flag') == 'Hangar'
            and (a['item_id'] in items_with_children
                 or a.get('type_id') in CONTAINER_TYPE_IDS))
    ]

    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS known_containers (
            item_id    INTEGER PRIMARY KEY,
            name       TEXT,
            ignored    INTEGER NOT NULL DEFAULT 0,
            last_seen  TEXT
        )
    """)
    for asset in hangar_containers:
        item_id = asset['item_id']
        name = esi_names.get(item_id)
        cursor.execute("""
            INSERT INTO known_containers (item_id, name, ignored, last_seen)
            VALUES (?, ?, 0, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                name      = COALESCE(excluded.name, known_containers.name),
                last_seen = excluded.last_seen
        """, (item_id, name, snapshot_time))

    conn.commit()
    print(f"[OK] Known containers updated: {len(hangar_containers)} container(s)")


def snapshot_test_comp(conn):
    """Fetch TEST Buyback Google Sheet and store a competitor stock snapshot."""
    import csv, io as _io

    SHEET_ID = '1UGdb9mQIrdNprFN9_9g4WDYMh-C8fX5CTlhFBCV6bI4'
    TABS = [
        ('Minerals, Gas',        '604363953'),
        ('Moon Goo, Composites', '498403852'),
        ('Ore, Ice',             '1641474510'),
        ('PI',                   '684077699'),
    ]

    INTERVAL_HOURS = 12
    cursor = conn.cursor()
    last_snap = cursor.execute(
        'SELECT MAX(snapshot_timestamp) FROM test_comp_snapshots'
    ).fetchone()[0]
    if last_snap:
        from datetime import timedelta
        last_dt = datetime.fromisoformat(last_snap)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        if age_hours < INTERVAL_HOURS:
            print(f'\n>>> Skipping TEST Buyback snapshot (last was {age_hours:.1f}h ago, interval={INTERVAL_HOURS}h)')
            return None

    snapshot_time = datetime.now(timezone.utc).isoformat()
    rows_inserted = 0

    print('\n>>> Snapshotting TEST Buyback competitor stock...')
    for tab_label, gid in TABS:
        url = (f'https://docs.google.com/spreadsheets/d/'
               f'{SHEET_ID}/export?format=csv&gid={gid}')
        try:
            resp = requests.get(url, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            reader = csv.DictReader(_io.StringIO(resp.text))
            tab_count = 0
            for row in reader:
                name = row.get('Type', '').strip()
                qty_str = row.get('Quantity', '0').strip().replace(',', '')
                try:
                    qty = int(float(qty_str))
                except ValueError:
                    qty = 0
                if not name:
                    continue
                cursor.execute(
                    'INSERT INTO test_comp_snapshots '
                    '(snapshot_timestamp, tab_label, item_name, quantity) '
                    'VALUES (?, ?, ?, ?)',
                    (snapshot_time, tab_label, name, qty)
                )
                tab_count += 1
                rows_inserted += 1
            print(f'  {tab_label}: {tab_count} items')
        except Exception as e:
            print(f'  [WARN] Could not fetch tab "{tab_label}": {e}')

    conn.commit()
    print(f'[OK] Competitor snapshot stored: {rows_inserted} items at {snapshot_time}')
    return snapshot_time


def main():
    """
    Update LX-ZOJ inventory from ESI.
    Stores snapshot in database and updates HTML.
    """

    print("=" * 60)
    print("UPDATE_LX_ZOJ_INVENTORY")
    print(f"Started: {datetime.now().strftime('%I:%M:%S %p')}")
    print("=" * 60)

    # Switch to main branch FIRST (before modifying any files)
    original_branch = ensure_main_branch()

    print(f"\nCharacter ID: {CHARACTER_ID}")
    print(f"Structure: LX-ZOJ ({LX_ZOJ_STRUCTURE_ID})")

    # Get authentication
    headers = get_authenticated_headers()
    if headers is None:
        print("\n[ERROR] Cannot proceed without authentication")
        return

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    try:
        # Get tracked items list
        tracked_items = get_tracked_items(conn)

        # Fetch all character assets
        all_assets = get_character_assets(headers)

        if not all_assets:
            print("\n[WARNING] No assets found")
            conn.close()
            return

        # Filter to LX-ZOJ hangar only (now annotates _container_item_id on each item)
        lx_zoj_items = filter_lx_zoj_items(all_assets)

        # Collect ALL container item_ids in the hangar (including empty ones)
        all_item_ids_set = {a['item_id'] for a in all_assets}
        items_with_children_set = {
            a['location_id'] for a in all_assets
            if a.get('location_id') in all_item_ids_set
        }
        container_ids = {
            a['item_id'] for a in all_assets
            if (a.get('location_id') == LX_ZOJ_STRUCTURE_ID
                and a.get('location_flag') == 'Hangar'
                and (a['item_id'] in items_with_children_set
                     or a.get('type_id') in CONTAINER_TYPE_IDS))
        }

        # Fetch custom ESI names for all hangar containers
        esi_names = fetch_container_names_from_esi(headers, container_ids)

        # Update container names stored in the DB (if we have any assignments)
        if container_ids:
            _update_container_names_in_db(conn, esi_names)

        # Update known_containers table with all discovered hangar containers
        update_known_containers(conn, all_assets, esi_names,
                                datetime.now(timezone.utc).isoformat())

        # Match against tracked items (aggregate by type_id for the site display)
        inventory = match_tracked_inventory(lx_zoj_items, tracked_items)

        # Store aggregate snapshot in database
        snapshot_time = store_inventory_snapshot(conn, inventory, tracked_items)

        # Store per-container snapshot for consignor quantity tracking
        store_container_snapshot(conn, lx_zoj_items, tracked_items, snapshot_time)

        # Update each consignor's current_qty from their assigned container
        sync_consignor_quantities(conn)

        # Snapshot TEST Buyback competitor stock (no auth needed — public sheet)
        snapshot_test_comp(conn)

        # Update HTML file (regenerates from database, so we don't need to pass inventory)
        html_success = update_html_inventory(None)

        # Commit and push to GitHub
        git_success = False
        if html_success:
            git_success = commit_and_push_to_github(snapshot_time)

        # Show summary
        print("\n" + "=" * 60)
        print("INVENTORY UPDATE SUMMARY")
        print("=" * 60)
        print(f"Snapshot time: {snapshot_time}")
        print(f"Items in stock: {len([q for q in inventory.values() if q > 0])}")
        print(f"Items out of stock: {len([q for q in inventory.values() if q == 0]) + (35 - len(inventory))}")
        print(f"Containers tracked: {len(container_ids)}")
        print(f"HTML updated: {'Yes' if html_success else 'No'}")
        print(f"GitHub pushed: {'Yes' if git_success else 'No'}")
        print("=" * 60)

        conn.close()

        print(f"\n[OK] Inventory update completed!")
        print(f"Finished: {datetime.now().strftime('%I:%M:%S %p')}")
        restore_branch(original_branch)

    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        restore_branch(original_branch)
        raise

if __name__ == '__main__':
    main()
