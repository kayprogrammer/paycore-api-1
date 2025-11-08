from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class WalletEmailUtil:
    """Email utilities for wallet-related notifications"""

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
    def send_wallet_created_email(cls, wallet):
        """Send wallet creation notification to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            wallet_url = f"{frontend_url}/wallets/{wallet.wallet_id}"

            context = {
                "user_name": wallet.user.full_name,
                "currency_name": wallet.currency.name,
                "currency_code": wallet.currency.code,
                "currency_symbol": wallet.currency.symbol,
                "wallet_id": str(wallet.wallet_id),
                "balance": f"{wallet.balance:,.2f}",
                "created_date": wallet.created_at.strftime("%B %d, %Y"),
                "wallet_url": wallet_url,
                "current_year": datetime.now().year,
            }

            cls._send_email(
                subject=f"{wallet.currency.name} Wallet Created Successfully!",
                template_name="wallet-created.html",
                context=context,
                recipient=wallet.user.email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send wallet created email for wallet {wallet.wallet_id}: {e}",
                exc_info=True,
            )
