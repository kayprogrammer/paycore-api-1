import logging
from celery import shared_task
from typing import Dict, Any
from asgiref.sync import async_to_sync

from apps.compliance.models import KYCVerification, KYCDocument, KYCStatus
from apps.compliance.services.kyc_provider import KYCProviderService
from apps.compliance.services.compliance_checker import ComplianceChecker
from apps.compliance.schemas import (
    CreateAMLCheckSchema,
    CreateSanctionsScreeningSchema,
    UpdateKYCStatusSchema,
)
from apps.compliance.services.kyc_manager import KYCManager

from apps.accounts.models import User
from datetime import date, timedelta
from decimal import Decimal
from apps.transactions.models import Transaction
from django.utils import timezone
from asgiref.sync import async_to_sync
from apps.compliance.emails import KYCEmailUtil

logger = logging.getLogger(__name__)


# ==================== KYC TASKS ====================


class KYCTasks:
    """Background tasks for KYC verification processing"""

    @staticmethod
    @shared_task(
        bind=True,
        name="compliance.auto_approve_kyc",
        queue="compliance",
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 10},
        retry_backoff=True,
    )
    def auto_approve_kyc(self, kyc_id: str):
        """
        Auto-approve KYC instantly for internal provider
        This simulates instant processing for demo/testing purposes
        """
        try:
            # Get KYC to check status
            kyc = KYCVerification.objects.select_related("user").get_or_none(
                kyc_id=kyc_id
            )

            if not kyc:
                logger.error(f"KYC {kyc_id} not found for auto-approval")
                return {"status": "failed", "error": "KYC record not found"}

            if kyc.status != KYCStatus.PENDING:
                logger.warning(
                    f"KYC {kyc_id} is not in pending status, skipping auto-approval"
                )
                return {"status": "skipped", "current_status": kyc.status}

            update_data = UpdateKYCStatusSchema(
                status=KYCStatus.APPROVED,
                rejection_reason=None,
                expires_at=None,
            )
            admin_user = None  # System auto-approval, no specific admin
            updated_kyc = async_to_sync(KYCManager.update_kyc_status)(
                admin_user, kyc_id, update_data
            )

            logger.info(f"KYC {kyc_id} auto-approved successfully via KYCManager")
            return {
                "status": "success",
                "kyc_id": kyc_id,
                "approved_at": (
                    updated_kyc.reviewed_at.isoformat()
                    if updated_kyc.reviewed_at
                    else None
                ),
            }

        except Exception as exc:
            logger.error(f"Auto-approve KYC task failed for {kyc_id}: {str(exc)}")
            # Retry on database connection errors
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="compliance.process_kyc_verification",
        queue="kyc",
    )
    def process_kyc_verification(self, kyc_id: str):
        """
        Process KYC verification by submitting to external provider
        This task is triggered when a user submits KYC documents
        """
        try:
            kyc = KYCVerification.objects.select_related("user").get_or_none(
                kyc_id=kyc_id
            )

            if not kyc:
                logger.error(f"KYC {kyc_id} not found")
                return {"status": "failed", "error": "KYC record not found"}

            # Get associated documents
            documents = list(KYCDocument.objects.filter(kyc_verification=kyc))

            if not documents:
                logger.warning(f"No documents found for KYC {kyc_id}")
                return {
                    "status": "failed",
                    "error": "No documents uploaded for verification",
                }

            # Submit to provider
            provider_service = KYCProviderService()
            submission_success = provider_service.submit_kyc_for_verification(
                kyc, documents
            )

            if not submission_success:
                logger.warning(
                    f"KYC {kyc_id} submission failed, marked for manual review"
                )
                return {
                    "status": "failed",
                    "kyc_id": kyc_id,
                    "message": "Automated submission failed, requires manual review",
                }

            logger.info(f"KYC {kyc_id} successfully submitted for verification")
            return {
                "status": "success",
                "kyc_id": kyc_id,
                "provider_reference_id": kyc.provider_reference_id,
            }

        except Exception as exc:
            logger.error(f"KYC verification task failed for {kyc_id}: {str(exc)}")
            raise self.retry(exc=exc)


