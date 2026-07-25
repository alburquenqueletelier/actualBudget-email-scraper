import imaplib
import email
import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
from typing import Callable, List, Dict, Any, Optional

class EmailFetcher:
    def __init__(self, server: str, port: int, user: str, access_token_provider: Callable[[], str]):
        self.server = server
        self.port = port
        self.user = user
        # Called on every poll so the access token is always fresh (they expire ~1h).
        self.access_token_provider = access_token_provider

    @staticmethod
    def _build_sender_criterion(senders: List[str]) -> str:
        # IMAP OR takes exactly two operands, so multiple senders nest: (OR FROM a (OR FROM b FROM c))
        quoted = [s.replace('\\', '\\\\').replace('"', '\\"') for s in senders]
        if len(quoted) == 1:
            return f'FROM "{quoted[0]}"'
        return f'(OR FROM "{quoted[0]}" {EmailFetcher._build_sender_criterion(quoted[1:])})'

    @staticmethod
    def _imap_date(d: datetime.date) -> str:
        # IMAP SEARCH date format, e.g. 25-Jul-2026 (day granularity only — no time-of-day).
        return d.strftime("%d-%b-%Y")

    def fetch_unseen_notifications(
        self,
        sender_filters: List[str],
        since: Optional[datetime.date] = None,
        before: Optional[datetime.date] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch bank notification emails.

        Default (no date args): only UNSEEN mail — the safe, no-duplicate path.
        If `since`/`before` given: search by date instead, INCLUDING already-read
        mail (IMAP dates are day-granular). Re-processing read mail is safe because
        the Actual side dedupes via imported_id.
        """
        messages_data = []
        try:
            mail = imaplib.IMAP4_SSL(self.server, self.port)
            access_token = self.access_token_provider()
            auth_string = f"user={self.user}\x01auth=Bearer {access_token}\x01\x01"
            mail.authenticate("XOAUTH2", lambda _challenge: auth_string.encode())
            mail.select("inbox")

            parts = []
            if since is None and before is None:
                parts.append("UNSEEN")
            if since is not None:
                parts.append(f'SINCE {self._imap_date(since)}')
            if before is not None:
                # IMAP BEFORE is exclusive; add a day so `before` reads as inclusive.
                parts.append(f'BEFORE {self._imap_date(before + datetime.timedelta(days=1))}')
            if sender_filters:
                parts.append(self._build_sender_criterion(sender_filters))
            search_criterion = f'({" ".join(parts)})' if parts else '(ALL)'
            status, messages = mail.search(None, search_criterion)

            if status != "OK" or not messages[0]:
                mail.logout()
                return messages_data

            for num in messages[0].split():
                _, data = mail.fetch(num, '(RFC822)')
                msg = email.message_from_bytes(data[0][1])

                # Decode subject
                subject = ""
                raw_subject = msg["Subject"]
                if raw_subject:
                    decoded = decode_header(raw_subject)[0]
                    subject = decoded[0].decode(decoded[1] or 'utf-8') if isinstance(decoded[0], bytes) else decoded[0]

                # Extract plain text body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors='ignore')
                else:
                    body = msg.get_payload(decode=True).decode(errors='ignore')

                # Email Date header -> date (fallback: today) for correct tx dating + dedup.
                email_date = datetime.date.today()
                if msg["Date"]:
                    try:
                        email_date = parsedate_to_datetime(msg["Date"]).date()
                    except (TypeError, ValueError):
                        pass

                sender = parseaddr(msg.get("From", ""))[1].lower()

                messages_data.append({
                    "subject": subject,
                    "body": body,
                    "date": email_date,
                    "sender": sender,
                })

                # Mark as seen
                mail.store(num, '+FLAGS', '\\Seen')

            mail.logout()
        except Exception as e:
            print(f"[ERROR] Email IMAP Fetching failed: {e}")

        return messages_data
