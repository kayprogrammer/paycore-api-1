from decimal import Decimal
from uuid import UUID
from typing import Dict, Any, Tuple

from django.contrib.auth.hashers import check_password

from apps.accounts.models import User
from apps.common.utils import serialize_for_json
from apps.transactions.services.providers.withdrawal_factory import (
    WithdrawalProviderFactory,
)
from apps.wallets.models import Wallet, WalletStatus
from apps.transactions.models import Transaction, TransactionType, TransactionStatus
from apps.common.decorators import aatomic
from apps.common.exceptions import (
    BodyValidationError,
    RequestError,
    ErrorCode,
)
from django.utils import timezone


class WithdrawalManager:
    """Service for managing withdrawal transactions"""

    @staticmethod
    async def _get_wallet(wallet_id: UUID, user: User) -> Wallet:
        wallet = await Wallet.objects.select_related("currency", "user").aget_or_none(
            wallet_id=wallet_id, user=user
        )
        if not wallet:
            raise BodyValidationError("wallet_id", "Wallet not found")
        if wallet.status != WalletStatus.ACTIVE:
            raise BodyValidationError("wallet_id", "Wallet is not active")

        return wallet

    @staticmethod
    async def _verify_pin(wallet: Wallet, pin: str = None) -> None:
        # Check if PIN is required for this wallet
        if wallet.requires_pin and wallet.pin_hash:
            if not pin:
                raise BodyValidationError("pin", "PIN required for this withdrawal")
            if not check_password(pin, wallet.pin_hash):
                raise BodyValidationError("pin", "Invalid PIN")

    @staticmethod
    async def _check_sufficient_balance(
        wallet: Wallet, amount: Decimal, fee: Decimal
    ) -> None:
        total_required = amount + fee
        if wallet.balance < total_required:
            raise BodyValidationError(
                "amount",
                f"Insufficient balance. Required: {total_required}, Available: {wallet.balance}",
            )

    @staticmethod
    @aatomic
    async def initiate_withdrawal(
        user: User,
        wallet_id: UUID,
        amount: Decimal,
        account_details: Dict[str, Any],
        pin: str = None,
        description: str = None,
    ) -> Tuple[Transaction, Dict[str, Any]]:
        wallet = await WithdrawalManager._get_wallet(wallet_id, user)
        await WithdrawalManager._verify_pin(wallet, pin)

        # Calculate fees (you can implement your own fee logic)
        fee_amount = Decimal("0.00")  # No fee for now, or calculate based on provider
        await WithdrawalManager._check_sufficient_balance(wallet, amount, fee_amount)
        test_mode = WithdrawalProviderFactory.get_test_mode_setting()
        provider = WithdrawalProviderFactory.get_provider_for_currency(
            wallet.currency.code, test_mode=test_mode
        )
        reference = f"WITHDRAW-{wallet_id.hex[:8]}-{int(__import__('time').time())}"

        # Create transaction record
        transaction = await Transaction.objects.acreate(
            from_user=user,
            from_wallet=wallet,
            transaction_type=TransactionType.WITHDRAWAL,
            status=TransactionStatus.PENDING,
            amount=amount,
            fee_amount=fee_amount,
            net_amount=amount,  # User receives full amount
            external_reference=reference,
            description=description or "Withdrawal to bank account",
            from_balance_before=wallet.balance,
            metadata={},
        )

        try:
            # Initiate withdrawal with provider
            withdrawal_info = await provider.initiate_withdrawal(
                user_email=user.email,
                user_first_name=user.first_name,
                user_last_name=user.last_name,
                amount=amount,
                currency_code=wallet.currency.code,
                reference=reference,
                account_details=account_details,
                description=description,
            )

            # Debit wallet immediately (withdrawal is committed)
            wallet.balance -= amount + fee_amount
            await wallet.asave(update_fields=["balance", "updated_at"])

            # Update transaction based on provider response
            if withdrawal_info["status"] == "completed":
                transaction.status = TransactionStatus.COMPLETED
                transaction.completed_at = timezone.now()
            elif withdrawal_info["status"] in ["pending", "processing"]:
                transaction.status = TransactionStatus.PENDING
            elif withdrawal_info["status"] == "failed":
                # Refund wallet if provider immediately failed
                wallet.balance += amount + fee_amount
                await wallet.asave(update_fields=["balance", "updated_at"])
                transaction.status = TransactionStatus.FAILED
                transaction.failure_reason = withdrawal_info.get("metadata", {}).get(
                    "message", "Withdrawal failed"
                )

            serialized_withdrawal_info = serialize_for_json(withdrawal_info)
            transaction.metadata = transaction.metadata | {
                "provider_response": serialized_withdrawal_info
            }
            transaction.from_balance_after = wallet.balance

            await transaction.asave(
                update_fields=[
                    "metadata",
                    "status",
                    "from_balance_after",
                    "completed_at",
                    "failure_reason",
                    "updated_at",
                ]
            )
            return transaction, withdrawal_info

        except Exception as e:
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to initiate withdrawal: {str(e)}",
            )

    @staticmethod
    @aatomic
    async def verify_and_complete_withdrawal(
        transaction_id: UUID = None, reference: str = None
    ) -> Transaction:
        """
        Verify and update withdrawal transaction status.
        Used for:
        - Webhook handlers
        - Manual verification
        - Polling for status updates
        """
        transaction = None
        if transaction_id:
            transaction = await Transaction.objects.select_related(
                "from_wallet__currency", "from_user"
            ).aget_or_none(transaction_id=transaction_id)
        elif reference:
            transaction = await Transaction.objects.select_related(
                "from_wallet__currency", "from_user"
            ).aget_or_none(external_reference=reference)
        else:
            raise BodyValidationError(
                "transaction", "Transaction ID or reference required"
            )

        if not transaction:
            raise BodyValidationError("transaction", "Transaction not found")

        # Skip if already completed or failed
        if transaction.status in [
            TransactionStatus.COMPLETED,
            TransactionStatus.FAILED,
        ]:
            return transaction

        # Get provider and verify
        test_mode = WithdrawalProviderFactory.get_test_mode_setting()
        provider = WithdrawalProviderFactory.get_provider(
            transaction.provider or "internal", test_mode=test_mode
        )

        try:
            verification_result = await provider.verify_withdrawal(
                transaction.external_reference
            )

            if verification_result["status"] == "success":
                transaction.status = TransactionStatus.COMPLETED
                transaction.completed_at = timezone.now()
                transaction.metadata = transaction.metadata | {
                    "provider_response": serialize_for_json(verification_result)
                }

            elif verification_result["status"] == "failed":
                # Withdrawal failed - refund wallet
                wallet = transaction.from_wallet
                refund_amount = transaction.amount + transaction.fee_amount
                wallet.balance += refund_amount
                await wallet.asave(update_fields=["balance", "updated_at"])

                transaction.status = TransactionStatus.FAILED
                transaction.failure_reason = verification_result.get(
                    "failure_reason", "Withdrawal failed"
                )
                transaction.from_balance_after = wallet.balance

            # else: still pending, keep current status

            serialized_withdrawal_info = serialize_for_json(verification_result)
            transaction.metadata = transaction.metadata | {
                "provider_response": serialized_withdrawal_info
            }

            await transaction.asave(
                update_fields=[
                    "status",
                    "completed_at",
                    "metadata",
                    "failure_reason",
                    "from_balance_after",
                    "updated_at",
                ]
            )

            return transaction

        except Exception as e:
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to verify withdrawal: {str(e)}",
            )
