"""
Celery tasks for payments app
"""

import logging
from celery import shared_task
from apps.payments.models import Invoice, Payment
from apps.payments.emails import PaymentEmailUtil

logger = logging.getLogger(__name__)


class PaymentEmailTasks:
    """Email tasks for payment-related notifications"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="payments.send_invoice_email",
        queue="emails",
    )
    def send_invoice_email(self, invoice_id: str):
        """Send invoice notification email to customer"""
        try:
            invoice = Invoice.objects.select_related(
                "user", "wallet", "wallet__currency"
            ).get_or_none(invoice_id=invoice_id)

            if not invoice:
                logger.error(f"Invoice {invoice_id} not found")
                return {"status": "failed", "error": "Invoice not found"}

            PaymentEmailUtil.send_invoice_email(invoice)
            logger.info(f"Invoice email sent for invoice {invoice.invoice_number}")
            return {"status": "success", "invoice_number": invoice.invoice_number}
        except Exception as exc:
            logger.error(f"Invoice email failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="payments.send_payment_confirmation_email",
        queue="emails",
    )
    def send_payment_confirmation_email(self, payment_id: str):
        """Send payment confirmation email to payer"""
        try:
            payment = Payment.objects.select_related(
                "payer_wallet",
                "payer_wallet__currency",
                "merchant_user",
                "payment_link",
                "invoice",
            ).get_or_none(payment_id=payment_id)

            if not payment:
                logger.error(f"Payment {payment_id} not found")
                return {"status": "failed", "error": "Payment not found"}

            PaymentEmailUtil.send_payment_confirmation_email(payment)
            logger.info(
                f"Payment confirmation email sent for payment {payment.reference}"
            )
            return {"status": "success", "reference": payment.reference}
        except Exception as exc:
            logger.error(f"Payment confirmation email failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="payments.send_payment_received_email",
        queue="emails",
    )
    def send_payment_received_email(self, payment_id: str):
        """Send payment received notification email to merchant"""
        try:
            payment = Payment.objects.select_related(
                "merchant_wallet",
                "merchant_wallet__currency",
                "merchant_user",
                "payment_link",
                "invoice",
            ).get_or_none(payment_id=payment_id)

            if not payment:
                logger.error(f"Payment {payment_id} not found")
                return {"status": "failed", "error": "Payment not found"}

            PaymentEmailUtil.send_payment_received_email(payment)
            logger.info(
                f"Payment received email sent to merchant for payment {payment.reference}"
            )
            return {"status": "success", "reference": payment.reference}
        except Exception as exc:
            logger.error(f"Payment received email failed: {str(exc)}")
            raise self.retry(exc=exc)


# Expose task functions for imports
send_invoice_email_async = PaymentEmailTasks.send_invoice_email
send_payment_confirmation_email_async = (
    PaymentEmailTasks.send_payment_confirmation_email
)
send_payment_received_email_async = PaymentEmailTasks.send_payment_received_email
