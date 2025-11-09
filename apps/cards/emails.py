from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CardEmailUtil:
    """Email utilities for card-related notifications"""

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

    @classmethod
    def send_card_issued_email(cls, card):
        """Send card issuance notification to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            card_url = f"{frontend_url}/cards/{card.card_id}"

            # Mask card number for security
            masked_number = (
                f"**** **** **** {card.card_number[-4:]}"
                if card.card_number
                else "****"
            )

            context = {
                "user_name": card.user.full_name,
                "card_type": card.card_type.replace("_", " ").title(),
                "card_brand": card.card_brand.title() if card.card_brand else "Card",
                "masked_card_number": masked_number,
                "cardholder_name": card.card_holder_name,
                "expiry_date": (
                    f"{card.expiry_month:02d}/{card.expiry_year}"
                    if card.expiry_month and card.expiry_year
                    else "N/A"
                ),
                "issue_date": card.created_at.strftime("%B %d, %Y"),
                "is_virtual": card.card_type == "virtual",
                "is_active": card.status == "active",
                "currency_name": card.wallet.currency.name if card.wallet else "N/A",
                "card_url": card_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject="Your Card Has Been Issued!",
                template_name="card-issued.html",
                context=context,
                recipient=card.user.email,
            )
        except Exception as e:
            logger.error(f"Failed to send card issued email: {e}", exc_info=True)
