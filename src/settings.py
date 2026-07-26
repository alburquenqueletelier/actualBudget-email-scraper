import json
from pathlib import Path
from typing import List, Dict

SETTINGS_PATH = Path(__file__).parent / "settings.json"

# Fallbacks used only if settings.json omits a "parser" key or a field within it.
DEFAULT_PARSER = {
    "amount_regex": r"\$\s*([\d.]+)",
    "thousands_separator": ".",
    "credit_keywords": ["credito", "crédito", "tarjeta de credito", "tarjeta de crédito"],
    "income_keywords": ["recibida", "abono", "deposito", "depósito", "transferencia a tu favor", "transferencia recibida"],
    "payee_patterns": [r"(?:en|a)\s+([A-Za-z0-9\s]+?)(?:\s+el|\s+con|\s+\.|\n|$)"],
    "default_payee": "Bank Transaction",
}


def _load(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_parser_config(path: Path = SETTINGS_PATH) -> Dict:
    """Parser business logic (regexes + classification keywords) from settings.json.

    Kept in config, not hardcoded, so email formats can be tuned without code
    changes. Any missing field falls back to DEFAULT_PARSER.
    """
    parser = _load(path).get("parser", {})
    return {**DEFAULT_PARSER, **parser}


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
    return _load(path).get("accounts", [])


def account_senders(account: Dict) -> List[str]:
    """Sender addresses for an account. `sender` may be a string or a list."""
    sender = account.get("sender")
    if not sender:
        return []
    values = [sender] if isinstance(sender, str) else list(sender)
    return [v.lower() for v in values]


def get_sender_filters(accounts: List[Dict]) -> List[str]:
    """Unique, order-preserved list of sender addresses across all configured accounts."""
    seen = []
    for account in accounts:
        for sender in account_senders(account):
            if sender not in seen:
                seen.append(sender)
    return seen
