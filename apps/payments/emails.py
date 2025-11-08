from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PaymentEmailUtil:
    """Email utilities for payment-related notifications"""

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
    def send_invoice_email(cls, invoice):
        """Send invoice notification to customer"""
        try:
            # Get the frontend URL from settings or use default
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            invoice_url = f"{frontend_url}/invoices/{invoice.invoice_number}"

            # Get invoice items
            from apps.payments.models import InvoiceItem

            items_list = list(
                InvoiceItem.objects.filter(invoice=invoice).values(
                    "description", "quantity", "unit_price", "amount"
                )
            )

            # Format items for template
            formatted_items = [
                {
                    "description": item["description"],
                    "quantity": f"{item['quantity']:,.2f}",
                    "unit_price": f"{item['unit_price']:,.2f}",
                    "amount": f"{item['amount']:,.2f}",
                }
                for item in items_list
            ]

            context = {
                "customer_name": invoice.customer_name,
                "merchant_name": invoice.user.full_name,
                "invoice_number": invoice.invoice_number,
                "invoice_title": invoice.title,
                "invoice_description": invoice.description,
                "issue_date": invoice.issue_date.strftime("%B %d, %Y"),
                "due_date": invoice.due_date.strftime("%B %d, %Y"),
                "items": formatted_items,
                "subtotal": f"{invoice.subtotal:,.2f}",
                "tax_amount": (
                    f"{invoice.tax_amount:,.2f}" if invoice.tax_amount else None
                ),
                "discount_amount": (
                    f"{invoice.discount_amount:,.2f}"
                    if invoice.discount_amount
                    else None
                ),
                "total_amount": f"{invoice.total_amount:,.2f}",
                "currency_symbol": invoice.wallet.currency.symbol,
                "invoice_url": invoice_url,
                "notes": invoice.notes,
                "current_year": datetime.now().year,
            }

            cls._send_email(
                subject=f"Invoice {invoice.invoice_number} from {invoice.user.full_name}",
                template_name="invoice-created.html",
                context=context,
                recipient=invoice.customer_email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send invoice email for {invoice.invoice_number}: {e}",
                exc_info=True,
            )

    @classmethod
    def send_payment_confirmation_email(cls, payment):
        """Send payment confirmation email to payer"""
        try:
            # Get the frontend URL from settings or use default
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            transaction_url = f"{frontend_url}/transactions"

            # Determine payment description
            if payment.payment_link:
                payment_description = payment.payment_link.title
            elif payment.invoice:
                payment_description = f"Invoice {payment.invoice.invoice_number}"
            else:
                payment_description = "Payment"

            context = {
                "payer_name": payment.payer_name,
                "merchant_name": payment.merchant_user.full_name,
                "reference": payment.reference,
                "payment_date": payment.created_at.strftime("%B %d, %Y at %I:%M %p"),
                "payment_description": payment_description,
                "amount": f"{payment.amount:,.2f}",
                "fee_amount": f"{payment.fee_amount:,.2f}",
                "net_amount": f"{payment.net_amount:,.2f}",
                "currency_symbol": payment.payer_wallet.currency.symbol,
                "new_balance": f"{payment.payer_wallet.balance:,.2f}",
                "invoice_number": (
                    payment.invoice.invoice_number if payment.invoice else None
                ),
                "transaction_url": transaction_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject=f"Payment Confirmation - {payment.reference}",
                template_name="payment-confirmation.html",
                context=context,
                recipient=payment.payer_email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send payment confirmation email for {payment.reference}: {e}",
                exc_info=True,
            )

    @classmethod
    def send_payment_received_email(cls, payment):
        """Send payment received notification to merchant"""
        try:
            # Get the frontend URL from settings or use default
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            transaction_url = f"{frontend_url}/transactions"

            # Determine payment description
            if payment.payment_link:
                payment_description = payment.payment_link.title
            elif payment.invoice:
                payment_description = f"Invoice {payment.invoice.invoice_number}"
            else:
                payment_description = "Payment"

            context = {
                "merchant_name": payment.merchant_user.full_name,
                "payer_name": payment.payer_name,
                "payer_email": payment.payer_email,
                "reference": payment.reference,
                "payment_date": payment.created_at.strftime("%B %d, %Y at %I:%M %p"),
                "payment_description": payment_description,
                "gross_amount": f"{payment.amount:,.2f}",
                "fee_amount": f"{payment.fee_amount:,.2f}",
                "net_amount": f"{payment.net_amount:,.2f}",
                "currency_symbol": payment.merchant_wallet.currency.symbol,
                "new_balance": f"{payment.merchant_wallet.balance:,.2f}",
                "invoice_number": (
                    payment.invoice.invoice_number if payment.invoice else None
                ),
                "transaction_url": transaction_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject=f"Payment Received - {payment.reference}",
                template_name="payment-received.html",
                context=context,
                recipient=payment.merchant_user.email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send payment received email for {payment.reference}: {e}",
                exc_info=True,
            )
