import os
from dotenv import load_dotenv
import background

load_dotenv()

SMTP_MAILHOST_HOST = os.getenv("SMTP_MAILHOST_HOST")
SMTP_MAILHOST_PORT = int(os.getenv("SMTP_MAILHOST_PORT"))

SMTP_MAILHOST = (
    SMTP_MAILHOST_HOST,
    SMTP_MAILHOST_PORT,
)  # noqa: E501
SMTP_FROMADDR = os.getenv("SMTP_FROMADDR")
SMTP_TOADDRS = os.getenv("SMTP_TOADDRS")
SMTP_SUBJECT = os.getenv("SMTP_SUBJECT")
SMTP_CREDENTIALS_EMAIL = os.getenv("SMTP_CREDENTIALS_EMAIL")
SMTP_CREDENTIALS_PASSWORD = os.getenv("SMTP_CREDENTIALS_PASSWORD")  # noqa: E501
SMTP_CREDENTIALS = (
    SMTP_CREDENTIALS_EMAIL,
    SMTP_CREDENTIALS_PASSWORD,
)
SMTP_SECURE = os.getenv("SMTP_SECURE")
if SMTP_SECURE == "()":
    SMTP_SECURE = ()
else:
    SMTP_SECURE = None

SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT"))


@background.task
def send_email(subject, from_email, to_email, body):
    try:
        # Import smtplib for the actual sending function
        import smtplib

        # Import the email modules we'll need
        from email.message import EmailMessage

        # Create a text/plain message with body
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        # Send the message via our own SMTP server.
        s = smtplib.SMTP(host=SMTP_MAILHOST_HOST, port=SMTP_MAILHOST_PORT)
        s.connect(SMTP_MAILHOST_HOST, SMTP_MAILHOST_PORT)
        s.starttls()
        s.login(
            user=SMTP_CREDENTIALS_EMAIL, password=SMTP_CREDENTIALS_PASSWORD
        )  # noqa: E501
        s.send_message(msg)
        s.quit()
    except Exception as e:
        print(f"Could not send email: {e}")
