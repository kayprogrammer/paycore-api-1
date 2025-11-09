import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction as db_transaction
from datetime import timedelta
from asgiref.sync import async_to_sync
from django.conf import settings
from apps.loans.models import (
    AutoRepayment,
    LoanRepaymentSchedule,
    RepaymentStatus,
    AutoRepaymentStatus,
    LoanStatus,
    LoanApplication,
)
from apps.loans.services.loan_processor import LoanProcessor
from apps.loans.services.loan_manager import LoanManager
from apps.loans.schemas import MakeLoanRepaymentSchema, ApproveLoanSchema
from apps.accounts.models import User
from apps.loans.emails import LoanEmailUtil
from apps.loans.models import LoanApplication
from apps.loans.models import LoanRepayment

logger = logging.getLogger(__name__)


# ==================== LOAN APPROVAL TASKS ====================


class LoanApprovalTasks:
    """Background tasks for loan approval and disbursement"""

    @staticmethod
    @shared_task(
        bind=True,
        name="loans.auto_approve_loan",
        queue="loans",
    )
    def auto_approve_loan(self, application_id: str):
        """
        Auto-approve loan after 15 seconds for internal provider
        This simulates loan review processing time for demo/testing purposes
        """
        try:
            # Get loan application to check status
            loan = LoanApplication.objects.select_related(
                "loan_product", "wallet", "wallet__currency", "user"
            ).get_or_none(application_id=application_id)

            if not loan:
                logger.error(
                    f"Loan application {application_id} not found for auto-approval"
                )
                return {"status": "failed", "error": "Loan application not found"}

            if loan.status != LoanStatus.PENDING:
                logger.warning(
                    f"Loan application {application_id} is not in pending status, "
                    f"skipping auto-approval. Current status: {loan.status}"
                )
                return {"status": "skipped", "current_status": loan.status}

            # Create a system user for approval if needed
            system_user = User.objects.filter(email="system@paycore.com").first()
            if not system_user:
                # Use the loan applicant as reviewer for demo purposes
                system_user = loan.user

            # Approve with requested amount and existing interest rate
            approval_data = ApproveLoanSchema(
                approved_amount=loan.requested_amount,
                interest_rate=loan.interest_rate,
            )
            approved_loan = async_to_sync(LoanManager.approve_loan)(
                reviewer=system_user,
                application_id=application_id,
                data=approval_data,
            )
            logger.info(
                f"Loan {application_id} auto-approved successfully. "
                f"Amount: {approved_loan.approved_amount}, "
                f"Status: {approved_loan.status}"
            )

            # Use LoanProcessor to disburse the loan
            async_to_sync(LoanProcessor.disburse_loan)(
                application_id=application_id,
                admin_user=system_user,
            )

            return {
                "status": "success",
                "application_id": application_id,
                "approved_amount": float(approved_loan.approved_amount),
                "approved_at": (
                    approved_loan.reviewed_at.isoformat()
                    if approved_loan.reviewed_at
                    else None
                ),
            }

        except Exception as exc:
            logger.error(
                f"Auto-approve loan task failed for {application_id}: {str(exc)}"
            )
            return {"status": "failed", "error": str(exc)}

    @staticmethod
    @shared_task(
        bind=True,
        name="loans.auto_disburse_loan",
        queue="loans",
    )
    def auto_disburse_loan(self, application_id: str):
        """
        Auto-disburse loan after approval for internal provider
        This simulates loan disbursement processing time for demo/testing purposes
        """
        try:
            # Get loan application to check status
            try:
                loan = LoanApplication.objects.select_related(
                    "loan_product", "wallet", "wallet__currency", "user"
                ).get(application_id=application_id)
            except LoanApplication.DoesNotExist:
                loan = None

            if not loan:
                logger.error(
                    f"Loan application {application_id} not found for auto-disbursement"
                )
                return {"status": "failed", "error": "Loan application not found"}

            if loan.status != LoanStatus.APPROVED:
                logger.warning(
                    f"Loan application {application_id} is not in approved status, "
                    f"skipping auto-disbursement. Current status: {loan.status}"
                )
                return {"status": "skipped", "current_status": loan.status}

            if loan.disbursed_at:
                logger.warning(
                    f"Loan application {application_id} has already been disbursed"
                )
                return {"status": "skipped", "reason": "already_disbursed"}

            # Create a system user for disbursement if needed
            system_user = User.objects.filter(is_staff=True).first()

            # Use LoanProcessor to disburse the loan
            disbursed_loan = async_to_sync(LoanProcessor.disburse_loan)(
                application_id=application_id,
                admin_user=system_user,
            )

            logger.info(
                f"Loan {application_id} auto-disbursed successfully. "
                f"Amount: {disbursed_loan.approved_amount}, "
                f"Status: {disbursed_loan.status}"
            )

            return {
                "status": "success",
                "application_id": application_id,
                "disbursed_amount": float(disbursed_loan.approved_amount),
                "disbursed_at": (
                    disbursed_loan.disbursed_at.isoformat()
                    if disbursed_loan.disbursed_at
                    else None
                ),
            }

        except Exception as exc:
            logger.error(
                f"Auto-disburse loan task failed for {application_id}: {str(exc)}"
            )
            return {"status": "failed", "error": str(exc)}


