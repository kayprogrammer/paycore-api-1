from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TransferEmailUtil:
    """Email utilities for transfer-related notifications"""

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
    def send_transfer_success_email(cls, transaction):
        """Send transfer confirmation to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            transaction_url = (
                f"{frontend_url}/transactions/{transaction.transaction_id}"
            )

            # Determine recipient info
            recipient_name = (
                transaction.to_user.full_name if transaction.to_user else "Recipient"
            )
            recipient_account = None
            if transaction.to_wallet:
                recipient_account = str(transaction.to_wallet.wallet_id)[:16] + "..."

            context = {
                "user_name": transaction.from_user.full_name,
                "reference": transaction.external_reference
                or str(transaction.transaction_id),
                "recipient_name": recipient_name,
                "recipient_account": recipient_account,
                "amount": f"{transaction.amount:,.2f}",
                "fee_amount": (
                    f"{transaction.fee_amount:,.2f}" if transaction.fee_amount else None
                ),
                "transfer_date": transaction.created_at.strftime(
                    "%B %d, %Y at %I:%M %p"
                ),
                "currency_symbol": transaction.from_wallet.currency.symbol,
                "new_balance": f"{transaction.from_balance_after:,.2f}",
                "transaction_url": transaction_url,
                "current_year": datetime.now().year,
            }

            cls._send_email(
                subject=f"Transfer Successful - {context['reference']}",
                template_name="transfer-success.html",
                context=context,
                recipient=transaction.from_user.email,
            )
        except Exception as e:
            logger.error(f"Failed to send transfer email: {e}", exc_info=True)
