import imaplib as im
import email
from email.header import decode_header
from dataclasses import dataclass
import dotenv
import os

dotenv.load_dotenv(dotenv.find_dotenv())

@dataclass
class Email:
    _from: str
    subject: str
    body: str

class EmailIngestor:
    def __init__(self, email: str | None = None, password: str | None = None, imap_server: str = "imap.gmail.com", imap_port: int = 993, init_num: int = 20, mailbox = "INBOX"):
        self.email = email or os.getenv("EMAIL")
        self.password = password or os.getenv("PASSKEY") or os.getenv("PASSWORD")
        
        if (not self.email) or (not self.password):
            raise Exception("Fields missing for email and password. Check if .env is created with\n\tEMAIL=<your email>\n\tPASSKEY=<app password>")
        
        self.imap_server = imap_server
        try:
            self.mail = im.IMAP4_SSL(self.imap_server, imap_port)
            self.mail.login(self.email, self.password)
        except im.IMAP4.error as e:
            print(f"Error: {e}")
            print("Please check if you have enabled IMAP protocol in your email client, or check the imap server address")
            raise
        print("Login Successful!")
        self.mailbox = mailbox
        self.emailList: list[Email] = self.fetch_emails(init_num)
        
    
    def pull(self) -> Email | None:
        em = self.fetch_emails(1)[0]
        if em == self.emailList[-1]:
            return
        self.emailList.append(em)
        return em
        
    def fetch_emails(self, num: int = 20) -> list[Email]:
        try:
            status, response = self.mail.select(self.mailbox)
            print(f"Select status: {status}, response: {response}")
            if status != "OK":
                raise Exception(f"Failed to select mailbox: {self.mailbox}")
            
            _, messages = self.mail.search(None, "ALL")
            email_ids = messages[0].split()
            
            res: list[Email] = []
            
            for email_id in email_ids[-num:]:
                status, msg_data = self.mail.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject, encoding = decode_header(msg["Subject"])[0]
                        
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        
                        body = self.get_email_body(msg)
                        _from = msg.get("from")
                        if _from is None: 
                            _from = ""
                        res.append(Email(_from, subject, body))
            return res
            
        except Exception as e:
            print(f"Error fetching emails: {e}")
            return []
    
    def get_email_body(self, msg, length=5000) -> str:
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if "attachment" in content_disposition:
                    continue
                
                if content_type in ["text/plain", "text/html"]:
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        part_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                        body += part_body + "\n"
                    except Exception as e:
                        body += f"[Error reading part: {e}]\n"
        else:
            content_type = msg.get_content_type()
            try:
                charset = msg.get_content_charset() or 'utf-8'
                body = msg.get_payload(decode=True).decode(charset, errors='ignore')
            except Exception as e:
                body = f"[Error reading body: {e}]"
                raise
        
        return body[:length] + "..." if len(body) > length else body
                    
                
ingestor = EmailIngestor(imap_server="imap.163.com")
