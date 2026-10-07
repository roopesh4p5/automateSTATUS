"""EmailJS API Email Service implementation."""

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import List, Optional, Union

from .base import EmailService

logger = logging.getLogger(__name__)

EMAILJS_API_URL = "https://api.emailjs.com/api/v1.0/email/send"


class EmailJSService(EmailService):
    """EmailJS API delivery service."""

    def __init__(
        self,
        service_id: Optional[str] = None,
        template_id: Optional[str] = None,
        public_key: Optional[str] = None,
        private_key: Optional[str] = None,
        default_to: Optional[str] = None,
    ):
        self.service_id = service_id or os.environ.get("EMAILJS_SERVICE_ID", "")
        self.template_id = template_id or os.environ.get("EMAILJS_TEMPLATE_ID", "")
        # EmailJS user_id is the public key
        self.public_key = public_key or os.environ.get("EMAILJS_PUBLIC_KEY", os.environ.get("EMAILJS_USER_ID", ""))
        # EmailJS accessToken is the private key
        self.private_key = private_key or os.environ.get("EMAILJS_PRIVATE_KEY", os.environ.get("EMAILJS_ACCESS_TOKEN", ""))
        self.default_to = default_to or os.environ.get("EMAILJS_TO_EMAIL", "")

    def send_email(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        recipients: Union[str, List[str]],
        from_email: Optional[str] = None,
    ) -> bool:
        to_addr = (
            ", ".join(recipients)
            if isinstance(recipients, (list, tuple))
            else (recipients or self.default_to)
        )

        if not self.service_id or not self.template_id or not self.public_key:
            logger.error("EmailJS credentials incomplete (need service_id, template_id, public_key)")
            return False

        payload = {
            "service_id": self.service_id,
            "template_id": self.template_id,
            "user_id": self.public_key,
            "template_params": {
                "to_email": to_addr,
                "subject": subject,
                "html_content": html_content,
                "text_content": text_content,
                "message": text_content,
            },
        }
        if self.private_key:
            payload["accessToken"] = self.private_key

        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                EMAILJS_API_URL,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "OfficeNetworkMonitorBackend/1.0",
                },
                method="POST",
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=15.0, context=ctx) as resp:
                if resp.status == 200:
                    logger.info("Successfully sent email via EmailJS to %s", to_addr)
                    return True
                else:
                    logger.warning("EmailJS returned status %d", resp.status)
                    return False
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error("EmailJS HTTP error %d: %s", e.code, err_body)
            return False
        except Exception as e:
            logger.error("Failed to send email via EmailJS: %s", e)
            return False
