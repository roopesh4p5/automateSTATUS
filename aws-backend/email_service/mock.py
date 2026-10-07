"""Mock email service for development, testing, and dry runs."""

import logging
from typing import Any, Dict, List, Optional, Union

from .base import EmailService

logger = logging.getLogger(__name__)


class MockEmailService(EmailService):
    """Logs emails to console and retains sent messages in memory for inspection."""

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []

    def send_email(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        recipients: Union[str, List[str]],
        from_email: Optional[str] = None,
    ) -> bool:
        to_addr = ", ".join(recipients) if isinstance(recipients, (list, tuple)) else str(recipients)
        msg_record = {
            "subject": subject,
            "to": to_addr,
            "from": from_email or "system@officemonitor.local",
            "text_content": text_content,
            "html_content": html_content,
        }
        self.sent_messages.append(msg_record)
        logger.info("[MockEmailService] Simulated email dispatched to '%s' | Subject: '%s'", to_addr, subject)
        logger.debug("[MockEmailService] Body Preview:\n%s", text_content)
        return True
