"""
Run once to obtain a Google OAuth refresh_token for Calendar API.
Usage: python scripts/google_oauth_setup.py
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

CLIENT_CONFIG = {
    "installed": {
        "client_id": input("Pega tu GOOGLE_CLIENT_ID: ").strip(),
        "client_secret": input("Pega tu GOOGLE_CLIENT_SECRET: ").strip(),
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
creds = flow.run_local_server(port=0)

print("\n✅ Autenticación completada.\n")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
print("\nCopia ese valor a tu .env en Railway.")