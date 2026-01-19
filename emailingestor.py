import imaplib2 as im
import email
from email.header import decode_header
from dataclasses import dataclass
import dotenv
import os
from util import Log, log, endl, Lvl
import time
from util import *

dotenv.load_dotenv(dotenv.find_dotenv())

@dataclass
class Email:
    _from: str
    subject: str
    body: str
    
    def __str__(self):
        return f"Subject: {self.subject}\n\n{self.body}"

class EmailIngestor:
    @Log # Removed Email and Password fields; it always retrieves from .env, so Logging is safe
    def __init__(self, imap_server: str = "imap.gmail.com", imap_port: int = 993, init_num: int = 10, mailbox = "INBOX", support_email: str | None = None):
        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSKEY") or os.getenv("PASSWORD")
        
        if (not self.email) or (not self.password):
            raise Exception("Fields missing for email and password. Check if .env is created with\n\tEMAIL=<your email>\n\tPASSKEY=<app password>")
        
        self.imap_server = imap_server
        self.support_email = support_email or self.email
        status, response = None, None
        try:
            self.mail = im.IMAP4_SSL(self.imap_server, imap_port)
            self.mail.login(self.email, self.password)
            try:
                id_payload = (
                    '("name" "MUN-Amendment-Displayer" '
                    '"version" "1.0.0" '
                    '"vendor" "BIPH Model United Nations Team" '
                    f'"support-email" "{self.support_email}")'
                )
                sta, res = self.mail._simple_command("ID", id_payload)
                                                            
                if sta != "OK":
                    log << Lvl.warn << "ID Command warning: Status: " << sta << ", Response: " << res << endl
                else:
                    print(f"ID Command successful")
            except Exception as e:
                log << (Lvl.fatal if ".163.com" in self.imap_server else Lvl.warn) << f"ID Command failed: {e}" << endl
                
            
        except im.IMAP4.error as e:
            log << Lvl.fatal << f"Error: {e}" << endl
            print("Please check if you have enabled IMAP protocol in your email client, or check the imap server address")
            print(f"Status: {status}")
            print(f"Response: {response}")
            raise
        log << Lvl.info << "Login Successful" << endl
        self.mailbox = mailbox
        self.emailList: list[Email] = self.fetch_emails(init_num)
        
    @Log
    def pull(self, max_new: int = 10) -> list[Email]:
        """
        Pull up to `max_new` new emails that haven't been seen yet.
        Returns a list of Email objects (empty if no new emails).
        DO NOT place in rendering loops (see fetch_emails)
        """
        # Fetch up to max_new new messages using UID tracking
        new_emails = self.fetch_emails(max_new)

        if not new_emails:
            log << Lvl.info << "No new emails to pull" << endl
            return []

        # Filter out emails already in emailList (just in case)
        truly_new = [em for em in new_emails if em not in self.emailList]

        if truly_new:
            self.emailList.extend(truly_new)
            log << Lvl.info << f"Pulled {len(truly_new)} new emails" << endl
        else:
            log << Lvl.info << "No truly new emails found" << endl

        return truly_new


    
    def fetch_emails(self, num: int = 10) -> list[Email]:
        """
        Fetch the latest `num` emails, using UID tracking to avoid re-fetching old messages.
        DO NOT place in rendering loops (sleeps for a short time to avoid rate limiting)
        """
        try:
            # 1️⃣ Select mailbox
            status, response = self.mail.select(self.mailbox)
            log << Lvl.info << f"Select status: {status}, response: {response}" << endl
            if status != "OK":
                raise Exception(f"Failed to select mailbox: {self.mailbox}")

            # 2️⃣ Search for messages using UID
            # Track last seen UID (default to 0)
            last_uid = getattr(self, "_last_uid", 0)

            # Search for UIDs greater than last seen UID
            typ, data = self.mail.uid("SEARCH", None, f"UID {last_uid + 1}:*")
            if typ != "OK":
                raise Exception("UID search failed")

            uid_list = data[0].split() # type: ignore
            if not uid_list:
                if not uid_list:
                    log << Lvl.info << "No new emails to fetch" << endl

                return []  # No new messages
            
            # maintaining politeness
            time.sleep(0.1)
            
            # Only take the last `num` messages
            uid_list = uid_list[-num:]

            res: list[Email] = []

            for uid_val in uid_list:
                time.sleep(0.05)
                typ, msg_data = self.mail.uid("FETCH", uid_val, "(RFC822)")
                if typ != "OK":
                    log << Lvl.warn << f"Failed to fetch UID {uid_val}" << endl
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")

                        body = self.get_email_body(msg)
                        _from = msg.get("from") or ""

                        log << Lvl.info << f"Fetched email from: {_from}" << endl
                        res.append(Email(_from, subject, body))

                # Update last UID after successful fetch
                self._last_uid = int(uid_val)

            return res

        except Exception as e:
            log << Lvl.warn << f"Error fetching emails: {e}" << endl
            return []

    
    def get_email_body(self, msg, length=1000) -> str:
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                if "attachment" in content_disposition:
                    continue
                
                if content_type in ["text/plain", "text/html"]:
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        part_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                        body += html_to_text(part_body) + "\n"
                    except Exception as e:
                        body += f"[Error reading part: {e}]\n"
        else:
            content_type = msg.get_content_type()
            try:
                charset = msg.get_content_charset() or 'utf-8'
                body = msg.get_payload(decode=True).decode(charset, errors='ignore')
                return html_to_text(body) if "<html" in body.lower() else body
            except Exception as e:
                body = f"[Error reading body: {e}]"
                raise
        
        return body[:length] + "..." if len(body) > length else body
                    