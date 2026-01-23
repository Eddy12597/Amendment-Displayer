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
        self.emailList: list[Email] = [] # self.fetch_emails(init_num)
    
    def _reconnect(self):
        try:
            try:
                self.mail.logout()
            except Exception:
                pass  # already dead

            self.__init__(imap_server=self.imap_server)
            log << Lvl.info << "IMAP reconnected successfully" << endl
        except Exception as e:
            log << Lvl.FATAL << f"IMAP reconnect failed: {e}" << endl
            raise

    
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
        for attempt in (1, 2):
            try:
                return self._fetch_emails_once(num)
            except Exception as e:
                msg = str(e).lower()
                if attempt == 1 and ("autologout" in msg or "bye" in msg):
                    log << Lvl.warn << "IMAP autologout detected, reconnecting..." << endl
                    self._reconnect()
                    continue
                raise
        raise
            
    def _fetch_emails_once(self, num: int) -> list[Email]:
        status, response = self.mail.select(self.mailbox)
        if status != "OK":
            raise Exception(f"Failed to select mailbox: {self.mailbox}")

        last_uid = getattr(self, "_last_uid", 0)
        typ, data = self.mail.uid("SEARCH", None, f"UID {last_uid + 1}:*")
        if typ != "OK":
            raise Exception("UID search failed")
        
        uid_list = data[0].split()
        if not uid_list:
            log << Lvl.info << "No new emails to fetch" << endl
            return []

        uid_list = uid_list[-num:]
        res: list[Email] = []

        for uid_val in uid_list:
            typ, msg_data = self.mail.uid("FETCH", uid_val, "(RFC822)")
            if typ != "OK":
                continue

            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])
                    subject, enc = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(enc or "utf-8")

                    body = self.get_email_body(msg)
                    _from = msg.get("from") or ""
                    res.append(Email(_from, subject, body))

            self._last_uid = int(uid_val)

        return res



    
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
                    