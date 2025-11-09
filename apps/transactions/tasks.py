import logging
from celery import shared_task
from asgiref.sync import async_to_sync

from apps.transactions.models import Transaction, TransactionStatus
from apps.transactions.services.deposit_manager import DepositManager
from apps.transactions.emails import TransferEmailUtil
from apps.notifications.tasks import NotificationTasks

logger = logging.getLogger(__name__)


# ==================== DEPOSIT TASKS ====================


class DepositTasks:
    """Background tasks for deposit processing"""

    @staticmethod
    @shared_task(
        bind=True,
        name="transactions.auto_confirm_deposit",
        queue="payments",
    )
    def auto_confirm_deposit(self, transaction_id: str):
        """
        Auto-confirm deposit after 15 seconds for internal provider
        This simulates payment processing time for demo/testing purposes
        """
        try:
            # Get transaction to check status
            transaction = Transaction.objects.select_related(
                "to_wallet__currency", "to_user"
            ).get_or_none(transaction_id=transaction_id)

            if not transaction:
                logger.error(
                    f"Transaction {transaction_id} not found for auto-confirmation"
                )
                return {"status": "failed", "error": "Transaction not found"}

            if transaction.status != TransactionStatus.PENDING:
                logger.warning(
                    f"Transaction {transaction_id} is not in pending status, "
                    f"skipping auto-confirmation. Current status: {transaction.status}"
                )
                return {"status": "skipped", "current_status": transaction.status}

            # Use DepositManager to verify and complete the deposit
            completed_transaction = async_to_sync(
                DepositManager.verify_and_complete_deposit
            )(transaction_id=transaction_id)
            print("COMPLETED_TR: ", completed_transaction)
            logger.info(
                f"Deposit {transaction_id} auto-confirmed successfully. "
                f"Amount: {completed_transaction.amount}, "
                f"Status: {completed_transaction.status}"
            )

            # Send WebSocket notification to user
            if completed_transaction.status == TransactionStatus.COMPLETED:
                NotificationTasks.send_notification.delay(
                    user_id=completed_transaction.to_user.id,
                    title="Deposit Confirmed",
                    message=f"Your deposit of {completed_transaction.to_wallet.currency.symbol}{completed_transaction.amount:,.2f} has been confirmed successfully.",
                    notification_type="transaction",
                    priority="high",
                    related_object_type="transaction",
                    related_object_id=str(completed_transaction.transaction_id),
                    action_url="/transactions",
                    send_push=False,
                    send_realtime=True,
                )
                logger.info(
                    f"Deposit confirmation notification sent to user {completed_transaction.to_user.id}"
                )

            return {
                "status": "success",
                "transaction_id": transaction_id,
                "amount": float(completed_transaction.amount),
                "completed_at": (
                    completed_transaction.completed_at.isoformat()
                    if completed_transaction.completed_at
                    else None
                ),
            }

        except Exception as exc:
            logger.error(
                f"Auto-confirm deposit task failed for {transaction_id}: {str(exc)}"
            )
            return {"status": "failed", "error": str(exc)}


# ==================== WITHDRAWAL TASKS ====================


class WithdrawalTasks:
    """Background tasks for withdrawal processing"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="transactions.process_withdrawal",
        queue="payments",
    )
    def process_withdrawal(self, transaction_id: str):
        """
        Process withdrawal transaction
        This task is triggered when a user initiates a withdrawal
        """
        try:
            transaction = Transaction.objects.select_related(
                "from_wallet__currency", "from_user"
            ).get_or_none(transaction_id=transaction_id)

            if not transaction:
                logger.error(f"Transaction {transaction_id} not found")
                return {"status": "failed", "error": "Transaction not found"}

            logger.info(
                f"Withdrawal {transaction_id} processed successfully for user {transaction.from_user.email}"
            )
            return {
                "status": "success",
                "transaction_id": transaction_id,
                "amount": float(transaction.amount),
            }

        except Exception as exc:
            logger.error(
                f"Withdrawal processing task failed for {transaction_id}: {str(exc)}"
            )
            raise self.retry(exc=exc)


# ==================== TRANSFER EMAIL TASKS ====================


class TransferEmailTasks:
    """Email tasks for transfer-related notifications"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="transactions.send_transfer_success_email",
        queue="emails",
    )
    def send_transfer_success_email(self, transaction_id: str):
        """Send transfer confirmation email"""
        try:
            transaction = Transaction.objects.select_related(
                "from_user",
                "to_user",
                "from_wallet",
                "from_wallet__currency",
                "to_wallet",
            ).get_or_none(transaction_id=transaction_id)

            if not transaction:
                logger.error(f"Transaction {transaction_id} not found")
                return {"status": "failed", "error": "Transaction not found"}

            TransferEmailUtil.send_transfer_success_email(transaction)
            logger.info(
                f"Transfer email sent for transaction {transaction.transaction_id}"
            )
            return {
                "status": "success",
                "transaction_id": str(transaction.transaction_id),
            }
        except Exception as exc:
            logger.error(f"Transfer email failed: {str(exc)}")
            raise self.retry(exc=exc)


# Expose email task functions for imports
send_transfer_success_email_async = TransferEmailTasks.send_transfer_success_email
