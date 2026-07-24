import json
from pathlib import Path
from typing import List, Dict

SETTINGS_PATH = Path(__file__).parent / "settings.json"


def load_accounts(path: Path = SETTINGS_PATH) -> List[Dict]:
    """
    Each account: {"name": str, "type": "CREDIT"|"DEBIT", "match": [str, ...], "sender": str}.
    "type" is the scraper's own classification (which sign/keyword rules apply),
    unrelated to Actual's internal account-type field.
    "match" is optional: keywords/aliases (bank name, card last-4, etc.) used to
    pick the right account when multiple accounts share the same type.
    "sender" is optional: the notification email address for that account's bank,
    used to build the IMAP fetch filter (see get_sender_filters).
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("accounts", [])


def get_sender_filters(accounts: List[Dict]) -> List[str]:
    """Unique, order-preserved list of sender addresses across all configured accounts."""
    seen = []
    for account in accounts:
        sender = account.get("sender")
        if sender and sender not in seen:
            seen.append(sender)
    return seen
