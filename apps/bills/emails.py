from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BillPaymentEmailUtil:
    """Email utilities for bill payment-related notifications"""

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
    def send_bill_payment_success_email(cls, bill_payment):
        """Send bill payment confirmation to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            transaction_url = f"{frontend_url}/transactions"

            context = {
                "user_name": bill_payment.user.full_name,
                "biller_name": bill_payment.biller_name,
                "biller_category": (
                    bill_payment.biller_category.replace("_", " ").title()
                    if bill_payment.biller_category
                    else "Bill"
                ),
                "account_number": bill_payment.account_number,
                "reference": bill_payment.reference_number,
                "amount": f"{bill_payment.amount:,.2f}",
                "fee_amount": (
                    f"{bill_payment.fee_amount:,.2f}"
                    if bill_payment.fee_amount
                    else None
                ),
                "payment_date": bill_payment.paid_at.strftime("%B %d, %Y at %I:%M %p"),
                "currency_symbol": bill_payment.wallet.currency.symbol,
                "new_balance": f"{bill_payment.wallet.balance:,.2f}",
                "transaction_url": transaction_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject=f"Bill Payment Successful - {bill_payment.reference_number}",
                template_name="bill-payment-success.html",
                context=context,
                recipient=bill_payment.user.email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send bill payment email for {bill_payment.reference_number}: {e}",
                exc_info=True,
            )
