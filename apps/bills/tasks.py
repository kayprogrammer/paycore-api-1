"""
Celery tasks for bills app
"""

import logging
from celery import shared_task
from apps.bills.models import BillPayment
from apps.bills.emails import BillPaymentEmailUtil

logger = logging.getLogger(__name__)


class BillPaymentEmailTasks:
    """Email tasks for bill payment-related notifications"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="bills.send_bill_payment_success_email",
        queue="emails",
    )
    def send_bill_payment_success_email(self, bill_payment_id: str):
        """Send bill payment confirmation email"""
        try:
            bill_payment = BillPayment.objects.select_related(
                "user", "wallet", "wallet__currency"
            ).get_or_none(id=bill_payment_id)

            if not bill_payment:
                logger.error(f"Bill Payment {bill_payment_id} not found")
                return {"status": "failed", "error": "Bill Payment not found"}

            BillPaymentEmailUtil.send_bill_payment_success_email(bill_payment)
            logger.info(
                f"Bill payment email sent for payment {bill_payment.reference_number}"
            )
            return {"status": "success", "reference": bill_payment.reference_number}
        except Exception as exc:
            logger.error(f"Bill payment email failed: {str(exc)}")
            raise self.retry(exc=exc)


# Expose task functions for imports
send_bill_payment_success_email_async = (
    BillPaymentEmailTasks.send_bill_payment_success_email
)