class KYCWebhookTasks:
    """Background tasks for processing KYC webhooks from providers"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 5, "countdown": 30},
        name="compliance.process_kyc_webhook",
        queue="webhooks",
    )
    def process_kyc_webhook(self, webhook_data: Dict[str, Any]):
        """
        Process webhook updates from KYC providers (Onfido, Jumio, etc.)
        Called when provider sends verification status updates
        """
        try:
            provider_service = KYCProviderService()
            success = provider_service.process_webhook_update(webhook_data)

            if not success:
                logger.warning("KYC webhook processing failed, will retry")
                raise Exception("Webhook processing failed")

            logger.info("KYC webhook processed successfully")
            return {"status": "success", "webhook_processed": True}

        except Exception as exc:
            logger.error(f"KYC webhook processing failed: {str(exc)}")
            raise self.retry(exc=exc)


# ==================== AML TASKS ====================


class AMLTasks:
    """Background tasks for AML (Anti-Money Laundering) checks"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 120},
        name="compliance.perform_aml_check",
        queue="compliance",
    )
    def perform_aml_check(self, user_id: str, transaction_id: str = None):
        """
        Perform AML check on a user or transaction
        Can be triggered manually or automatically for high-value transactions
        """
        try:

            user = User.objects.get_or_none(id=user_id)
            if not user:
                logger.error(f"User {user_id} not found for AML check")
                return {"status": "failed", "error": "User not found"}

            # Create AML check
            check_data = CreateAMLCheckSchema(
                user_id=user_id,
                transaction_id=transaction_id,
                check_type="automated_screening",
                provider="Internal",
            )

            aml_check = async_to_sync(ComplianceChecker.create_aml_check)(check_data)

            logger.info(f"AML check {aml_check.check_id} completed for user {user_id}")
            return {
                "status": "success",
                "check_id": str(aml_check.check_id),
                "risk_level": aml_check.risk_level,
                "passed": aml_check.passed,
            }

        except Exception as exc:
            logger.error(f"AML check task failed for user {user_id}: {str(exc)}")
            raise self.retry(exc=exc)


# ==================== SANCTIONS SCREENING TASKS ====================


class SanctionsTasks:
    """Background tasks for sanctions screening"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 120},
        name="compliance.screen_for_sanctions",
        queue="compliance",
    )
    def screen_for_sanctions(
        self,
        user_id: str,
        full_name: str,
        date_of_birth: str = None,
        nationality: str = None,
    ):
        """
        Screen user against sanctions lists (OFAC, UN, EU)
        Triggered when user completes KYC or periodically for existing users
        """
        try:
            user = User.objects.get_or_none(id=user_id)
            if not user:
                logger.error(f"User {user_id} not found for sanctions screening")
                return {"status": "failed", "error": "User not found"}

            # Create sanctions screening
            screening_data = CreateSanctionsScreeningSchema(
                user_id=user_id,
                full_name=full_name,
                date_of_birth=(
                    date.fromisoformat(date_of_birth) if date_of_birth else None
                ),
                nationality=nationality,
                provider="Internal",
            )

            screening = async_to_sync(ComplianceChecker.create_sanctions_screening)(
                screening_data
            )

            logger.info(
                f"Sanctions screening {screening.screening_id} completed for user {user_id}"
            )
            return {
                "status": "success",
                "screening_id": str(screening.screening_id),
                "is_match": screening.is_match,
                "matched_lists": screening.matched_lists,
            }

        except Exception as exc:
            logger.error(
                f"Sanctions screening task failed for user {user_id}: {str(exc)}"
            )
            raise self.retry(exc=exc)


# ==================== TRANSACTION MONITORING TASKS ====================


class TransactionMonitoringTasks:
    """Background tasks for transaction monitoring and suspicious activity detection"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 2, "countdown": 60},
        name="compliance.monitor_transaction",
        queue="monitoring",
    )
    def monitor_transaction(
        self,
        user_id: str,
        transaction_id: str,
        transaction_amount: float,
        transaction_type: str,
    ):
        """
        Monitor transaction for suspicious activity
        Called automatically for every transaction above a certain threshold
        """
        try:

            user = User.objects.filter(id=user_id).first()
            if not user:
                logger.error(f"User {user_id} not found for transaction monitoring")
                return {"status": "failed", "error": "User not found"}

            # Define rules for suspicious activity
            triggered_rules = []

            # Rule 1: Large transaction
            if Decimal(str(transaction_amount)) > Decimal("10000"):
                triggered_rules.append("large_transaction")

            # Rule 2: High frequency (check recent transactions)

            recent_count = Transaction.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timedelta(hours=24),
            ).count()

            if recent_count > 10:
                triggered_rules.append("high_frequency")

            # Rule 3: Unusual time (outside 6 AM - 10 PM)
            current_hour = timezone.now().hour
            if current_hour < 6 or current_hour > 22:
                triggered_rules.append("unusual_time")

            # Only create alert if rules are triggered
            if triggered_rules:
                alert = async_to_sync(ComplianceChecker.create_monitoring_alert)(
                    user=user,
                    transaction_id=transaction_id,
                    alert_type="automated_detection",
                    description=f"Transaction flagged by rules: {', '.join(triggered_rules)}",
                    triggered_rules=triggered_rules,
                    transaction_amount=Decimal(str(transaction_amount)),
                    transaction_type=transaction_type,
                )

                logger.warning(
                    f"Transaction monitoring alert {alert.monitoring_id} created "
                    f"for transaction {transaction_id}"
                )
                return {
                    "status": "alert_created",
                    "monitoring_id": str(alert.monitoring_id),
                    "risk_level": alert.risk_level,
                    "triggered_rules": triggered_rules,
                }
            else:
                logger.info(f"Transaction {transaction_id} passed monitoring checks")
                return {"status": "passed", "triggered_rules": []}

        except Exception as exc:
            logger.error(
                f"Transaction monitoring task failed for {transaction_id}: {str(exc)}"
            )
            raise self.retry(exc=exc)


# ==================== PERIODIC COMPLIANCE TASKS ====================


