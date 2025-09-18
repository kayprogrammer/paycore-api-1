"""
Clean Celery tasks for accounts app
"""

import logging
from celery import shared_task
from apps.accounts.models import User
from apps.accounts.emails import EmailUtil
from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailTasks:
    """Clean class-based email tasks"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="accounts.send_otp_email",
        queue="emails",
    )
    def send_otp_email(self, user_id: int, email_type: str):
        try:
            user = User.objects.get_or_none(id=user_id, is_active=True)
            if not user:
                logger.error(f"User {user_id} not found")
                return {"status": "failed", "error": "User not found"}

            # Run the async function properly
            EmailUtil.send_otp(user, email_type)
            logger.info(f"Email sent: {email_type} to user {user_id}")
            return {"status": "success", "user_id": user_id}
        except Exception as exc:
            logger.error(f"Email failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(name="accounts.send_welcome_email", queue="emails")
    def send_welcome_email(user_id: int):
        try:
            user = User.objects.get_or_none(id=user_id, is_active=True)
            EmailUtil.welcome_email(user)
            logger.info(f"Welcome email sent to user {user_id}")
            return {"status": "success"}
        except Exception as exc:
            logger.error(f"Welcome email failed: {str(exc)}")
            return {"status": "failed", "error": str(exc)}

    @staticmethod
    @shared_task(name="accounts.send_password_reset_confirmation", queue="emails")
    def send_password_reset_confirmation(user_id: int):
        try:
            user = User.objects.get_or_none(id=user_id, is_active=True)
            EmailUtil.password_reset_confirmation(user)
            logger.info(f"Password reset confirmation sent to user {user_id}")
            return {"status": "success"}
        except Exception as exc:
            logger.error(f"Password reset confirmation failed: {str(exc)}")
            return {"status": "failed", "error": str(exc)}


class MaintenanceTasks:
    """System maintenance tasks"""

    @staticmethod
    @shared_task(name="accounts.cleanup_expired_otps", queue="maintenance")
    def cleanup_expired_otps():
        updated_count = User.objects.filter(otp_expires_at__lt=timezone.now()).update(
            otp_code=None, otp_expires_at=None
        )

        logger.info(f"Cleaned up {updated_count} expired OTPs")
        return {"status": "success", "cleaned_count": updated_count}


# Expose task functions for imports
send_otp_email_async = EmailTasks.send_otp_email
send_welcome_email_async = EmailTasks.send_welcome_email
send_password_reset_confirmation_async = EmailTasks.send_password_reset_confirmation
