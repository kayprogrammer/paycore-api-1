from django.contrib.auth import get_user_model
from decimal import Decimal
from typing import Optional
import logging

from apps.notifications.tasks import NotificationTasks
from apps.notifications.models import NotificationPriority, NotificationType

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationTriggers:
    """
    Centralized notification triggers for all app events
    All methods call Celery tasks to send notifications asynchronously

    Usage:
        from apps.notifications.triggers import NotificationTriggers

        # In your payment view/service:
        NotificationTriggers.payment_received(user, amount, currency)

        # In your loan view/service:
        NotificationTriggers.loan_approved(user, loan)
    """

    # ============= Payment Notifications =============

    @staticmethod
    def payment_received(
        user: User, amount: Decimal, currency: str, reference: str = None
    ):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Payment Received",
            message=f"You have received {currency} {amount:,.2f}",
            notification_type=NotificationType.PAYMENT,
            priority=NotificationPriority.MEDIUM,
            related_object_type="Payment",
            related_object_id=reference,
            action_url=f"/payments/{reference}" if reference else "/payments",
        )

    @staticmethod
    def payment_sent(
        user: User,
        amount: Decimal,
        currency: str,
        recipient: str,
        reference: str = None,
    ):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Payment Sent",
            message=f"You sent {currency} {amount:,.2f} to {recipient}",
            notification_type=NotificationType.PAYMENT,
            priority=NotificationPriority.MEDIUM,
            related_object_type="Payment",
            related_object_id=reference,
            action_url=f"/payments/{reference}" if reference else "/payments",
        )

    @staticmethod
    def payment_failed(user: User, amount: Decimal, currency: str, reason: str = None):
        message = f"Your payment of {currency} {amount:,.2f} failed"
        if reason:
            message += f": {reason}"

        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Payment Failed",
            message=message,
            notification_type=NotificationType.PAYMENT,
            priority=NotificationPriority.HIGH,
        )

    # ============= Loan Notifications =============

    @staticmethod
    def loan_applied(user: User, loan_id: str, amount: Decimal, currency: str):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Loan Application Submitted",
            message=f"Your loan application for {currency} {amount:,.2f} has been received and is being reviewed",
            notification_type=NotificationType.LOAN,
            priority=NotificationPriority.MEDIUM,
            related_object_type="Loan",
            related_object_id=loan_id,
            action_url=f"/loans/{loan_id}",
        )

    @staticmethod
    def loan_approved(user: User, loan_id: str, amount: Decimal, currency: str):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Loan Approved",
            message=f"Congratulations! Your loan of {currency} {amount:,.2f} has been approved",
            notification_type=NotificationType.LOAN,
            priority=NotificationPriority.HIGH,
            related_object_type="Loan",
            related_object_id=loan_id,
            action_url=f"/loans/{loan_id}",
        )

    @staticmethod
    def loan_rejected(user: User, loan_id: str, reason: str = None):
        message = "Your loan application has been declined"
        if reason:
            message += f": {reason}"

        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Loan Declined",
            message=message,
            notification_type=NotificationType.LOAN,
            priority=NotificationPriority.MEDIUM,
            related_object_type="Loan",
            related_object_id=loan_id,
            action_url=f"/loans/{loan_id}",
        )

    @staticmethod
    def loan_payment_due(
        user: User, loan_id: str, amount: Decimal, currency: str, due_date: str
    ):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Loan Payment Due",
            message=f"Your loan payment of {currency} {amount:,.2f} is due on {due_date}",
            notification_type=NotificationType.LOAN,
            priority=NotificationPriority.HIGH,
            related_object_type="Loan",
            related_object_id=loan_id,
            action_url=f"/loans/{loan_id}",
        )

    # ============= Card Notifications =============

    @staticmethod
    def card_created(user: User, card_id: str, card_type: str, last4: str):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Card Created",
            message=f"Your {card_type} card ending in {last4} has been created successfully",
            notification_type=NotificationType.CARD,
            priority=NotificationPriority.MEDIUM,
            related_object_type="Card",
            related_object_id=card_id,
            action_url=f"/cards/{card_id}",
        )

    @staticmethod
    def card_transaction(
        user: User, card_id: str, amount: Decimal, currency: str, merchant: str
    ):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Card Transaction",
            message=f"Card transaction: {currency} {amount:,.2f} at {merchant}",
            notification_type=NotificationType.CARD,
            priority=NotificationPriority.MEDIUM,
            related_object_type="Card",
            related_object_id=card_id,
            action_url=f"/cards/{card_id}",
        )

    @staticmethod
    def card_blocked(user: User, card_id: str, reason: str = None):
        message = "Your card has been blocked"
        if reason:
            message += f": {reason}"

        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Card Blocked",
            message=message,
            notification_type=NotificationType.CARD,
            priority=NotificationPriority.URGENT,
            related_object_type="Card",
            related_object_id=card_id,
            action_url=f"/cards/{card_id}",
        )

    # ============= KYC/Compliance Notifications =============

    @staticmethod
    def kyc_submitted(user: User, kyc_id: str):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="KYC Verification Submitted",
            message="Your identity verification has been submitted and is being reviewed",
            notification_type=NotificationType.KYC,
            priority=NotificationPriority.MEDIUM,
            related_object_type="KYCVerification",
            related_object_id=kyc_id,
            action_url=f"/compliance/kyc/{kyc_id}",
        )

    @staticmethod
    def kyc_approved(user: User, kyc_id: str, tier: int):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Identity Verified",
            message=f"Your identity has been successfully verified (Tier {tier})",
            notification_type=NotificationType.KYC,
            priority=NotificationPriority.HIGH,
            related_object_type="KYCVerification",
            related_object_id=kyc_id,
            action_url=f"/compliance/kyc/{kyc_id}",
        )

    @staticmethod
    def kyc_rejected(user: User, kyc_id: str, reason: str = None):
        message = "Your identity verification was unsuccessful"
        if reason:
            message += f": {reason}"

        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Verification Failed",
            message=message,
            notification_type=NotificationType.KYC,
            priority=NotificationPriority.HIGH,
            related_object_type="KYCVerification",
            related_object_id=kyc_id,
            action_url=f"/compliance/kyc/{kyc_id}",
        )

    # ============= Bill Payment Notifications =============

    @staticmethod
    def bill_payment_successful(
        user: User, amount: Decimal, currency: str, biller: str, reference: str = None
    ):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Bill Payment Successful",
            message=f"Your {biller} bill payment of {currency} {amount:,.2f} was successful",
            notification_type=NotificationType.BILL,
            priority=NotificationPriority.MEDIUM,
            related_object_type="BillPayment",
            related_object_id=reference,
            action_url=f"/bills/{reference}" if reference else "/bills",
        )

    @staticmethod
    def bill_payment_failed(
        user: User, amount: Decimal, currency: str, biller: str, reason: str = None
    ):
        message = f"Your {biller} bill payment of {currency} {amount:,.2f} failed"
        if reason:
            message += f": {reason}"

        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Bill Payment Failed",
            message=message,
            notification_type=NotificationType.BILL,
            priority=NotificationPriority.HIGH,
        )

    # ============= Account/Security Notifications =============

    @staticmethod
    def account_login(user: User, device: str = None, location: str = None):
        message = "A new login to your account was detected"
        if device:
            message += f" from {device}"
        if location:
            message += f" in {location}"

        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="New Login Detected",
            message=message,
            notification_type=NotificationType.SECURITY,
            priority=NotificationPriority.MEDIUM,
        )

    @staticmethod
    def password_changed(user: User):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Password Changed",
            message="Your password has been changed successfully. If you did not make this change, contact support immediately.",
            notification_type=NotificationType.SECURITY,
            priority=NotificationPriority.URGENT,
        )

    @staticmethod
    def suspicious_activity(user: User, activity_type: str, details: str = None):
        message = f"Suspicious activity detected: {activity_type}"
        if details:
            message += f" - {details}"

        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Security Alert",
            message=message,
            notification_type=NotificationType.SECURITY,
            priority=NotificationPriority.URGENT,
        )

    # ============= System Notifications =============

    @staticmethod
    def system_maintenance(user: User, start_time: str, duration: str):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Scheduled Maintenance",
            message=f"System maintenance scheduled for {start_time} (Duration: {duration}). Some services may be unavailable.",
            notification_type=NotificationType.SYSTEM,
            priority=NotificationPriority.MEDIUM,
        )

    @staticmethod
    def welcome_message(user: User):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title="Welcome to PayCore!",
            message="Thank you for joining PayCore. Complete your profile and KYC verification to unlock all features.",
            notification_type=NotificationType.ACCOUNT,
            priority=NotificationPriority.MEDIUM,
            action_url="/profile/kyc",
        )

    # ============= Promotion Notifications =============

    @staticmethod
    def promotion_alert(user: User, title: str, message: str, action_url: str = None):
        NotificationTasks.send_notification.delay(
            user_id=user.id,
            title=title,
            message=message,
            notification_type=NotificationType.PROMOTION,
            priority=NotificationPriority.LOW,
            action_url=action_url,
        )
