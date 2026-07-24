import imaplib
import email
from email.header import decode_header
from typing import List, Dict, Any

class EmailFetcher:
    def __init__(self, server: str, port: int, user: str, password: str):
        self.server = server
        self.port = port
        self.user = user
        self.password = password

    def fetch_unseen_notifications(self, sender_filter: str) -> List[Dict[str, str]]:
        messages_data = []
        try:
            mail = imaplib.IMAP4_SSL(self.server, self.port)
            mail.login(self.user, self.password)
            mail.select("inbox")

            # Search for unread emails from specific sender or containing keywords
            search_criterion = f'(UNSEEN FROM "{sender_filter}")' if sender_filter else '(UNSEEN)'
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
