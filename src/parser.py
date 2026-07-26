import re
from typing import Dict, Any, List, Optional

from settings import account_senders

class BankEmailParser:
    @staticmethod
    def _resolve_account(full_text_lower: str, accounts: List[Dict], account_type: str) -> Optional[str]:
        candidates = [a for a in accounts if a.get("type", "").upper() == account_type]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]["name"]

        # Multiple accounts share this type: disambiguate via each account's "match" keywords.
        for account in candidates:
            if any(keyword.lower() in full_text_lower for keyword in account.get("match", [])):
                return account["name"]

        print(f"[WARN] Multiple {account_type} accounts configured, none matched email content — "
              f"defaulting to '{candidates[0]['name']}'. Add a distinguishing 'match' keyword in settings.json.")
        return candidates[0]["name"]

    @staticmethod
    def _extract_payee(full_text: str, config: Dict[str, Any]) -> str:
        # Patterns tried in order; first capture wins (e.g. transfer destination
        # name before the generic "en/a <merchant>" fallback).
        for pattern in config["payee_patterns"]:
            m = re.search(pattern, full_text, re.IGNORECASE)
            if m and m.group(1).strip():
                return m.group(1).strip()
        return config["default_payee"]

    @staticmethod
    def extract_transaction_data(subject: str, body: str, accounts: List[Dict], config: Dict[str, Any], sender: Optional[str] = None) -> Optional[Dict[str, Any]]:
        full_text = f"{subject}\n{body}"
        full_text_lower = full_text.lower()

        # Amount (Chilean peso, e.g. "$ 15.990", dot = thousands separator)
        amount_match = re.search(config["amount_regex"], full_text)
        if not amount_match:
            return None

        amount_str = amount_match.group(1).replace(config["thousands_separator"], "")
        try:
            amount = int(amount_str)
        except ValueError:
            return None

        payee = BankEmailParser._extract_payee(full_text, config)

        # Resolve account by SENDER first — it's the reliable signal. Body keywords
        # are unsafe: a transfer email names the *destination* bank (e.g. "Santander")
        # which would misroute. Sender narrows to that bank's account(s).
        scoped = [a for a in accounts if sender and sender.lower() in account_senders(a)]
        if len(scoped) == 1:
            target_account = scoped[0]["name"]
        else:
            # One sender maps to several accounts (e.g. Santander TC+CC share a
            # sender) — split by credit/debit type, then by "match" keywords.
            pool = scoped or accounts
            is_credit = any(k in full_text_lower for k in config["credit_keywords"])
            target_account = BankEmailParser._resolve_account(
                full_text_lower, pool, "CREDIT" if is_credit else "DEBIT"
            )
        if target_account is None:
            return None

        # Income vs expense; expenses are negative in Actual Budget
        is_income = any(k in full_text_lower for k in config["income_keywords"])
        final_amount = amount if is_income else -amount

        return {
            "payee": payee,
            "amount": final_amount,
            "account": target_account,
        }
