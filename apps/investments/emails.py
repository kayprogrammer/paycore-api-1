from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class InvestmentEmailUtil:
    """Email utilities for investment-related notifications"""

    @classmethod
    def _send_email(cls, subject, template_name, context, recipient):
        """Internal helper to render template and send email."""
        try:
            message = render_to_string(template_name, context)
            email_message = EmailMessage(subject=subject, body=message, to=[recipient])
            email_message.content_subtype = "html"
            email_message.send()
            logger.info(f"Email sent successfully to {recipient}: {subject}")
        except Exception as e:
            logger.error(f"Email sending failed for {recipient}: {e}", exc_info=True)

    # Placeholder for investment email methods
    # Will be implemented based on investment models and requirements
    @classmethod
    def send_investment_created_email(cls, investment):
        """Send investment creation confirmation to user"""
        # To be implemented when investment features are defined
        pass

    @classmethod
    def send_investment_matured_email(cls, investment):
        """Send investment maturity notification to user"""
        # To be implemented when investment features are defined
        pass
