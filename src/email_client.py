import imaplib
import email
from email.header import decode_header
from typing import Callable, List, Dict, Any

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

    def fetch_unseen_notifications(self, sender_filters: List[str]) -> List[Dict[str, str]]:
        messages_data = []
        try:
            mail = imaplib.IMAP4_SSL(self.server, self.port)
            access_token = self.access_token_provider()
            auth_string = f"user={self.user}\x01auth=Bearer {access_token}\x01\x01"
            mail.authenticate("XOAUTH2", lambda _challenge: auth_string.encode())
            mail.select("inbox")

            # Search for unread emails from any of the configured bank notification senders
            search_criterion = f'(UNSEEN {self._build_sender_criterion(sender_filters)})' if sender_filters else '(UNSEEN)'
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

                messages_data.append({"subject": subject, "body": body})

                # Mark as seen
                mail.store(num, '+FLAGS', '\\Seen')

            mail.logout()
        except Exception as e:
            print(f"[ERROR] Email IMAP Fetching failed: {e}")

        return messages_data
