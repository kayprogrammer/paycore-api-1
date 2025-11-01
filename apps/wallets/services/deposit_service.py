from decimal import Decimal
from typing import Dict, Any, Optional
from django.utils import timezone
from datetime import datetime

from apps.wallets.models import Wallet, WalletStatus
from apps.transactions.models import Transaction, TransactionType, TransactionDirection
from apps.transactions.services.transaction_service import TransactionService
from apps.common.decorators import aatomic
from apps.common.exceptions import (
    RequestError,
    ErrorCode,
    NotFoundError,
    BodyValidationError,
)


class DepositService:
    """Service for processing deposits to wallet account numbers"""

    @staticmethod
    @aatomic
    async def process_account_deposit(
        account_number: str,
        amount: Decimal,
        sender_account_number: str,
        sender_account_name: str,
        sender_bank_name: str,
        external_reference: str,
        narration: str = None,
        transaction_date: Optional[datetime] = None,
        webhook_payload: Optional[dict] = None,
    ) -> Dict[str, Any]:
        wallet = await Wallet.objects.select_related("user", "currency").aget_or_none(
            account_number=account_number
        )
        if not wallet:
            raise NotFoundError(
                f"Wallet with account number {account_number} not found"
            )

        duplicate = await Transaction.objects.filter(
            external_reference=external_reference
        ).aexists()

        if duplicate:
            raise BodyValidationError(
                "external_reference", "This deposit has already been processed"
            )

        if wallet.status != WalletStatus.ACTIVE:
            raise RequestError(
                ErrorCode.NOT_ALLOWED,
                f"Wallet is {wallet.status}, cannot receive deposits",
            )

        fee_percentage = Decimal("0.015")  # 1.5%
        fee_charged = amount * fee_percentage
        amount_credited = amount - fee_charged

        balance_before = wallet.balance
        wallet.balance += amount_credited
        wallet.available_balance += amount_credited
        wallet.last_transaction_at = timezone.now()
        await wallet.asave()

        balance_after = wallet.balance

        if not transaction_date:
            transaction_date = timezone.now()

        transaction = await TransactionService.create_transaction(
            transaction_type=TransactionType.DEPOSIT,
            amount=amount,
            direction=TransactionDirection.INBOUND,
            to_user=wallet.user,
            to_wallet=wallet,
            description=narration or f"Deposit from {sender_account_name}",
            external_reference=external_reference,
            fee_amount=fee_charged,
            to_balance_before=balance_before,
            to_balance_after=balance_after,
            sender_account_number=sender_account_number,
            sender_account_name=sender_account_name,
            sender_bank_name=sender_bank_name,
            metadata={
                "deposit_method": "account_number",
                "account_number": account_number,
                "sender_account": sender_account_number,
                "sender_name": sender_account_name,
                "sender_bank": sender_bank_name,
                "narration": narration,
                "webhook_payload": webhook_payload or {},
                "transaction_date": (
                    transaction_date.isoformat() if transaction_date else None
                ),
            },
        )

        if fee_charged > 0:
            await TransactionService.add_transaction_fee(
                transaction=transaction,
                fee_type="deposit",
                amount=fee_charged,
                percentage=fee_percentage * 100,
                description="Deposit processing fee",
            )

        await TransactionService.complete_transaction(
            transaction=transaction, reason="Deposit processed successfully"
        )

        return {
            "success": True,
            "transaction_id": str(transaction.transaction_id),
            "external_reference": external_reference,
            "amount_received": amount,
            "fee_charged": fee_charged,
            "amount_credited": amount_credited,
            "wallet_balance": wallet.balance,
            "account_number": account_number,
            "account_name": wallet.account_name,
            "status": "completed",
        }
