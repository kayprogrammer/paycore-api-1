from decimal import Decimal
from django.utils import timezone
from typing import Dict, Any
from asgiref.sync import sync_to_async
import uuid

from apps.accounts.models import User
from apps.transactions.services.transaction_service import TransactionService
from apps.wallets.models import Wallet, WalletStatus
from apps.common.exceptions import (
    NotFoundError,
    RequestError,
    ErrorCode,
)
from apps.wallets.schemas import HoldFundsSchema


class WalletOperations:
    """Service for wallet balance operations and transfers"""

    @staticmethod
    async def get_wallet_balance(user: User, wallet_id: uuid.UUID):
        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=wallet_id, user=user
        )
        if not wallet:
            raise NotFoundError(err_msg="Wallet not found")
        return wallet

    @staticmethod
    async def update_balance(
        wallet: Wallet,
        amount: Decimal,
        operation: str,  # 'credit', 'debit', 'hold', 'release'
        reference: str = None,
    ) -> Wallet:
        """Update wallet balance with proper validation"""

        if wallet.status != WalletStatus.ACTIVE:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Wallet is not active",
                status_code=400,
            )

        if operation == "credit":
            wallet.balance += amount
            wallet.available_balance += amount

        elif operation == "debit":
            if wallet.available_balance < amount:
                raise RequestError(
                    err_code=ErrorCode.VALIDATION_ERROR,
                    err_msg="Insufficient available balance",
                    status_code=400,
                )
            wallet.balance -= amount
            wallet.available_balance -= amount

            # Update spending counters
            wallet.daily_spent += amount
            wallet.monthly_spent += amount

        elif operation == "hold":
            if wallet.available_balance < amount:
                raise RequestError(
                    err_code=ErrorCode.VALIDATION_ERROR,
                    err_msg="Insufficient available balance for hold",
                    status_code=400,
                )
            wallet.available_balance -= amount
            wallet.pending_balance += amount

        elif operation == "release":
            if wallet.pending_balance < amount:
                raise RequestError(
                    err_code=ErrorCode.VALIDATION_ERROR,
                    err_msg="Insufficient pending balance to release",
                    status_code=400,
                )
            wallet.pending_balance -= amount
            wallet.available_balance += amount

        else:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Invalid balance operation",
                status_code=400,
            )

        wallet.last_transaction_at = timezone.now()
        await wallet.asave()

        return wallet

    @staticmethod
    async def hold_funds(
        user: User, wallet_id: uuid.UUID, data: HoldFundsSchema
    ) -> Dict[str, Any]:
        """Place a hold on wallet funds"""

        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=wallet_id, user=user
        )
        if not wallet:
            raise NotFoundError("Wallet not found")

        balance_before = wallet.balance
        await WalletOperations.update_balance(
            wallet, data.amount, "hold", data.reference
        )

        # Create transaction record
        transaction_obj = await TransactionService.create_hold_transaction(
            user=user,
            wallet=wallet,
            amount=data.amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            reference=data.reference,
            expires_at=data.expires_at,
            metadata={"hold_type": "funds_hold", "currency_code": wallet.currency.code},
        )

        await TransactionService.complete_transaction(transaction_obj)

        return {
            "hold_id": transaction_obj.transaction_id,
            "wallet_id": wallet.wallet_id,
            "amount": data.amount,
            "reference": data.reference,
            "expires_at": data.expires_at.isoformat() if data.expires_at else None,
            "timestamp": timezone.now().isoformat(),
        }

    @staticmethod
    async def release_hold(
        user: User, wallet_id: uuid.UUID, amount: Decimal, reference: str = None
    ) -> Dict[str, Any]:
        """Release a hold on wallet funds"""

        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=wallet_id, user=user
        )
        if not wallet:
            raise NotFoundError("Wallet not found")

        balance_before = wallet.balance
        await WalletOperations.update_balance(wallet, amount, "release", reference)

        transaction_obj = await TransactionService.create_release_transaction(
            user=user,
            wallet=wallet,
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            reference=reference,
            metadata={
                "release_type": "funds_release",
                "currency_code": wallet.currency.code,
            },
        )

        await TransactionService.complete_transaction(transaction_obj)
        return {
            "wallet_id": wallet.wallet_id,
            "amount": amount,
            "reference": reference,
            "timestamp": timezone.now().isoformat(),
        }

    @staticmethod
    async def get_wallet_summary(user: User) -> Dict[str, Any]:
        """Get summary of all user wallets"""

        # Fetch all wallets with their currencies in a single query
        wallets_list = await sync_to_async(list)(
            Wallet.objects.filter(user=user)
            .select_related("currency")
            .order_by("currency__code", "-is_default", "name")
        )
        if not wallets_list:
            return {"wallets": [], "total_balances": {}, "wallet_count": 0}

        # Process wallets and aggregate totals in single pass
        wallets = []
        total_balances = {}

        for wallet in wallets_list:
            # Build wallet data
            wallet_data = {
                "wallet_id": wallet.wallet_id,
                "name": wallet.name,
                "type": wallet.wallet_type,
                "currency": wallet.currency.code,
                "symbol": wallet.currency.symbol,
                "balance": wallet.balance,
                "available_balance": wallet.available_balance,
                "pending_balance": wallet.pending_balance,
                "status": wallet.status,
                "is_default": wallet.is_default,
                "formatted_balance": wallet.formatted_balance,
            }
            wallets.append(wallet_data)

            # Aggregate totals by currency
            currency_code = wallet.currency.code
            if currency_code not in total_balances:
                total_balances[currency_code] = {
                    "total_balance": wallet.balance,
                    "total_available": wallet.available_balance,
                    "total_pending": wallet.pending_balance,
                    "symbol": wallet.currency.symbol,
                    "wallet_count": 1,
                }
            else:
                total_balances[currency_code]["total_balance"] += wallet.balance
                total_balances[currency_code][
                    "total_available"
                ] += wallet.available_balance
                total_balances[currency_code]["total_pending"] += wallet.pending_balance
                total_balances[currency_code]["wallet_count"] += 1

        return {
            "wallets": wallets,
            "total_balances": total_balances,
            "wallet_count": len(wallets_list),
        }
