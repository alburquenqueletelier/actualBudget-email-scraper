import re
from typing import Dict, Any, Optional

class BankEmailParser:
    @staticmethod
    def extract_transaction_data(subject: str, body: str, credit_account: str, debit_account: str) -> Optional[Dict[str, Any]]:
        full_text = f"{subject}\n{body}"

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
        is_credit = any(keyword in full_text.lower() for keyword in ["credito", "crédito", "tarjeta de credito"])
        target_account = credit_account if is_credit else debit_account

        # Determine transaction direction (Expense vs Income)
        is_income = any(keyword in full_text.lower() for keyword in ["recibida", "abono", "deposito", "depósito", "transferencia a tu favor"])

        # Expenses must be negative integers in Actual Budget
        final_amount = amount if is_income else -amount

        return {
            "payee": payee,
            "amount": final_amount,
            "account": target_account
        }
