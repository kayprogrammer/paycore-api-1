from decimal import Decimal
from typing import Optional, Dict, Any
from django.utils import timezone
from uuid import UUID
from django.db.models import Q

from apps.accounts.models import User
from apps.transactions.models import (
    Transaction,
    TransactionType,
    TransactionStatus,
    TransactionDirection,
    TransactionFee,
    TransactionHold,
    TransactionLog,
)
from asgiref.sync import sync_to_async

from apps.wallets.models import Wallet


class TransactionService:
    """Service for managing transaction creation and lifecycle"""

    @staticmethod
    async def create_transaction(
        transaction_type: TransactionType,
        amount: Decimal,
        direction: TransactionDirection,
        from_user: Optional[User] = None,
        to_user: Optional[User] = None,
        from_wallet: Optional[Wallet] = None,
        to_wallet: Optional[Wallet] = None,
        description: Optional[str] = None,
        reference: Optional[str] = None,
        external_reference: Optional[str] = None,
        fee_amount: Decimal = Decimal("0"),
        metadata: Optional[Dict[str, Any]] = None,
        from_balance_before: Optional[Decimal] = None,
        from_balance_after: Optional[Decimal] = None,
        to_balance_before: Optional[Decimal] = None,
        to_balance_after: Optional[Decimal] = None,
        **kwargs,
    ) -> Transaction:
        net_amount = amount - fee_amount

        transaction_data = {
            "transaction_type": transaction_type,
            "status": TransactionStatus.PENDING,
            "direction": direction,
            "amount": amount,
            "fee_amount": fee_amount,
            "net_amount": net_amount,
            "from_user": from_user,
            "to_user": to_user,
            "from_wallet": from_wallet,
            "to_wallet": to_wallet,
            "description": description,
            "reference": reference,
            "external_reference": external_reference,
            "from_balance_before": from_balance_before,
            "from_balance_after": from_balance_after,
            "to_balance_before": to_balance_before,
            "to_balance_after": to_balance_after,
            "metadata": metadata or {},
            "initiated_at": timezone.now(),
        }

        # Add any additional kwargs
        transaction_data.update(kwargs)

        transaction = await Transaction.objects.acreate(**transaction_data)

        # Create initial transaction log
        await TransactionLog.objects.acreate(
            transaction=transaction,
            previous_status=None,
            new_status=TransactionStatus.PENDING,
            reason="Transaction initiated",
        )

        return transaction

    @staticmethod
    async def create_wallet_transfer_transaction(
        from_user: User,
        to_user: User,
        from_wallet: Wallet,
        to_wallet: Wallet,
        amount: Decimal,
        from_balance_before: Decimal,
        from_balance_after: Decimal,
        to_balance_before: Decimal,
        to_balance_after: Decimal,
        description: Optional[str] = None,
        reference: Optional[str] = None,
        fee_amount: Decimal = Decimal("0"),
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Transaction:
        return await TransactionService.create_transaction(
            transaction_type=TransactionType.TRANSFER,
            amount=amount,
            direction=(
                TransactionDirection.OUTBOUND
                if from_user != to_user
                else TransactionDirection.INTERNAL
            ),
            from_user=from_user,
            to_user=to_user,
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            description=description or "Wallet transfer",
            reference=reference,
            fee_amount=fee_amount,
            metadata=metadata,
            from_balance_before=from_balance_before,
            from_balance_after=from_balance_after,
            to_balance_before=to_balance_before,
            to_balance_after=to_balance_after,
        )

    @staticmethod
    async def create_hold_transaction(
        user: User,
        wallet: Wallet,  # Can be UUID or Wallet object
        amount: Decimal,
        balance_before: Decimal,
        balance_after: Decimal,
        reference: Optional[str] = None,
        expires_at: Optional[timezone.datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Transaction:
        transaction = await TransactionService.create_transaction(
            transaction_type=TransactionType.HOLD,
            amount=amount,
            direction=TransactionDirection.INTERNAL,
            from_user=user,
            from_wallet=wallet,
            description="Funds hold",
            reference=reference,
            metadata=metadata,
            from_balance_before=balance_before,
            from_balance_after=balance_after,
        )

        # Create transaction hold record
        await TransactionHold.objects.acreate(
            transaction=transaction,
            wallet=wallet,
            amount_held=amount,
            expires_at=expires_at,
        )

        return transaction

    @staticmethod
    async def create_release_transaction(
        user: User,
        wallet: Wallet,
        amount: Decimal,
        balance_before: Decimal,
        balance_after: Decimal,
        reference: Optional[str] = None,
        hold_transaction: Optional[Transaction] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Transaction:
        return await TransactionService.create_transaction(
            transaction_type=TransactionType.RELEASE,
            amount=amount,
            direction=TransactionDirection.INTERNAL,
            from_user=user,
            from_wallet=wallet,
            description="Funds release",
            reference=reference,
            metadata=metadata,
            from_balance_before=balance_before,
            from_balance_after=balance_after,
        )

    @staticmethod
    async def complete_transaction(
        transaction: Transaction,
        changed_by: Optional[User] = None,
        reason: Optional[str] = None,
    ) -> Transaction:
        previous_status = transaction.status
        transaction.complete_transaction()
        await transaction.asave()

        await TransactionLog.objects.acreate(
            transaction=transaction,
            previous_status=previous_status,
            new_status=transaction.status,
            changed_by=changed_by,
            reason=reason or "Transaction completed successfully",
        )
        return transaction

    @staticmethod
    async def fail_transaction(
        transaction: Transaction, reason: str, changed_by: Optional[User] = None
    ) -> Transaction:
        previous_status = transaction.status
        transaction.fail_transaction(reason)
        await transaction.asave()

        # Log the status change
        await TransactionLog.objects.acreate(
            transaction=transaction,
            previous_status=previous_status,
            new_status=transaction.status,
            changed_by=changed_by,
            reason=reason,
        )

        return transaction

    @staticmethod
    async def add_transaction_fee(
        transaction: Transaction,
        fee_type: str,
        amount: Decimal,
        percentage: Optional[Decimal] = None,
        description: Optional[str] = None,
    ) -> TransactionFee:
        return await TransactionFee.objects.acreate(
            transaction=transaction,
            fee_type=fee_type,
            amount=amount,
            percentage=percentage,
            description=description,
        )

    @staticmethod
    async def update_transaction_status(
        transaction: Transaction,
        new_status: TransactionStatus,
        changed_by: Optional[User] = None,
        reason: Optional[str] = None,
    ) -> Transaction:
        previous_status = transaction.status
        transaction.status = new_status

        if new_status == TransactionStatus.PROCESSING and not transaction.processed_at:
            transaction.processed_at = timezone.now()
        elif new_status == TransactionStatus.COMPLETED and not transaction.completed_at:
            transaction.completed_at = timezone.now()
            if not transaction.processed_at:
                transaction.processed_at = timezone.now()
        elif new_status == TransactionStatus.FAILED and not transaction.failed_at:
            transaction.failed_at = timezone.now()

        await transaction.asave()

        await TransactionLog.objects.acreate(
            transaction=transaction,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason or f"Status changed to {new_status}",
        )
        return transaction
