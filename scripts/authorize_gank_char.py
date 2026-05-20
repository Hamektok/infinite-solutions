"""
authorize_gank_char.py
----------------------
One-time OAuth authorization to create a credentials file for Zanju Hakaari.

Run: python scripts/authorize_gank_char.py

Uses the same EVE developer app as Hamektok Hakaari (same Raxxiz account).
A browser window will open showing EVE's character picker — select Zanju Hakaari
and approve the scopes. The script captures the callback automatically and saves:
    config/credentials_gank_contact_zanju.json
"""
import json
import os
import base64
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

PROJECT_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_CREDS = os.path.join(PROJECT_DIR, 'config', 'credentials_hamektok.json')
OUTPUT_CREDS = os.path.join(PROJECT_DIR, 'config', 'credentials_gank_contact_zanju.json')

TARGET_CHAR_ID   = 2118111467
TARGET_CHAR_NAME = 'Zanju Hakaari'
CALLBACK_PORT    = 5000
REDIRECT_URI     = f'http://localhost:{CALLBACK_PORT}/auth/callback'

SCOPES = (
    'esi-characters.write_contacts.v1 '
    'esi-characters.read_contacts.v1 '
    'esi-wallet.read_character_wallet.v1 '
    'esi-characters.read_standings.v1'
)

# ── Load client credentials from Hamektok's file (same Raxxiz account) ────────
with open(SOURCE_CREDS) as f:
    base_creds = json.load(f)

CLIENT_ID     = base_creds['client_id']
CLIENT_SECRET = base_creds['client_secret']

# ── Build auth URL ─────────────────────────────────────────────────────────────
auth_url = ('https://login.eveonline.com/v2/oauth/authorize?'
            + urllib.parse.urlencode({
                'response_type': 'code',
                'client_id':     CLIENT_ID,
                'redirect_uri':  REDIRECT_URI,
                'scope':         SCOPES,
                'state':         'gank_char_auth',
            }))

# ── Local HTTP server to catch the callback ────────────────────────────────────
_auth_code = [None]

class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        _auth_code[0] = params.get('code')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(
            b'<h2>Authorization complete!</h2>'
            b'<p>You can close this tab and return to the terminal.</p>'
        )

    def log_message(self, *args):
        pass


print(f'Opening browser for EVE SSO authorization...')
print(f'>>> When the character picker appears, select: {TARGET_CHAR_NAME} <<<')
print(f'\nAuth URL (for debugging):\n{auth_url}\n')
print('NOTE: If your browser auto-selects the wrong character, log out of')
print('      EVE SSO in your browser first, or use a private/incognito window.')
webbrowser.open(auth_url)

print(f'Waiting for callback on port {CALLBACK_PORT}...')
server = HTTPServer(('localhost', CALLBACK_PORT), _CallbackHandler)
server.handle_request()

code = _auth_code[0]
if not code:
    print('ERROR: No authorization code received.')
    raise SystemExit(1)

# ── Exchange code for tokens ───────────────────────────────────────────────────
print('Exchanging authorization code for tokens...')
r = requests.post(
    'https://login.eveonline.com/v2/oauth/token',
    data={
        'grant_type':   'authorization_code',
        'code':         code,
        'redirect_uri': REDIRECT_URI,
    },
    auth=(CLIENT_ID, CLIENT_SECRET),
    headers={'Content-Type': 'application/x-www-form-urlencoded'},
    timeout=15,
)
r.raise_for_status()
token_data = r.json()

refresh_token = token_data['refresh_token']
access_token  = token_data['access_token']

# ── Decode JWT to confirm which character was authorized ───────────────────────
parts  = access_token.split('.')
padded = parts[1] + '=' * (-len(parts[1]) % 4)
payload = json.loads(base64.urlsafe_b64decode(padded))
char_id_from_token = int(payload.get('sub', '0:0').split(':')[-1])

if char_id_from_token != TARGET_CHAR_ID:
    print(f'\nWARNING: Expected character ID {TARGET_CHAR_ID} ({TARGET_CHAR_NAME})')
    print(f'         Got character ID {char_id_from_token} instead.')
    print(f'         Did you select the right character in the browser?')
    confirm = input('Save anyway? (y/N): ').strip().lower()
    if confirm != 'y':
        print('Aborted. Run the script again and select Zanju Hakaari.')
        raise SystemExit(1)

# ── Save credentials file ──────────────────────────────────────────────────────
output = {
    'client_id':      CLIENT_ID,
    'client_secret':  CLIENT_SECRET,
    'refresh_token':  refresh_token,
    'character_id':   char_id_from_token,
    'character_name': TARGET_CHAR_NAME,
}
with open(OUTPUT_CREDS, 'w') as f:
    json.dump(output, f, indent=2)

print(f'\nSuccess! Credentials saved to: {OUTPUT_CREDS}')
print(f'Character: {TARGET_CHAR_NAME} (ID: {char_id_from_token})')
print('\nYou can now select "Zanju Hakaari" in the Gank Watch tab.')
