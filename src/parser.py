import re
from typing import Dict, Any, List, Optional

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
    def extract_transaction_data(subject: str, body: str, accounts: List[Dict]) -> Optional[Dict[str, Any]]:
        full_text = f"{subject}\n{body}"
        full_text_lower = full_text.lower()

        # Extract amount (Matches Chilean Peso formats like $15.990 or $15990)
        amount_match = re.search(r'\$\s?([\d\.]+)', full_text)
        if not amount_match:
            return None

        # Clean amount string to integer
        amount_str = amount_match.group(1).replace('.', '')
        try:
            amount = int(amount_str)
        except ValueError:
            return None

        # Extract merchant / payee name
        payee_match = re.search(r'(?:en|a)\s+([A-Za-z0-9\s]+?)(?:\s+el|\s+con|\s+\.|\n|$)', full_text, re.IGNORECASE)
        payee = payee_match.group(1).strip() if payee_match else "Bank Transaction"

        # Determine target account (Credit Card vs Debit/Checking)
        is_credit = any(keyword in full_text_lower for keyword in ["credito", "crédito", "tarjeta de credito"])
        target_account = BankEmailParser._resolve_account(full_text_lower, accounts, "CREDIT" if is_credit else "DEBIT")
        if target_account is None:
            return None

        # Determine transaction direction (Expense vs Income)
        is_income = any(keyword in full_text_lower for keyword in ["recibida", "abono", "deposito", "depósito", "transferencia a tu favor"])

        # Expenses must be negative integers in Actual Budget
        final_amount = amount if is_income else -amount

        return {
            "payee": payee,
            "amount": final_amount,
            "account": target_account
        }
