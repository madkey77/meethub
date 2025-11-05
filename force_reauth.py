"""Force fresh OAuth authentication bypassing all caches."""
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# Relax OAuth scope validation - Google may return additional scopes
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Define scopes
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/meetings.space.readonly",
    "https://www.googleapis.com/auth/drive",
]

print("=" * 80)
print("FORCED RE-AUTHENTICATION")
print("=" * 80)
print("\nThis script will force a completely fresh OAuth authentication.")
print(f"\nRequested scopes:")
for scope in SCOPES:
    print(f"  - {scope}")

# Delete any existing token
token_path = Path("./token.json")
if token_path.exists():
    token_path.unlink()
    print(f"\n✓ Deleted existing token file: {token_path}")

# Create flow
flow = InstalledAppFlow.from_client_secrets_file(
    "credentials.json",
    scopes=SCOPES,
)

# Check environment
is_wsl = "WSL" in os.uname().release or "microsoft" in os.uname().release.lower()

if is_wsl:
    print("\n" + "=" * 80)
    print("WSL DETECTED - Manual Authentication Required")
    print("=" * 80)

    flow.redirect_uri = "http://localhost:8080/"
    auth_url, _ = flow.authorization_url(
        prompt='consent',
        access_type='offline',
        include_granted_scopes='true'
    )

    print("\n1. Copy this URL and open it in your Windows browser:")
    print(f"\n{auth_url}\n")
    print("2. Sign in and authorize the application")
    print("3. You'll see an error page (can't reach localhost)")
    print("4. Copy the ENTIRE URL from your browser address bar")
    print("5. Paste it below\n")
    print("=" * 80)

    redirect_response = input("\nPaste the complete redirect URL here: ").strip()

    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(redirect_response)
    params = parse_qs(parsed.query)

    if 'code' not in params:
        print("\n✗ ERROR: No authorization code found in URL")
        exit(1)

    code = params['code'][0]
    flow.fetch_token(code=code)
    creds = flow.credentials
else:
    # Normal flow for non-WSL
    print("\nOpening browser for authentication...")
    creds = flow.run_local_server(port=0)

# Save token
with open(token_path, "w") as token_file:
    token_file.write(creds.to_json())

print(f"\n✓ Authentication successful!")
print(f"✓ Token saved to: {token_path}")
print(f"\nGranted scopes:")
for scope in creds.scopes:
    print(f"  - {scope}")
print("\n" + "=" * 80)
print("You can now run: python -m src.cli test-auth")
print("=" * 80)
