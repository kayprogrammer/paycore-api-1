from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging
from datetime import datetime
from apps.loans.models import LoanRepaymentSchedule

logger = logging.getLogger(__name__)


class LoanEmailUtil:
    """Email utilities for loan-related notifications"""

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
    def send_loan_approved_email(cls, loan):
        """Send loan approval notification to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            loan_url = f"{frontend_url}/loans/{loan.loan_id}"

            context = {
                "user_name": loan.user.full_name,
                "loan_reference": loan.reference or loan.external_reference,
                "approved_amount": f"{loan.approved_amount:,.2f}",
                "interest_rate": f"{loan.interest_rate}",
                "loan_term": f"{loan.term_months}",
                "monthly_payment": f"{loan.monthly_payment:,.2f}",
                "total_repayment": f"{loan.total_repayment_amount:,.2f}",
                "first_payment_date": loan.first_payment_date.strftime("%B %d, %Y"),
                "approval_date": loan.approved_at.strftime("%B %d, %Y"),
                "currency_symbol": loan.wallet.currency.symbol,
                "loan_url": loan_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject="Loan Application Approved!",
                template_name="loan-approved.html",
                context=context,
                recipient=loan.user.email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send loan approval email for {loan.reference or loan.external_reference}: {e}",
                exc_info=True,
            )

    @classmethod
    def send_loan_disbursed_email(cls, loan):
        """Send loan disbursement notification to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            loan_url = f"{frontend_url}/loans/{loan.loan_id}"
            wallet_url = f"{frontend_url}/wallets/{loan.wallet.wallet_id}"

            context = {
                "user_name": loan.user.full_name,
                "loan_reference": loan.reference or loan.external_reference,
                "disbursed_amount": f"{loan.disbursed_amount:,.2f}",
                "disbursement_date": loan.disbursed_at.strftime(
                    "%B %d, %Y at %I:%M %p"
                ),
                "wallet_name": f"{loan.wallet.currency.name} Wallet",
                "new_wallet_balance": f"{loan.wallet.balance:,.2f}",
                "first_payment_date": loan.first_payment_date.strftime("%B %d, %Y"),
                "monthly_payment": f"{loan.monthly_payment:,.2f}",
                "currency_symbol": loan.wallet.currency.symbol,
                "loan_url": loan_url,
                "wallet_url": wallet_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject="Loan Disbursed Successfully!",
                template_name="loan-disbursed.html",
                context=context,
                recipient=loan.user.email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send loan disbursement email for {loan.reference or loan.external_reference}: {e}",
                exc_info=True,
            )

    @classmethod
    def send_loan_repayment_email(cls, repayment):
        """Send loan repayment confirmation to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            loan_url = f"{frontend_url}/loans/{repayment.loan.application_id}"
            transaction_url = f"{frontend_url}/transactions/{repayment.transaction_id}"

            # Check if this is the final payment
            is_final_payment = repayment.schedule.outstanding_amount <= 0
            schedule = repayment.schedule
            # Get the next schedule after this
            next_schedule = LoanRepaymentSchedule.objects.filter(loan=schedule.loan, due_date__gt=schedule.due_date).first()
            context = {
                "user_name": repayment.loan.user.full_name,
                "loan_reference": repayment.reference
                or repayment.external_reference,
                "payment_reference": repayment.reference or repayment.transaction_id,
                "payment_amount": f"{repayment.amount:,.2f}",
                "amount_paid": f"{repayment.amount:,.2f}",
                "payment_date": repayment.created_at.strftime("%B %d, %Y at %I:%M %p"),
                "principal_paid": f"{repayment.principal_paid:,.2f}",
                "interest_paid": f"{repayment.interest_paid:,.2f}",
                "remaining_balance": f"{repayment.schedule.outstanding_amount:,.2f}",
                "next_payment_date": (
                    next_schedule.due_date.strftime("%B %d, %Y")
                    if next_schedule
                    else None
                ),
                "next_payment_amount": f"{next_schedule.total_amount:,.2f}" if next_schedule else 0,
                "is_final_payment": is_final_payment,
                "currency_symbol": repayment.loan.wallet.currency.symbol,
                "loan_url": loan_url,
                "transaction_url": transaction_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject=f"Loan Repayment Successful - {repayment.reference or repayment.transaction_id}",
                template_name="loan-repayment-success.html",
                context=context,
                recipient=repayment.loan.user.email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send loan repayment email for {repayment.reference or repayment.transaction_id}: {e}",
                exc_info=True,
            )
