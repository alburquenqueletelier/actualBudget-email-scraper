from datetime import datetime
from actual import Actual

class ActualService:
    def __init__(self, base_url: str, password: str, file_password: str = None):
        self.base_url = base_url
        self.password = password
        self.file_password = file_password

    def sync_transaction(self, account_name: str, payee: str, amount: int):
        try:
            actual = Actual(
                base_url=self.base_url,
                password=self.password,
                file_password=self.file_password if self.file_password else None
            )
            with actual:
                account = actual.get_account(account_name)
                today_str = datetime.now().strftime("%Y-%m-%d")

                account.add_transaction(
                    date=today_str,
                    payee=payee,
                    amount=amount,
                    notes="Automated import via email scraper"
                )
                print(f"[SUCCESS] Transaction added: {payee} | Amount: {amount} | Account: {account_name}")
        except Exception as e:
            print(f"[ERROR] Actual Budget Sync failed: {e}")
