import os
import time
from dotenv import load_dotenv
from email_client import EmailFetcher
from oauth import refresh_access_token
from parser import BankEmailParser
from actual_client import ActualService

load_dotenv()

ACTUAL_SERVER_URL = os.getenv("ACTUAL_SERVER_URL")
ACTUAL_PASSWORD = os.getenv("ACTUAL_PASSWORD")
ACTUAL_FILE_PASSWORD = os.getenv("ACTUAL_FILE_PASSWORD")

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
EMAIL_USER = os.getenv("EMAIL_USER")

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", 300))
SENDER_FILTER = os.getenv("SEARCH_SENDER_FILTER", "")
ACCOUNT_CREDIT = os.getenv("ACCOUNT_MAP_CREDIT", "Credit Card")
ACCOUNT_DEBIT = os.getenv("ACCOUNT_MAP_DEBIT", "Checking")

def get_access_token() -> str:
    return refresh_access_token(GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN)

def run():
    print("[INIT] Starting Bank Email Scraper Service...")
    email_fetcher = EmailFetcher(IMAP_SERVER, IMAP_PORT, EMAIL_USER, get_access_token)
    actual_service = ActualService(ACTUAL_SERVER_URL, ACTUAL_PASSWORD, ACTUAL_FILE_PASSWORD)

    while True:
        print("[CHECK] Polling inbox for unread bank emails...")
        emails = email_fetcher.fetch_unseen_notifications(SENDER_FILTER)

        for item in emails:
            tx = BankEmailParser.extract_transaction_data(
                item["subject"],
                item["body"],
                ACCOUNT_CREDIT,
                ACCOUNT_DEBIT
            )
            if tx:
                actual_service.sync_transaction(tx["account"], tx["payee"], tx["amount"])
            else:
                print("[WARN] Email content matched search filter but failed Regex parsing.")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run()
