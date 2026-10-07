"""SMTP Email Service implementation."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import smtplib
from typing import List, Optional, Union

from .base import EmailService

logger = logging.getLogger(__name__)


class SmtpEmailService(EmailService):
    """SMTP Email delivery service using standard smtplib."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: Optional[bool] = None,
        from_email: Optional[str] = None,
    ):
        self.host = host or os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.port = port or int(os.environ.get("SMTP_PORT", "587"))
        self.username = username or os.environ.get("SMTP_USERNAME", "")
        self.password = password or os.environ.get("SMTP_PASSWORD", "")
        tls_env = os.environ.get("SMTP_USE_TLS", "true").lower()
        self.use_tls = use_tls if use_tls is not None else (tls_env in ("true", "1", "yes"))
        self.default_from = from_email or os.environ.get("SMTP_FROM_EMAIL", self.username)

    def send_email(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        recipients: Union[str, List[str]],
        from_email: Optional[str] = None,
    ) -> bool:
        if isinstance(recipients, str):
            recipient_list = [r.strip() for r in recipients.replace(";", ",").split(",") if r.strip()]
        else:
            recipient_list = list(recipients)

        sender = from_email or self.default_from
        if not sender or not recipient_list:
            logger.error("SMTP error: Missing sender or recipient address")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipient_list)

        # Attach text/plain first, then text/html
        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            logger.info("Connecting to SMTP server %s:%d...", self.host, self.port)
            if self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=15)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                if self.use_tls:
                    server.starttls()

            if self.username and self.password:
                server.login(self.username, self.password)

            server.sendmail(sender, recipient_list, msg.as_string())
            server.quit()
            logger.info("Email successfully sent via SMTP to %s", recipient_list)
            return True
        except Exception as e:
            logger.error("Failed to send email via SMTP: %s", e)
            return False
