import requests

TOKEN_URI = "https://oauth2.googleapis.com/token"


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Exchange a long-lived OAuth2 refresh token for a short-lived access token."""
    response = requests.post(
        TOKEN_URI,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["access_token"]
