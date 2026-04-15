"""
One-time EVE SSO authorization helper for the gank contact character.
Starts a local server on port 8642, opens the browser, catches the
callback code, exchanges it for tokens, and saves to credentials_gank_contact.json.
"""

import http.server
import threading
import webbrowser
import urllib.parse
import urllib.request
import json
import os
import base64

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CRED_PATH   = os.path.join(PROJECT_DIR, 'config', 'credentials_gank_contact.json')

with open(CRED_PATH) as f:
    creds = json.load(f)

CLIENT_ID     = creds['client_id']
CLIENT_SECRET = creds['client_secret']
REDIRECT_URI  = 'http://localhost:5000/auth/callback'
SCOPES        = (
    'esi-characters.write_contacts.v1 '
    'esi-wallet.read_character_wallet.v1 '
    'esi-characters.read_standings.v1'
)

auth_code = None

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith('/auth/callback'):
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="background:#09090d;color:#d8e0f0;font-family:sans-serif;
                  display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
                  <div style="text-align:center;">
                    <h2 style="color:#ff8833;">Authorization successful!</h2>
                    <p>You can close this tab and return to the admin dashboard.</p>
                  </div>
                </body></html>
            """)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'No code received.')

    def log_message(self, format, *args):
        pass  # suppress request logs

def exchange_code(code):
    """Exchange auth code for access + refresh tokens."""
    token_url = 'https://login.eveonline.com/v2/oauth/token'
    auth_str  = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
    headers   = {
        'Authorization': f'Basic {auth_str}',
        'Content-Type':  'application/x-www-form-urlencoded',
    }
    body = urllib.parse.urlencode({
        'grant_type':   'authorization_code',
        'code':         code,
        'redirect_uri': REDIRECT_URI,
    }).encode()

    req  = urllib.request.Request(token_url, data=body, headers=headers)
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())

def get_character_name(access_token):
    """Verify token and get character info."""
    req = urllib.request.Request(
        'https://esi.evetech.net/verify/',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception:
        return {}


if __name__ == '__main__':
    # Start local callback server
    server = http.server.HTTPServer(('localhost', 5000), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    # Build auth URL and open browser
    auth_url = (
        'https://login.eveonline.com/v2/oauth/authorize?'
        + urllib.parse.urlencode({
            'response_type': 'code',
            'client_id':     CLIENT_ID,
            'redirect_uri':  REDIRECT_URI,
            'scope':         SCOPES,
            'state':         'gank_contact_auth',
        })
    )

    print('Opening browser for EVE SSO login...')
    print('Log in as the character you want to use for contact management.')
    print()
    webbrowser.open(auth_url)

    # Wait for callback
    thread.join(timeout=120)

    if not auth_code:
        print('ERROR: No auth code received within 2 minutes. Did you complete the login?')
        raise SystemExit(1)

    print('Auth code received. Exchanging for tokens...')

    token_data = exchange_code(auth_code)
    refresh_token  = token_data.get('refresh_token')
    access_token   = token_data.get('access_token')

    if not refresh_token:
        print(f'ERROR: No refresh token in response: {token_data}')
        raise SystemExit(1)

    # Get character info
    char_info = get_character_name(access_token)
    char_name = char_info.get('CharacterName', '')
    char_id   = char_info.get('CharacterID', creds.get('character_id'))

    # Save to credentials file
    creds['refresh_token']   = refresh_token
    creds['character_id']    = char_id
    creds['character_name']  = char_name

    with open(CRED_PATH, 'w') as f:
        json.dump(creds, f, indent=2)

    print(f'Success! Authorized as: {char_name} (ID: {char_id})')
    print(f'Refresh token saved to: {CRED_PATH}')
    server.server_close()
