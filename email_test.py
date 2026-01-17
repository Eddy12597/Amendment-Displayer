import smtplib
from email.mime.text import MIMEText
import getpass


def test_smtp(email: str, password: str, passkey: str, smtp_server: str | None = None, port=465, use_ssl=True):
    """Test SMTP connection with correct server for domain"""
    try:
        # Create a simple test email
        msg = MIMEText("This is a test email to verify SMTP connection.")
        msg['Subject'] = 'SMTP Connection Test'
        msg['From'] = email
        msg['To'] = email
        
        # For 163.com, use specific settings
        if smtp_server is None:
            domain = email[email.find("@")+1:]
            if domain == "163.com":
                smtp_server = "smtp.163.com"
                port = 465  # 163.com REQUIRES port 465 with SSL
                use_ssl = True
                print("ℹ️  For 163.com: Using SMTP_SSL on port 465")
            elif domain == "qq.com":
                smtp_server = "smtp.qq.com"
                port = 465
                use_ssl = True
            else:
                smtp_server = "smtp." + domain
        
        print(f"Testing SMTP connection to {smtp_server}:{port}...")
        
        # Connect to server based on SSL requirement
        if use_ssl:
            # Use SMTP_SSL for direct SSL connection
            server = smtplib.SMTP_SSL(smtp_server, port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_server, port, timeout=10)
            server.ehlo()
            if port == 587:
                server.starttls()
                server.ehlo()
        
        # Set debug level to see what's happening
        server.set_debuglevel(1)
        
        # Login
        print(f"\nAttempting login with: {email}")
        
        # Try passkey first (for 163.com, this is usually the authorization code)
        try:
            server.login(email, passkey)
            print("✓ SMTP Login successful with passkey!")
        except smtplib.SMTPAuthenticationError:
            print("Passkey failed. Trying password...")
            try:
                server.login(email, password)
                print("✓ SMTP Login successful with password!")
            except smtplib.SMTPAuthenticationError as e:
                print(f"✗ SMTP Authentication failed: {e}")
                print("\nFor 163.com accounts:")
                print("1. You need an 'authorization code', not your login password")
                print("2. Get it from: mail.163.com → Settings → POP3/SMTP/IMAP")
                print("3. Enable 'IMAP/SMTP service' first")
                server.quit()
                return False
        
        # Try to send test email
        print("\nAttempting to send test email...")
        server.send_message(msg)
        print("✓ Test email sent successfully!")
        
        server.quit()
        return True
        
    except smtplib.SMTPException as e:
        print(f"✗ SMTP Error: {type(e).__name__}: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        return False

# Test IMAP separately
def test_imap(email: str, password: str, passkey: str, imap_server: str | None = None, port=993):
    """Test IMAP connection with Office 365"""
    import imaplib
    import ssl
    
    if imap_server is None:
        imap_server = "imap." + email[email.find("@")+1:]
    
    try:
        print(f"\nTesting IMAP connection to {imap_server}:{port}...")
        print(f"Attempting login with: {email}")
        
        # Create SSL context for secure connection
        context = ssl.create_default_context()
        
        # Connect with SSL
        mail = imaplib.IMAP4_SSL(imap_server, port, ssl_context=context)
        
        # Login
        try:
            mail.login(email, password)
        except:
            print("Failed. Trying passkey...")
            try:
                mail.login(email, passkey)
            except:
                raise
        print("✓ IMAP Login successful!")
        
        # List mailboxes to verify access
        status, folders = mail.list()
        if status == 'OK':
            print(f"✓ Found {len(folders)} mailboxes")
        
        mail.logout()
        return True
        
    except imaplib.IMAP4.error as e:
        print(f"✗ IMAP Authentication failed: {e}")
        print("\nTroubleshooting steps:")
        print("1. Verify password is correct")
        print("2. Check if IMAP is enabled in Office 365:")
        print("   - Outlook Web > Settings > Mail > Sync email > IMAP")
        print("3. If MFA is enabled, you need an app password")
        print("4. Admin may have disabled IMAP access")
        return False
    except Exception as e:
        print(f"✗ IMAP Error: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    # Test with your credentials
    email = input("Enter your email: ")
    password = input("Enter your password: ")
    passkey = input("Enter your passkey: ")
    
    print("=" * 60)
    print("SMTP vs IMAP Connection Test")
    print("=" * 60)
    
    # Test SMTP first
    smtp_ok = test_smtp(email, password, passkey)
    
    # Test IMAP
    imap_ok = test_imap(email, password, passkey)
    
    print("\n" + "=" * 60)
    print("Results Summary:")
    print(f"SMTP: {'✓ WORKS' if smtp_ok else '✗ FAILED'}")
    print(f"IMAP: {'✓ WORKS' if imap_ok else '✗ FAILED'}")
    
    if smtp_ok and not imap_ok:
        print("\n✓ SMTP works but IMAP doesn't - This indicates:")
        print("1. IMAP protocol might be disabled in your account")
        print("2. Admin may have blocked IMAP access")
        print("3. Different authentication requirements for IMAP")
        print("\nAction: Check Office 365 admin settings for IMAP access")
    elif not smtp_ok and not imap_ok:
        print("\n✗ Both SMTP and IMAP failed - This indicates:")
        print("1. Incorrect credentials")
        print("2. MFA/2FA enabled (need app password)")
        print("3. Account access issues")