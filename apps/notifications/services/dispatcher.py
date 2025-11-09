"""
Unified Notification Dispatcher
Centralized service for sending notifications across multiple channels (in-app, push, email)
"""

from typing import Dict, Any, List, Optional, Union
from enum import Enum
from django.contrib.auth import get_user_model
import logging, importlib

from apps.notifications.models import NotificationType, NotificationPriority
from apps.notifications.services.base import NotificationService
from apps.notifications.services.fcm import FCMService

logger = logging.getLogger(__name__)

User = get_user_model()


class NotificationChannel(str, Enum):
    """Notification delivery channels"""

    IN_APP = "in_app"
    PUSH = "push"
    EMAIL = "email"


class NotificationEventType(str, Enum):
    """Notification event types for routing"""

    # KYC Events
    KYC_APPROVED = "kyc_approved"
    KYC_PENDING = "kyc_pending"
    KYC_REJECTED = "kyc_rejected"

    # Loan Events
    LOAN_APPROVED = "loan_approved"
    LOAN_DISBURSED = "loan_disbursed"
    LOAN_REPAYMENT = "loan_repayment"

    # Investment Events
    INVESTMENT_CREATED = "investment_created"
    INVESTMENT_MATURED = "investment_matured"

    # Card Events
    CARD_ISSUED = "card_issued"

    # Wallet Events
    WALLET_CREATED = "wallet_created"

    # Bill Payment Events
    BILL_PAYMENT_SUCCESS = "bill_payment_success"

    # Transfer Events
    TRANSFER_SUCCESS = "transfer_success"

    # Payment Events
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_RECEIVED = "payment_received"


# Email task routing map
EMAIL_TASK_ROUTER = {
    # KYC
    NotificationEventType.KYC_APPROVED: {
        "task": "apps.compliance.tasks.KYCEmailTasks.send_kyc_approved_email",
        "id_field": "kyc_id",
    },
    NotificationEventType.KYC_PENDING: {
        "task": "apps.compliance.tasks.KYCEmailTasks.send_kyc_pending_email",
        "id_field": "kyc_id",
    },
    NotificationEventType.KYC_REJECTED: {
        "task": "apps.compliance.tasks.KYCEmailTasks.send_kyc_rejected_email",
        "id_field": "kyc_id",
    },
    # Loans
    NotificationEventType.LOAN_APPROVED: {
        "task": "apps.loans.tasks.LoanEmailTasks.send_loan_approved_email",
        "id_field": "loan_id",
    },
    NotificationEventType.LOAN_DISBURSED: {
        "task": "apps.loans.tasks.LoanEmailTasks.send_loan_disbursed_email",
        "id_field": "loan_id",
    },
    NotificationEventType.LOAN_REPAYMENT: {
        "task": "apps.loans.tasks.LoanEmailTasks.send_loan_repayment_email",
        "id_field": "repayment_id",
    },
    # Investments
    NotificationEventType.INVESTMENT_CREATED: {
        "task": "apps.investments.tasks.InvestmentEmailTasks.send_investment_created_email",
        "id_field": "investment_id",
    },
    NotificationEventType.INVESTMENT_MATURED: {
        "task": "apps.investments.tasks.InvestmentEmailTasks.send_investment_matured_email",
        "id_field": "investment_id",
    },
    # Cards
    NotificationEventType.CARD_ISSUED: {
        "task": "apps.cards.tasks.CardEmailTasks.send_card_issued_email",
        "id_field": "card_id",
    },
    # Wallets
    NotificationEventType.WALLET_CREATED: {
        "task": "apps.wallets.tasks.WalletEmailTasks.send_wallet_created_email",
        "id_field": "wallet_id",
    },
    # Bills
    NotificationEventType.BILL_PAYMENT_SUCCESS: {
        "task": "apps.bills.tasks.BillPaymentEmailTasks.send_bill_payment_success_email",
        "id_field": "bill_payment_id",
    },
    # Transfers
    NotificationEventType.TRANSFER_SUCCESS: {
        "task": "apps.transactions.tasks.TransferEmailTasks.send_transfer_success_email",
        "id_field": "transaction_id",
    },
    # Payments
    NotificationEventType.PAYMENT_SUCCESS: {
        "task": "apps.payments.tasks.PaymentEmailTasks.send_payment_confirmation_email",
        "id_field": "payment_id",
    },
    NotificationEventType.PAYMENT_RECEIVED: {
        "task": "apps.payments.tasks.PaymentEmailTasks.send_payment_received_email",
        "id_field": "payment_id",
    },
}


