from decimal import Decimal
from typing import Optional, Dict, Any
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from uuid import UUID

from apps.accounts.auth import Authentication
from apps.accounts.models import User
from apps.common.paginators import Paginator
from apps.common.schemas import PaginationQuerySchema
from apps.transactions.models import (
    Transaction,
    TransactionStatus,
)
from apps.transactions.schemas import TransactionFilterSchema
from apps.transactions.services.transaction_service import TransactionService
from apps.wallets.models import Wallet, WalletStatus
from apps.common.exceptions import (
    RequestError,
    ErrorCode,
    NotFoundError,
    BodyValidationError,
)
from apps.common.decorators import aatomic
from django.contrib.auth.hashers import check_password


class TransactionOperations:
    """High-level service for transaction operations"""

    @staticmethod
    @aatomic
    async def initiate_transfer(
        user: User,
        from_wallet_id: UUID,
        to_wallet_id: UUID,
        amount: Decimal,
        description: Optional[str] = None,
        reference: Optional[str] = None,
        pin: Optional[str] = None,
        biometric_token: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from_wallet = await Wallet.objects.select_related(
            "currency", "user"
        ).aget_or_none(wallet_id=from_wallet_id, user=user)
        if not from_wallet:
            raise BodyValidationError("from_wallet_id", "Source wallet not found")

        to_wallet = await Wallet.objects.select_related(
            "currency", "user"
        ).aget_or_none(wallet_id=to_wallet_id)
        if not to_wallet:
            raise BodyValidationError("to_wallet_id", "Destination wallet not found")

        if from_wallet.status != WalletStatus.ACTIVE:
            raise BodyValidationError("from_wallet_id", "Source wallet is not active")

        if to_wallet.status != WalletStatus.ACTIVE:
            raise BodyValidationError(
                "to_wallet_id", "Destination wallet is not active"
            )

        # Verify PIN if wallet requires it or if PIN is provided
        if from_wallet.requires_pin or pin:
            if not pin:
                raise BodyValidationError("pin", "PIN is required for this wallet")

            if not from_wallet.pin_hash or not check_password(
                pin, from_wallet.pin_hash
            ):
                raise BodyValidationError("pin", "Invalid PIN")

        # Verify biometric if wallet requires it or if token is provided
        if from_wallet.requires_biometric or biometric_token:
            if not biometric_token or not device_id:
                raise BodyValidationError(
                    "biometric_token",
                    "Biometric authentication required for this wallet",
                )

            # Validate biometric token
            auth_user, _ = await Authentication.validate_trust_token(
                user.email, biometric_token, device_id
            )

            if not auth_user or auth_user.id != user.id:
                raise BodyValidationError(
                    "biometric_token", "Invalid biometric authentication"
                )

        converted_amount = amount
        metadata = {
            "transfer_type": "wallet_to_wallet",
            "from_currency": from_wallet.currency.code,
            "to_currency": to_wallet.currency.code,
            "original_amount": str(amount),
        }

        if from_wallet.currency_id != to_wallet.currency_id:
            # Convert amount via USD
            amount_in_usd = amount * from_wallet.currency.exchange_rate_usd
            converted_amount = amount_in_usd / to_wallet.currency.exchange_rate_usd
            converted_amount = Decimal(
                str(round(float(converted_amount), to_wallet.currency.decimal_places))
            )

            metadata.update(
                {
                    "converted_amount": str(converted_amount),
                    "exchange_rate_applied": str(converted_amount / amount),
                    "from_usd_rate": str(from_wallet.currency.exchange_rate_usd),
                    "to_usd_rate": str(to_wallet.currency.exchange_rate_usd),
                }
            )

        # FEE CALCULATION
        fee_amount = Decimal("0")
        fee_details = []

        # Apply transfer fee for external transfers (1%)
        if from_wallet.user_id != to_wallet.user_id:
            transfer_fee = amount * Decimal("0.01")
            fee_amount += transfer_fee
            fee_details.append(
                {
                    "type": "transfer",
                    "amount": transfer_fee,
                    "percentage": Decimal("1.0"),
                    "description": "External transfer fee",
                }
            )

        # Apply currency conversion fee if applicable (0.5%)
        if from_wallet.currency_id != to_wallet.currency_id:
            conversion_fee = amount * Decimal("0.005")
            fee_amount += conversion_fee
            fee_details.append(
                {
                    "type": "currency_conversion",
                    "amount": conversion_fee,
                    "percentage": Decimal("0.5"),
                    "description": "Currency conversion fee",
                }
            )

        total_amount = amount + fee_amount

        # BALANCE VALIDATION
        can_spend, error_msg = from_wallet.can_spend(total_amount)
        if not can_spend:
            raise RequestError(ErrorCode.INVALID_ENTRY, error_msg, 400)

        # UPDATE BALANCES (ATOMIC)
        from_balance_before = from_wallet.balance
        to_balance_before = to_wallet.balance

        # Debit from source wallet
        from_wallet.balance -= total_amount
        from_wallet.available_balance -= total_amount
        from_wallet.daily_spent += total_amount
        from_wallet.monthly_spent += total_amount
        from_wallet.last_transaction_at = timezone.now()

        # Credit to destination wallet (with converted amount)
        to_wallet.balance += converted_amount
        to_wallet.available_balance += converted_amount
        to_wallet.last_transaction_at = timezone.now()

        # Save both wallets
        await from_wallet.asave()
        await to_wallet.asave()

        from_balance_after = from_wallet.balance
        to_balance_after = to_wallet.balance

        # CREATE TRANSACTION RECORD
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
            metadata=metadata,
        )

        # ADD FEE RECORDS
        for fee_detail in fee_details:
            await TransactionService.add_transaction_fee(
                transaction=transaction,
                fee_type=fee_detail["type"],
                amount=fee_detail["amount"],
                percentage=fee_detail["percentage"],
                description=fee_detail["description"],
            )

        # COMPLETE TRANSACTION
        await TransactionService.complete_transaction(
            transaction=transaction,
            changed_by=user,
            reason="Transfer completed successfully",
        )

        return {
            "transaction_id": transaction.transaction_id,
            "transaction_type": transaction.transaction_type,
            "currency_code": from_wallet.currency.code,
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
        wallet_id_filter = (
            Q(from_wallet_id=wallet_id) | Q(to_wallet_id=wallet_id)
            if wallet_id
            else Q()
        )
        transactions_q = (
            Transaction.objects.filter(Q(from_user=user) | Q(to_user=user))
            .filter(wallet_id_filter)
            .select_related(
                "from_user",
                "to_user",
                "from_wallet",
                "to_wallet",
                "from_wallet__currency",
            )
            .order_by("-created_at")
        )

        filtered_transactions_q = filters.filter(transactions_q)
        paginated_data = await Paginator.paginate_queryset(
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