# ==================== AUTO REPAYMENT TASKS ====================


class AutoRepaymentTasks:
    """Automatic loan repayment tasks"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 2, "countdown": 300},
        name="loans.process_auto_repayments",
        queue="loans",
    )
    def process_auto_repayments(self):
        """
        Process automatic loan repayments for due schedules
        Runs daily to check for upcoming/due repayments
        """

        try:
            today = timezone.now().date()
            processed_count = 0
            failed_count = 0

            # Get all active auto-repayment configurations
            auto_repayments = (
                AutoRepayment.objects.filter(
                    is_enabled=True,
                    status=AutoRepaymentStatus.ACTIVE,
                    loan__status__in=[LoanStatus.ACTIVE, LoanStatus.OVERDUE],
                )
                .select_related("loan", "loan__user", "wallet", "wallet__currency")
                .all()
            )

            for auto_repay in auto_repayments:
                try:
                    # Calculate trigger date (due_date - days_before_due)
                    trigger_date = today + timedelta(days=auto_repay.days_before_due)

                    # Get next pending/overdue schedule due on or before trigger date
                    next_schedule = (
                        LoanRepaymentSchedule.objects.filter(
                            loan=auto_repay.loan,
                            status__in=[
                                RepaymentStatus.PENDING,
                                RepaymentStatus.OVERDUE,
                            ],
                            due_date__lte=trigger_date,
                        )
                        .order_by("installment_number")
                        .first()
                    )

                    if not next_schedule:
                        continue  # No pending payments due on or before trigger date

                    # Determine payment amount
                    if auto_repay.auto_pay_full_amount:
                        amount = (
                            next_schedule.outstanding_amount + next_schedule.late_fee
                        )
                    elif auto_repay.custom_amount:
                        amount = min(
                            auto_repay.custom_amount,
                            next_schedule.outstanding_amount + next_schedule.late_fee,
                        )
                    else:
                        amount = (
                            next_schedule.outstanding_amount + next_schedule.late_fee
                        )

                    # Check wallet balance
                    if auto_repay.wallet.balance < amount:
                        AutoRepaymentTasks._handle_payment_failure(
                            auto_repay,
                            f"Insufficient balance. Required: {amount}, Available: {auto_repay.wallet.balance}",
                            retry_task=self if auto_repay.retry_on_failure else None,
                        )
                        failed_count += 1
                        continue

                    # Process payment
                    user = auto_repay.loan.user
                    payment_data = MakeLoanRepaymentSchema(
                        wallet_id=auto_repay.wallet.wallet_id,
                        amount=amount,
                        schedule_id=next_schedule.schedule_id,
                        notes=f"Automatic repayment for installment #{next_schedule.installment_number}",
                    )

                    # Process repayment using async_to_sync
                    repayment = async_to_sync(LoanProcessor.make_repayment)(
                        user, auto_repay.loan.application_id, payment_data
                    )

                    auto_repay.total_payments_made += 1
                    auto_repay.last_payment_date = timezone.now()
                    auto_repay.last_payment_amount = amount
                    auto_repay.consecutive_failures = 0  # Reset failure counter
                    auto_repay.save(
                        update_fields=[
                            "total_payments_made",
                            "last_payment_date",
                            "last_payment_amount",
                            "consecutive_failures",
                            "updated_at",
                        ]
                    )

                    processed_count += 1
                    logger.info(
                        f"Auto-repayment successful: Loan {auto_repay.loan.application_id}, Amount: {amount}"
                    )

                    if auto_repay.send_notification_on_success:
                        AutoRepaymentTasks.send_auto_repayment_notification.delay(
                            auto_repay.id, "success", amount
                        )

                except Exception as e:
                    logger.error(
                        f"Auto-repayment failed for loan {auto_repay.loan.application_id}: {str(e)}"
                    )
                    AutoRepaymentTasks._handle_payment_failure(auto_repay, str(e))
                    failed_count += 1

            logger.info(
                f"Auto-repayment batch complete: {processed_count} succeeded, {failed_count} failed"
            )
            return {
                "status": "success",
                "processed": processed_count,
                "failed": failed_count,
            }

        except Exception as exc:
            logger.error(f"Auto-repayment batch failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    def _handle_payment_failure(auto_repay, reason: str, retry_task=None):
        """Handle failed automatic payment"""
        auto_repay.last_failure_date = timezone.now()
        auto_repay.last_failure_reason = reason
        auto_repay.consecutive_failures += 1

        # Suspend if max retries exceeded
        if auto_repay.consecutive_failures >= auto_repay.max_retry_attempts:
            auto_repay.status = AutoRepaymentStatus.FAILED
            auto_repay.suspend(
                f"Max retry attempts ({auto_repay.max_retry_attempts}) exceeded"
            )
            logger.warning(
                f"Auto-repayment suspended for loan {auto_repay.loan.application_id}"
            )

        auto_repay.save(
            update_fields=[
                "last_failure_date",
                "last_failure_reason",
                "consecutive_failures",
                "status",
                "updated_at",
            ]
        )

        if auto_repay.send_notification_on_failure:
            AutoRepaymentTasks.send_auto_repayment_notification.delay(
                auto_repay.id, "failure", reason=reason
            )

        if (
            retry_task
            and auto_repay.retry_on_failure
            and auto_repay.consecutive_failures < auto_repay.max_retry_attempts
        ):
            retry_countdown = (
                auto_repay.retry_interval_hours * 3600
            )  # Convert to seconds
            AutoRepaymentTasks.retry_failed_auto_repayment.apply_async(
                args=[auto_repay.id], countdown=retry_countdown
            )

    @staticmethod
    @shared_task(name="loans.retry_failed_auto_repayment", queue="loans")
    def retry_failed_auto_repayment(auto_repayment_id: int):
        """Retry a failed automatic repayment"""

        try:
            auto_repay = AutoRepayment.objects.select_related(
                "loan", "loan__user", "wallet", "wallet__currency"
            ).get(id=auto_repayment_id)

            next_schedule = (
                LoanRepaymentSchedule.objects.filter(
                    loan=auto_repay.loan,
                    status__in=[RepaymentStatus.PENDING, RepaymentStatus.OVERDUE],
                )
                .order_by("installment_number")
                .first()
            )

            if not next_schedule:
                logger.info(
                    f"No pending schedule for retry: {auto_repay.loan.application_id}"
                )
                return {"status": "skipped", "reason": "no_pending_schedule"}

            if auto_repay.auto_pay_full_amount:
                amount = next_schedule.outstanding_amount + next_schedule.late_fee
            elif auto_repay.custom_amount:
                amount = min(
                    auto_repay.custom_amount,
                    next_schedule.outstanding_amount + next_schedule.late_fee,
                )
            else:
                amount = next_schedule.outstanding_amount + next_schedule.late_fee

            if auto_repay.wallet.balance < amount:
                AutoRepaymentTasks._handle_payment_failure(
                    auto_repay,
                    f"Insufficient balance on retry. Required: {amount}, Available: {auto_repay.wallet.balance}",
                )
                return {"status": "failed", "reason": "insufficient_balance"}

            # Process payment
            user = auto_repay.loan.user
            payment_data = MakeLoanRepaymentSchema(
                wallet_id=auto_repay.wallet.wallet_id,
                amount=amount,
                schedule_id=next_schedule.schedule_id,
                notes=f"Automatic repayment retry #{auto_repay.consecutive_failures}",
            )

            repayment = async_to_sync(LoanProcessor.make_repayment)(
                user, auto_repay.loan.application_id, payment_data
            )

            auto_repay.total_payments_made += 1
            auto_repay.last_payment_date = timezone.now()
            auto_repay.last_payment_amount = amount
            auto_repay.consecutive_failures = 0  # Reset on success
            auto_repay.save(
                update_fields=[
                    "total_payments_made",
                    "last_payment_date",
                    "last_payment_amount",
                    "consecutive_failures",
                    "updated_at",
                ]
            )

            logger.info(
                f"Auto-repayment retry successful: Loan {auto_repay.loan.application_id}"
            )

            if auto_repay.send_notification_on_success:
                AutoRepaymentTasks.send_auto_repayment_notification.delay(
                    auto_repay.id, "success", amount
                )

            return {"status": "success", "amount": str(amount)}

        except Exception as e:
            logger.error(f"Auto-repayment retry failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    @staticmethod
    @shared_task(name="loans.send_auto_repayment_notification", queue="emails")
    def send_auto_repayment_notification(
        auto_repayment_id: int, notification_type: str, amount=None, reason=None
    ):
        """Send notification for auto-repayment success/failure"""

        try:
            auto_repay = AutoRepayment.objects.select_related("loan", "loan__user").get(
                id=auto_repayment_id
            )
            user = auto_repay.loan.user

            if notification_type == "success":
                # TODO: Integrate with notifications module when available
                logger.info(
                    f"Auto-repayment success notification: User {user.email}, Amount: {amount}"
                )
                # EmailUtil.send_auto_repayment_success(user, auto_repay, amount)
            elif notification_type == "failure":
                logger.info(
                    f"Auto-repayment failure notification: User {user.email}, Reason: {reason}"
                )
                # EmailUtil.send_auto_repayment_failure(user, auto_repay, reason)

            return {"status": "success", "notification_type": notification_type}

        except Exception as e:
            logger.error(f"Failed to send auto-repayment notification: {str(e)}")
            return {"status": "failed", "error": str(e)}


class LoanMaintenanceTasks:
    """Loan system maintenance tasks"""

    @staticmethod
    @shared_task(name="loans.update_overdue_schedules", queue="maintenance")
    def update_overdue_schedules():
        """
        Update repayment schedules that are overdue
        Calculates days overdue and applies late fees
        """

        try:
            today = timezone.now().date()
            updated_count = 0

            overdue_schedules = LoanRepaymentSchedule.objects.filter(
                status__in=[RepaymentStatus.PENDING, RepaymentStatus.PARTIAL],
                due_date__lt=today,
            ).select_related("loan", "loan__loan_product")

            for schedule in overdue_schedules:
                days_overdue = (today - schedule.due_date).days
                schedule.days_overdue = days_overdue
                schedule.status = RepaymentStatus.OVERDUE

                # Apply late fee if not already applied
                if (
                    schedule.late_fee == 0
                    and schedule.loan.loan_product.late_payment_fee > 0
                ):
                    schedule.late_fee = schedule.loan.loan_product.late_payment_fee

                schedule.save(
                    update_fields=["days_overdue", "status", "late_fee", "updated_at"]
                )

                if schedule.loan.status == LoanStatus.ACTIVE:
                    schedule.loan.status = LoanStatus.OVERDUE
                    schedule.loan.save(update_fields=["status", "updated_at"])

                updated_count += 1

            logger.info(f"Updated {updated_count} overdue schedules")
            return {"status": "success", "updated_count": updated_count}

        except Exception as e:
            logger.error(f"Failed to update overdue schedules: {str(e)}")
            return {"status": "failed", "error": str(e)}

    @staticmethod
    @shared_task(name="loans.cleanup_old_credit_scores", queue="maintenance")
    def cleanup_old_credit_scores():
        """
        Clean up old credit score records, keeping only the latest per user
        Keeps last 10 score records per user for history

        Optimized to use a single DELETE query with window functions
        instead of N queries per user
        """
        from apps.loans.models import CreditScore
        from django.db.models import Window, F
        from django.db.models.functions import RowNumber

        try:
            # Annotate each credit score with its rank within the user's scores
            # Partition by user_id and order by created_at descending
            scores_with_rank = CreditScore.objects.annotate(
                rank=Window(
                    expression=RowNumber(),
                    partition_by=[F("user_id")],
                    order_by=F("created_at").desc(),
                )
            )
            scores_to_delete = scores_with_rank.filter(rank__gt=10).values_list(
                "id", flat=True
            )
            deleted_count, _ = CreditScore.objects.filter(
                id__in=list(scores_to_delete)
            ).delete()

            logger.info(f"Cleaned up {deleted_count} old credit score records")
            return {"status": "success", "deleted_count": deleted_count}

        except Exception as e:
            logger.error(f"Failed to cleanup old credit scores: {str(e)}")
            return {"status": "failed", "error": str(e)}


# ==================== LOAN EMAIL TASKS ====================


class LoanEmailTasks:
    """Email tasks for loan-related notifications"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="loans.send_loan_approved_email",
        queue="emails",
    )
    def send_loan_approved_email(self, loan_id: str):
        """Send loan approval notification email"""
        try:
            try:
                loan = LoanApplication.objects.select_related(
                    "user", "wallet", "wallet__currency"
                ).get(application_id=loan_id)
            except LoanApplication.DoesNotExist:
                loan = None

            if not loan:
                logger.error(f"Loan {loan_id} not found")
                return {"status": "failed", "error": "Loan not found"}

            LoanEmailUtil.send_loan_approved_email(loan)
            logger.info(f"Loan approval email sent for loan {loan.application_id}")
            return {"status": "success", "application_id": str(loan.application_id)}
        except Exception as exc:
            logger.error(f"Loan approval email failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="loans.send_loan_disbursed_email",
        queue="emails",
    )
    def send_loan_disbursed_email(self, loan_id: str):
        """Send loan disbursement notification email"""
        try:
            try:
                loan = LoanApplication.objects.select_related(
                    "user", "wallet", "wallet__currency"
                ).get(application_id=loan_id)
            except LoanApplication.DoesNotExist:
                loan = None

            if not loan:
                logger.error(f"Loan {loan_id} not found")
                return {"status": "failed", "error": "Loan not found"}

            LoanEmailUtil.send_loan_disbursed_email(loan)
            logger.info(f"Loan disbursement email sent for loan {loan.application_id}")
            return {"status": "success", "application_id": str(loan.application_id)}
        except Exception as exc:
            logger.error(f"Loan disbursement email failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="loans.send_loan_repayment_email",
        queue="emails",
    )
    def send_loan_repayment_email(self, repayment_id: str):
        """Send loan repayment confirmation email"""
        try:
            repayment = LoanRepayment.objects.select_related(
                "loan", "loan__user", "loan__wallet", "loan__wallet__currency"
            ).get_or_none(repayment_id=repayment_id)

            if not repayment:
                logger.error(f"Loan Repayment {repayment_id} not found")
                return {"status": "failed", "error": "Loan Repayment not found"}

            LoanEmailUtil.send_loan_repayment_email(repayment)
            logger.info(
                f"Loan repayment email sent for repayment {repayment.reference}"
            )
            return {"status": "success", "reference": repayment.reference}
        except Exception as exc:
            logger.error(f"Loan repayment email failed: {str(exc)}")
            raise self.retry(exc=exc)


# Expose task functions for imports
auto_approve_loan = LoanApprovalTasks.auto_approve_loan
auto_disburse_loan = LoanApprovalTasks.auto_disburse_loan
process_auto_repayments = AutoRepaymentTasks.process_auto_repayments
retry_failed_auto_repayment = AutoRepaymentTasks.retry_failed_auto_repayment
send_auto_repayment_notification = AutoRepaymentTasks.send_auto_repayment_notification
update_overdue_schedules = LoanMaintenanceTasks.update_overdue_schedules
cleanup_old_credit_scores = LoanMaintenanceTasks.cleanup_old_credit_scores
send_loan_approved_email_async = LoanEmailTasks.send_loan_approved_email
send_loan_disbursed_email_async = LoanEmailTasks.send_loan_disbursed_email
send_loan_repayment_email_async = LoanEmailTasks.send_loan_repayment_email
