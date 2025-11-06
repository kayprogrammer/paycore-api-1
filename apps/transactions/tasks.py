import logging
from celery import shared_task
from asgiref.sync import async_to_sync

from apps.transactions.models import Transaction, TransactionStatus
from apps.transactions.services.deposit_manager import DepositManager

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
                logger.error(f"Transaction {transaction_id} not found for auto-confirmation")
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