# Notification type mapping
EVENT_TO_NOTIFICATION_TYPE = {
    NotificationEventType.KYC_APPROVED: NotificationType.KYC,
    NotificationEventType.KYC_PENDING: NotificationType.KYC,
    NotificationEventType.KYC_REJECTED: NotificationType.KYC,
    NotificationEventType.LOAN_APPROVED: NotificationType.LOAN,
    NotificationEventType.LOAN_DISBURSED: NotificationType.LOAN,
    NotificationEventType.LOAN_REPAYMENT: NotificationType.LOAN,
    NotificationEventType.INVESTMENT_CREATED: NotificationType.INVESTMENT,
    NotificationEventType.INVESTMENT_MATURED: NotificationType.INVESTMENT,
    NotificationEventType.CARD_ISSUED: NotificationType.CARD,
    NotificationEventType.WALLET_CREATED: NotificationType.WALLET,
    NotificationEventType.BILL_PAYMENT_SUCCESS: NotificationType.BILL,
    NotificationEventType.TRANSFER_SUCCESS: NotificationType.TRANSFER,
    NotificationEventType.PAYMENT_SUCCESS: NotificationType.PAYMENT,
    NotificationEventType.PAYMENT_RECEIVED: NotificationType.PAYMENT,
}


class UnifiedNotificationDispatcher:
    """
    Unified dispatcher for sending notifications across multiple channels
    Handles routing to appropriate email tasks, in-app notifications, and push notifications
    """

    @staticmethod
    def dispatch(
        user: User,
        event_type: Union[NotificationEventType, str],
        channels: List[Union[NotificationChannel, str]],
        title: str,
        message: str,
        context_data: Dict[str, Any],
        priority: str = NotificationPriority.MEDIUM,
        related_object_type: Optional[str] = None,
        related_object_id: Optional[str] = None,
        action_url: Optional[str] = None,
        action_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Dispatch notification across specified channels
        """
        # Convert string enums to proper types
        if isinstance(event_type, str):
            try:
                event_type = NotificationEventType(event_type)
            except ValueError:
                logger.warning(f"Invalid event type: {event_type}")

        channels = [
            NotificationChannel(ch) if isinstance(ch, str) else ch for ch in channels
        ]

        results = {
            "success": True,
            "channels_attempted": [ch.value for ch in channels],
            "channels_sent": [],
            "errors": [],
        }

        # Get notification type from event
        notification_type = EVENT_TO_NOTIFICATION_TYPE.get(
            event_type, NotificationType.OTHER
        )

        try:
            # Handle IN_APP channel
            if NotificationChannel.IN_APP in channels:
                if user.in_app_enabled:
                    notification = NotificationService.create_notification(
                        user=user,
                        title=title,
                        message=message,
                        notification_type=notification_type,
                        priority=priority,
                        related_object_type=related_object_type,
                        related_object_id=related_object_id,
                        action_url=action_url,
                        action_data=action_data,
                        metadata=metadata,
                        send_push=NotificationChannel.PUSH in channels,
                        send_realtime=True,
                    )

                    if notification:
                        results["channels_sent"].append(
                            NotificationChannel.IN_APP.value
                        )
                        if NotificationChannel.PUSH in channels and user.push_enabled:
                            results["channels_sent"].append(
                                NotificationChannel.PUSH.value
                            )
                else:
                    logger.info(f"In-app notifications disabled for user {user.id}")

            # Handle PUSH channel (if not already handled by in_app)
            elif (
                NotificationChannel.PUSH in channels
                and NotificationChannel.IN_APP not in channels
            ):
                if user.push_enabled:
                    FCMService.send_to_user(
                        user,
                        title,
                        message,
                        {
                            "notification_type": notification_type,
                            "action_url": action_url or "",
                            **(action_data or {}),
                        },
                    )
                    results["channels_sent"].append(NotificationChannel.PUSH.value)
                else:
                    logger.info(f"Push notifications disabled for user {user.id}")

            # Handle EMAIL channel
            if NotificationChannel.EMAIL in channels:
                if user.email_enabled:
                    email_result = UnifiedNotificationDispatcher._dispatch_email(
                        event_type=event_type,
                        context_data=context_data,
                    )

                    if email_result["success"]:
                        results["channels_sent"].append(NotificationChannel.EMAIL.value)
                    else:
                        results["errors"].append(
                            f"Email: {email_result.get('error', 'Unknown error')}"
                        )
                else:
                    logger.info(f"Email notifications disabled for user {user.id}")

        except Exception as e:
            logger.error(
                f"Error in unified notification dispatch: {str(e)}", exc_info=True
            )
            results["success"] = False
            results["errors"].append(str(e))

        return results

    @staticmethod
    def _dispatch_email(
        event_type: NotificationEventType,
        context_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Route email to appropriate task based on event type

        Args:
            event_type: Type of notification event
            context_data: Context data containing required IDs
        """
        try:
            # Get routing config for this event
            routing_config = EMAIL_TASK_ROUTER.get(event_type)
            if not routing_config:
                logger.warning(f"No email task routing configured for {event_type}")
                return {"success": False, "error": "No email routing configured"}

            # Get the ID field name and value
            id_field = routing_config["id_field"]
            object_id = context_data.get(id_field)

            if not object_id:
                logger.error(
                    f"Missing required field '{id_field}' in context_data for {event_type}"
                )
                return {"success": False, "error": f"Missing {id_field}"}

            # Dynamically import and call the task
            task_path = routing_config["task"]
            # Split into: module.TaskClass.method_name
            # e.g., "apps.wallets.tasks.WalletEmailTasks.send_wallet_created_email"
            parts = task_path.split(".")
            method_name = parts[-1]  # Last part is the method name
            task_class = parts[-2]  # Second to last is the class name
            module_path = ".".join(parts[:-2])  # Everything before is the module path

            # Import the module
            module = importlib.import_module(module_path)

            # Get the task class
            task_cls = getattr(module, task_class)

            # Get the method and call with delay
            task_method = getattr(task_cls, method_name)

            # Call the Celery task asynchronously
            task_method.delay(str(object_id))

            logger.info(f"Email task dispatched for {event_type}: {task_path}")
            return {"success": True}

        except Exception as e:
            logger.error(
                f"Error dispatching email for {event_type}: {str(e)}", exc_info=True
            )
            return {"success": False, "error": str(e)}

    @staticmethod
    def quick_notify(
        user: User,
        event_type: Union[NotificationEventType, str],
        title: str,
        message: str,
        object_id: str,
        channels: Optional[List[Union[NotificationChannel, str]]] = None,
        priority: str = NotificationPriority.MEDIUM,
        action_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Quick helper method for common notification scenarios
        Automatically maps object_id to the correct field based on event_type
        """
        if isinstance(event_type, str):
            event_type = NotificationEventType(event_type)
        if channels is None:
            channels = [NotificationChannel.IN_APP, NotificationChannel.EMAIL]

        routing_config = EMAIL_TASK_ROUTER.get(event_type)
        id_field = routing_config["id_field"] if routing_config else "object_id"
        context_data = {id_field: object_id}

        # Infer related object type from event
        related_object_type = None
        if "kyc" in event_type.value:
            related_object_type = "KYCVerification"
        elif "loan" in event_type.value:
            related_object_type = (
                "Loan" if "repayment" not in event_type.value else "LoanRepayment"
            )
        elif "investment" in event_type.value:
            related_object_type = "Investment"
        elif "card" in event_type.value:
            related_object_type = "Card"
        elif "wallet" in event_type.value:
            related_object_type = "Wallet"
        elif "bill" in event_type.value:
            related_object_type = "BillPayment"
        elif "transfer" in event_type.value:
            related_object_type = "Transaction"
        elif "payment" in event_type.value:
            related_object_type = "Payment"

        return UnifiedNotificationDispatcher.dispatch(
            user=user,
            event_type=event_type,
            channels=channels,
            title=title,
            message=message,
            context_data=context_data,
            priority=priority,
            related_object_type=related_object_type,
            related_object_id=str(object_id),
            action_url=action_url,
        )
