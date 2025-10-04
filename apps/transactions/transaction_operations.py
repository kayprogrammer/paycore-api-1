from decimal import Decimal
from typing import Optional, Dict, Any
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Q, Sum, Count, Avg
from uuid import UUID
from asgiref.sync import sync_to_async

from apps.accounts.models import User
from apps.common.paginators import CustomPagination
from apps.common.schemas import PaginationQuerySchema
from apps.transactions.models import (
    Transaction,
    TransactionStatus,
)
from apps.transactions.schemas import TransactionFilterSchema
from apps.transactions.services import TransactionService
from apps.wallets.models import Wallet, WalletStatus
from apps.common.exceptions import RequestError, ErrorCode, NotFoundError

paginator = CustomPagination()

class TransactionOperations:
    """High-level service for transaction operations"""

    @staticmethod
    async def initiate_transfer(
        user: User,
        from_wallet_id: UUID,
        to_wallet_id: UUID,
        amount: Decimal,
        description: Optional[str] = None,
        reference: Optional[str] = None,
        pin: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Initiate a wallet-to-wallet transfer"""

        # Get wallets
        from_wallet = await Wallet.objects.select_related("currency", "user").aget(
            wallet_id=from_wallet_id, user=user
        )

        to_wallet = await Wallet.objects.select_related("currency", "user").aget(
            wallet_id=to_wallet_id
        )

        # Validate transfer
        if from_wallet.currency_id != to_wallet.currency_id:
            raise RequestError(
                ErrorCode.INVALID_ENTRY,
                "Wallets must have the same currency",
                400,
            )

        if from_wallet.status != WalletStatus.ACTIVE:
            raise RequestError(
                ErrorCode.NOT_ALLOWED,
                "Source wallet is not active",
                400,
            )

        # Check balance
        can_spend, error_msg = from_wallet.can_spend(amount)
        if not can_spend:
            raise RequestError(ErrorCode.INVALID_ENTRY, error_msg, 400)

        # Calculate fee (example: 1% for external transfers)
        fee_amount = Decimal("0")
        if from_wallet.user_id != to_wallet.user_id:
            fee_amount = amount * Decimal("0.01")  # 1% fee

        total_amount = amount + fee_amount

        # Verify total can be spent
        can_spend_total, error_msg = from_wallet.can_spend(total_amount)
        if not can_spend_total:
            raise RequestError(ErrorCode.INVALID_ENTRY, error_msg, 400)

        # Perform transfer in atomic transaction
        @db_transaction.atomic
        async def execute_transfer():
            # Update balances
            from_balance_before = from_wallet.balance
            to_balance_before = to_wallet.balance

            from_wallet.balance -= total_amount
            from_wallet.available_balance -= total_amount
            from_wallet.daily_spent += total_amount
            from_wallet.monthly_spent += total_amount
            from_wallet.last_transaction_at = timezone.now()

            to_wallet.balance += amount
            to_wallet.available_balance += amount
            to_wallet.last_transaction_at = timezone.now()

            await from_wallet.asave()
            await to_wallet.asave()

            from_balance_after = from_wallet.balance
            to_balance_after = to_wallet.balance

            # Create transaction record
            transaction = await TransactionService.create_wallet_transfer_transaction(
                from_user=from_wallet.user,
                to_user=to_wallet.user,
                from_wallet=from_wallet,
                to_wallet=to_wallet,
                amount=amount,
                from_balance_before=from_balance_before,
                from_balance_after=from_balance_after,
                to_balance_before=to_balance_before,
                to_balance_after=to_balance_after,
                description=description,
                reference=reference,
                fee_amount=fee_amount,
            )

            # Add fee if applicable
            if fee_amount > 0:
                await TransactionService.add_transaction_fee(
                    transaction=transaction,
                    fee_type="transfer",
                    amount=fee_amount,
                    percentage=Decimal("1.0"),
                    description="Transfer fee",
                )

            # Complete transaction
            await TransactionService.complete_transaction(
                transaction=transaction,
                changed_by=user,
                reason="Transfer completed successfully",
            )

            return transaction

        transaction = await sync_to_async(execute_transfer)()

        return {
            "transaction_id": transaction.transaction_id,
            "amount": amount,
            "fee_amount": fee_amount,
            "total_amount": total_amount,
            "status": transaction.status,
            "from_wallet": from_wallet.name,
            "to_wallet": to_wallet.name,
            "timestamp": transaction.completed_at,
        }

    @staticmethod
    async def get_transaction_detail(
        user: User, transaction_id: UUID
    ) -> Dict[str, Any]:
        transaction = await (
            Transaction.objects.select_related(
                "from_user",
                "to_user",
                "from_wallet",
                "to_wallet",
                "from_wallet__currency",
            )
            .prefetch_related("fees", "disputes")
            .aget_or_none(transaction_id=transaction_id)
        )

        if not transaction:
            raise NotFoundError("Transaction not found")

        if transaction.from_user_id != user.id and transaction.to_user_id != user.id:
            raise RequestError(
                ErrorCode.INVALID_OWNER,
                "You don't have access to this transaction",
                403,
            )

        transaction.fees = await sync_to_async(list)(transaction.fees.values("fee_type", "amount", "percentage", "description"))
        transaction.has_dispute = await transaction.disputes.aexists()
        transaction.can_dispute = (
            transaction.status == TransactionStatus.COMPLETED
            and not transaction.has_dispute
            and (timezone.now() - transaction.completed_at).days <= 30
        )

        transaction.can_reverse = (
            transaction.status == TransactionStatus.COMPLETED
            and transaction.from_user_id == user.id
            and (timezone.now() - transaction.completed_at).days <= 1
        )
        return transaction

    @staticmethod
    async def list_user_transactions(
        user: User,
        filters: TransactionFilterSchema,
        page_params: PaginationQuerySchema,
        wallet_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        wallet_id_filter = Q(from_wallet_id=wallet_id) | Q(to_wallet_id=wallet_id) if wallet_id else Q()
        transactions_q = Transaction.objects.filter(Q(from_user=user) | Q(to_user=user)).filter(wallet_id_filter).select_related(
            "from_user", "to_user", "from_wallet", "to_wallet", "from_wallet__currency"
        ).order_by("-created_at")

        filtered_transactions_q = filters.filter(transactions_q)
        paginated_data = await paginator.paginate_queryset(
            filtered_transactions_q, page_params.page, page_params.limit
        )
        return paginated_data

    @staticmethod
    async def get_transaction_stats(user: User) -> Dict[str, Any]:
        stats = await Transaction.objects.filter(
            Q(from_user=user) | Q(to_user=user)
        ).aaggregate(
            total_count=Count("id"),
            successful_count=Count("id", filter=Q(status=TransactionStatus.COMPLETED)),
            failed_count=Count(
                "id",
                filter=Q(
                    status__in=[
                        TransactionStatus.FAILED,
                        TransactionStatus.CANCELLED,
                    ]
                ),
            ),
            pending_count=Count(
                "id",
                filter=Q(
                    status__in=[
                        TransactionStatus.PENDING,
                        TransactionStatus.PROCESSING,
                    ]
                ),
            ),
            total_sent=Sum("amount", filter=Q(from_user=user)),
            total_received=Sum("amount", filter=Q(to_user=user)),
            total_fees=Sum("fee_amount", filter=Q(from_user=user)),
            avg_amount=Avg("amount"),
        )

        return {
            "total_transactions": stats["total_count"] or 0,
            "total_sent": stats["total_sent"] or Decimal("0"),
            "total_received": stats["total_received"] or Decimal("0"),
            "total_fees": stats["total_fees"] or Decimal("0"),
            "successful_count": stats["successful_count"] or 0,
            "failed_count": stats["failed_count"] or 0,
            "pending_count": stats["pending_count"] or 0,
            "average_transaction_amount": stats["avg_amount"] or Decimal("0"),
        }
