import smtplib
import os
import mimetypes
from dotenv import load_dotenv
from email.message import EmailMessage

load_dotenv()

email_address: str = os.environ.get("EMAIL_ADDR", "")
email_password: str = os.environ.get("EMAIL_PASSWORD", "")

def send_email(to: str, subject: str, body: str, attachment:str|None = None, cc: list[str]|str|None = None) -> None:
    """Send an email with the given subject and body to the specified recipient.

    `cc` may be a single address or a list; smtp.send_message routes To + Cc
    headers automatically, so no extra recipient bookkeeping is needed here.
    """
    msg = EmailMessage()
    msg["From"] = email_address
    msg["To"] = to
    if cc:
        msg["Cc"] = ", ".join(cc) if isinstance(cc, list) else cc
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment is not None:
        with open(attachment, "rb") as f:
            file_data = f.read()
            file_name = f.name
        mime_type, _ = mimetypes.guess_type(file_name)
        if mime_type is None:
            mime_type = "application/octet-stream"
        
        maintype, subtype = mime_type.split("/", 1)
        msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=file_name)


    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_address, email_password)
        smtp.send_message(msg)
    