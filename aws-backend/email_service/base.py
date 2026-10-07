"""Abstract base class for email delivery services."""

from abc import ABC, abstractmethod
from typing import List, Optional, Union


class EmailService(ABC):
    """Abstract email service interface (PRD Section 20)."""

    @abstractmethod
    def send_email(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        recipients: Union[str, List[str]],
        from_email: Optional[str] = None,
    ) -> bool:
        """Send an email to one or more recipients.

        Args:
            subject: Email subject line.
            html_content: HTML body.
            text_content: Plain-text fallback body.
            recipients: Destination email address or list of addresses.
            from_email: Optional sender address override.

        Returns:
            bool: True if sent successfully, False otherwise.
        """
        pass
