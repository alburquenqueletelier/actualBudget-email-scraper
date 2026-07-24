"""
One-time helper to obtain a Gmail OAuth2 refresh token for IMAP access.

Run this ONCE, locally, on a machine with a browser (not the headless server).
It opens a Google consent screen, then prints the refresh token to paste into
the server's .env as GMAIL_REFRESH_TOKEN.

Prerequisites (Google Cloud Console):
  1. Create/select a project.
  2. Enable the Gmail API.
  3. OAuth consent screen: add your Gmail address as a test user (or publish).
  4. Credentials -> Create Credentials -> OAuth client ID -> Application type
     "Desktop app". Download the client secret JSON.

Usage:
  python scripts/gmail_oauth_setup.py /path/to/client_secret.json
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://mail.google.com/"]


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/gmail_oauth_setup.py /path/to/client_secret.json")
        sys.exit(1)

    client_secret_path = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    # access_type=offline + prompt=consent forces Google to hand back a refresh token
    # even if this account already authorized the app before.
    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    print("\n--- Copy these into actual-email-scraper/.env on the server ---")
    print(f"GMAIL_CLIENT_ID={credentials.client_id}")
    print(f"GMAIL_CLIENT_SECRET={credentials.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={credentials.refresh_token}")


if __name__ == "__main__":
    main()
