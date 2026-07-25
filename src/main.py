import os
import time
import threading
import hmac
import hashlib
import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Header, Query, HTTPException
from fastapi.responses import HTMLResponse
import schedule
import uvicorn

from email_client import EmailFetcher
from oauth import refresh_access_token
from parser import BankEmailParser
from actual_client import ActualService
from settings import load_accounts, get_sender_filters

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

# Token required to trigger /run. Mandatory — service refuses to start without it.
SCRAPER_TOKEN = os.getenv("SCRAPER_TOKEN")
# Daily nightly run time, 24h "HH:MM" local to the container.
SCRAPER_SCHEDULE_TIME = os.getenv("SCRAPER_SCHEDULE_TIME", "03:00")
HTTP_PORT = int(os.getenv("HTTP_PORT", 8000))

ACCOUNTS = load_accounts()
SENDER_FILTERS = get_sender_filters(ACCOUNTS)

# One shared run must not overlap another (nightly + manual click).
_run_lock = threading.Lock()


def get_access_token() -> str:
    return refresh_access_token(GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN)


email_fetcher = EmailFetcher(IMAP_SERVER, IMAP_PORT, EMAIL_USER, get_access_token)
actual_service = ActualService(ACTUAL_SERVER_URL, ACTUAL_PASSWORD, ACTUAL_FILE_PASSWORD)


def _imported_id(account: str, date: datetime.date, amount: int, payee: str, sender: str) -> str:
    """Deterministic dedup key so the same notification never imports twice."""
    raw = f"{account}|{date.isoformat()}|{amount}|{payee}|{sender}"
    return "email-scraper:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()


def run_once(since: datetime.date = None, before: datetime.date = None) -> dict:
    """Single scrape pass. Returns counts. Serialized via _run_lock.

    No date args: UNSEEN mail only. With since/before: date-filtered (incl. read
    mail); duplicates are absorbed by the imported_id dedup on the Actual side.
    """
    with _run_lock:
        print(f"[CHECK] Scraping inbox (since={since}, before={before})...")
        emails = email_fetcher.fetch_unseen_notifications(SENDER_FILTERS, since=since, before=before)
        imported = 0
        duplicates = 0
        skipped = 0
        for item in emails:
            tx = BankEmailParser.extract_transaction_data(
                item["subject"],
                item["body"],
                ACCOUNTS,
            )
            if not tx:
                skipped += 1
                print("[WARN] Email content matched search filter but failed Regex parsing.")
                continue
            date = item["date"]
            imported_id = _imported_id(tx["account"], date, tx["amount"], tx["payee"], item["sender"])
            is_new = actual_service.sync_transaction(
                tx["account"], tx["payee"], tx["amount"], date, imported_id
            )
            if is_new:
                imported += 1
            else:
                duplicates += 1
        result = {"fetched": len(emails), "imported": imported, "duplicates": duplicates, "skipped": skipped}
        print(f"[DONE] {result}")
        return result


def _check_token(token: str):
    if not token or not hmac.compare_digest(token, SCRAPER_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing token")


app = FastAPI(title="Actual Email Scraper")


def _parse_date(value: str, field: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} must be YYYY-MM-DD")


@app.post("/run")
def trigger(
    x_auth_token: str = Header(default=""),
    since: str = Query(default="", description="YYYY-MM-DD; include mail on/after this day (incl. read)"),
    before: str = Query(default="", description="YYYY-MM-DD; include mail on/before this day"),
):
    _check_token(x_auth_token)
    since_date = _parse_date(since, "since") if since else None
    before_date = _parse_date(before, "before") if before else None
    return run_once(since=since_date, before=before_date)


@app.get("/", response_class=HTMLResponse)
def button_page():
    # Public page — holds no secret. Token is typed once, kept in the browser's
    # localStorage, and sent only as the X-Auth-Token header on the POST /run.
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>Email Scraper</title></head>
<body style="font-family:sans-serif;max-width:32rem;margin:4rem auto;text-align:center">
  <h2>Actual Email Scraper</h2>
  <p><input id="token" type="password" placeholder="Access token" style="padding:.5rem;width:20rem"></p>
  <button id="run" style="font-size:1.2rem;padding:.8rem 1.5rem;cursor:pointer">Update now</button>
  <pre id="out" style="text-align:left;background:#f4f4f4;padding:1rem;margin-top:1rem"></pre>
  <script>
    const field = document.getElementById('token');
    field.value = localStorage.getItem('scraper_token') || '';
    document.getElementById('run').onclick = async () => {
      const token = field.value.trim();
      localStorage.setItem('scraper_token', token);
      const out = document.getElementById('out');
      out.textContent = 'Running...';
      try {
        const r = await fetch('/run', {method:'POST', headers:{'X-Auth-Token': token}});
        out.textContent = r.status + ' ' + JSON.stringify(await r.json(), null, 2);
      } catch (e) { out.textContent = 'Error: ' + e; }
    };
  </script>
</body></html>"""


@app.get("/health")
def health():
    return {"status": "ok"}


def _scheduler_loop():
    schedule.every().day.at(SCRAPER_SCHEDULE_TIME).do(run_once)
    print(f"[INIT] Nightly scrape scheduled daily at {SCRAPER_SCHEDULE_TIME}")
    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    if not SCRAPER_TOKEN:
        raise SystemExit("[FATAL] SCRAPER_TOKEN must be set")
    print("[INIT] Starting Bank Email Scraper Service...")
    threading.Thread(target=_scheduler_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT)


if __name__ == "__main__":
    main()