@shared_task(name="compliance.daily_kyc_expiry_check", queue="compliance")
def check_kyc_expiry():
    """
    Daily task to check for expired KYC verifications
    Runs at midnight to mark expired KYCs
    """
    try:
        # Use update() return value to avoid extra query
        # update() returns the number of rows affected
        expired_count = KYCVerification.objects.filter(
            status=KYCStatus.APPROVED,
            expires_at__lte=timezone.now(),
        ).update(status=KYCStatus.EXPIRED)

        logger.info(
            f"KYC expiry check completed: {expired_count} KYCs marked as expired"
        )
        return {"status": "success", "expired_count": expired_count}

    except Exception as e:
        logger.error(f"KYC expiry check failed: {str(e)}")
        return {"status": "failed", "error": str(e)}


@shared_task(name="compliance.weekly_sanctions_rescan", queue="compliance")
def rescan_sanctions():
    """
    Weekly task to re-screen all active users against updated sanctions lists
    Runs every Sunday at 2 AM

    Optimized to avoid N+1 queries using prefetch_related
    """
    try:
        from apps.accounts.models import User
        from django.db.models import Prefetch

        # Fetch all active users with their latest approved KYC in a single query
        users_with_kyc = User.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                "kyc_verifications",
                queryset=KYCVerification.objects.filter(
                    status=KYCStatus.APPROVED
                ).order_by("-created_at"),
                to_attr="approved_kycs",
            )
        )

        count = 0
        for user in users_with_kyc:
            # Get the first (latest) approved KYC from prefetched data
            if hasattr(user, "approved_kycs") and user.approved_kycs:
                kyc = user.approved_kycs[0]

                # Trigger sanctions screening
                SanctionsTasks.screen_for_sanctions.delay(
                    user_id=str(user.id),
                    full_name=f"{kyc.first_name} {kyc.last_name}",
                    date_of_birth=kyc.date_of_birth.isoformat(),
                    nationality=kyc.nationality,
                )
                count += 1

        logger.info(f"Weekly sanctions rescan initiated for {count} users")
        return {"status": "success", "users_rescanned": count}

    except Exception as e:
        logger.error(f"Weekly sanctions rescan failed: {str(e)}")
        return {"status": "failed", "error": str(e)}


# ==================== KYC EMAIL TASKS ====================


class KYCEmailTasks:
    """Email tasks for KYC-related notifications"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="compliance.send_kyc_approved_email",
        queue="emails",
    )
    def send_kyc_approved_email(self, kyc_verification_id: str):
        """Send KYC approval notification email"""
        try:
            kyc_verification = KYCVerification.objects.select_related(
                "user"
            ).get_or_none(kyc_id=kyc_verification_id)

            if not kyc_verification:
                logger.error(f"KYC Verification {kyc_verification_id} not found")
                return {"status": "failed", "error": "KYC Verification not found"}

            KYCEmailUtil.send_kyc_approved_email(kyc_verification)
            logger.info(
                f"KYC approval email sent for user {kyc_verification.user.email}"
            )
            return {"status": "success", "reference": kyc_verification.reference_number}
        except Exception as exc:
            logger.error(f"KYC approval email failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="compliance.send_kyc_pending_email",
        queue="emails",
    )
    def send_kyc_pending_email(self, kyc_verification_id: str):
        """Send KYC pending review notification email"""
        try:
            kyc_verification = (
                KYCVerification.objects.select_related("user")
                .prefetch_related("documents")
                .get_or_none(kyc_id=kyc_verification_id)
            )

            if not kyc_verification:
                logger.error(f"KYC Verification {kyc_verification_id} not found")
                return {"status": "failed", "error": "KYC Verification not found"}

            KYCEmailUtil.send_kyc_pending_email(kyc_verification)
            logger.info(
                f"KYC pending email sent for user {kyc_verification.user.email}"
            )
            return {"status": "success", "reference": kyc_verification.reference_number}
        except Exception as exc:
            logger.error(f"KYC pending email failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="compliance.send_kyc_rejected_email",
        queue="emails",
    )
    def send_kyc_rejected_email(self, kyc_verification_id: str):
        """Send KYC rejection/action required notification email"""
        try:
            kyc_verification = KYCVerification.objects.select_related(
                "user"
            ).get_or_none(kyc_id=kyc_verification_id)

            if not kyc_verification:
                logger.error(f"KYC Verification {kyc_verification_id} not found")
                return {"status": "failed", "error": "KYC Verification not found"}

            KYCEmailUtil.send_kyc_rejected_email(kyc_verification)
            logger.info(
                f"KYC rejection email sent for user {kyc_verification.user.email}"
            )
            return {"status": "success", "reference": kyc_verification.reference_number}
        except Exception as exc:
            logger.error(f"KYC rejection email failed: {str(exc)}")
            raise self.retry(exc=exc)


# Expose email task functions for imports
send_kyc_approved_email_async = KYCEmailTasks.send_kyc_approved_email
send_kyc_pending_email_async = KYCEmailTasks.send_kyc_pending_email
send_kyc_rejected_email_async = KYCEmailTasks.send_kyc_rejected_email
