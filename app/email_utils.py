import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.resend.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "resend")
SMTP_PASS = os.getenv("SMTP_PASS", "")
DEFAULT_FROM = os.getenv("DEFAULT_FROM_EMAIL", "support@cosmicexplorer.uk")

def send_external_email(to_email: str, subject: str, body: str, html_body: str = None):
    if not SMTP_PASS:
        print("SMTP_PASS not set, skipping email send.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = DEFAULT_FROM
    msg["To"] = to_email

    part1 = MIMEText(body, "plain")
    msg.attach(part1)

    if html_body:
        part2 = MIMEText(html_body, "html")
        msg.attach(part2)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(DEFAULT_FROM, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
