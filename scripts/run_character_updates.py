import subprocess
import os
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Character data scripts
SCRIPTS = [
    'update_character_orders.py',
    'update_wallet_transactions.py',
    'update_character_orders_history.py',
    'update_corporation_killmails.py',
]

def main():
    print("=" * 60)
    print(f"Starting character data update - {datetime.now()}")
    print("=" * 60)
    
    for script in SCRIPTS:
        script_path = os.path.join(SCRIPT_DIR, script)
        print(f"\nRunning: {script}")
        
        try:
            result = subprocess.run(['python', script_path], capture_output=True, text=True)
            print(result.stdout)
            if result.returncode != 0:
                print(f"ERROR: {result.stderr}")
        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(10)  # pause between scripts to avoid sustained network bursts

    print(f"\nCharacter updates complete - {datetime.now()}")

if __name__ == '__main__':
    main()