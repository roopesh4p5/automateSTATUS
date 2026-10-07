"""Email service package providing provider abstraction and factory method."""

import logging
import os
from typing import Optional

from .base import EmailService
from .emailjs import EmailJSService
from .mock import MockEmailService
from .smtp import SmtpEmailService

logger = logging.getLogger(__name__)


def get_email_service(provider: Optional[str] = None) -> EmailService:
    """Instantiate and return the configured EmailService provider.

    Resolution order:
    1. provider argument (if given)
    2. EMAIL_PROVIDER environment variable ('smtp', 'emailjs', 'mock')
    3. Auto-detection based on presence of SMTP_* or EMAILJS_* env vars
    4. Fallback to MockEmailService
    """
    prov = (provider or os.environ.get("EMAIL_PROVIDER", "")).strip().lower()

    if prov == "smtp":
        logger.info("Initializing SMTP email service")
        return SmtpEmailService()
    elif prov == "emailjs":
        logger.info("Initializing EmailJS service")
        return EmailJSService()
    elif prov == "mock":
        logger.info("Initializing Mock email service")
        return MockEmailService()

    # Auto-detection
    if os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USERNAME"):
        logger.info("Auto-detected SMTP configuration")
        return SmtpEmailService()
    elif os.environ.get("EMAILJS_SERVICE_ID") and os.environ.get("EMAILJS_PUBLIC_KEY"):
        logger.info("Auto-detected EmailJS configuration")
        return EmailJSService()

    logger.info("No live email credentials found. Defaulting to MockEmailService for development/testing.")
    return MockEmailService()


__all__ = ["EmailService", "SmtpEmailService", "EmailJSService", "MockEmailService", "get_email_service"]
