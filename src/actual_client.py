import datetime
from actual import Actual
from actual.queries import reconcile_transaction

class ActualService:
    def __init__(self, base_url: str, password: str, file_password: str = None):
        self.base_url = base_url
        self.password = password
        self.file_password = file_password

    def sync_transaction(
        self,
        account_name: str,
        payee: str,
        amount: int,
        date: datetime.date,
        imported_id: str,
    ) -> bool:
        """Add a transaction, deduped via imported_id.

        Returns True if a new transaction was created, False if it matched an
        existing one (duplicate) or on error. reconcile_transaction matches
        strongly on imported_id, else fuzzily on (date, amount).
        """
        try:
            actual = Actual(
                base_url=self.base_url,
                password=self.password,
                file_password=self.file_password if self.file_password else None,
            )
            with actual:
                tx = reconcile_transaction(
                    actual.session,
                    date=date,
                    account=account_name,
                    payee=payee,
                    amount=amount,
                    imported_id=imported_id,
                    notes="Automated import via email scraper",
                )
                # New rows are s.add()'ed into session.new; a matched existing tx is not.
                is_new = tx in actual.session.new
                actual.commit()
                if is_new:
                    print(f"[SUCCESS] Transaction added: {payee} | {amount} | {account_name} | {date}")
                else:
                    print(f"[SKIP] Duplicate, already present: {payee} | {amount} | {account_name} | {date}")
                return is_new
        except Exception as e:
            print(f"[ERROR] Actual Budget Sync failed: {e}")
            return False
