from decimal import Decimal
from uuid import UUID
from typing import Dict, Any, Tuple

from apps.accounts.models import User
from apps.common.utils import serialize_for_json
from apps.transactions.services.factory import DepositProviderFactory
from apps.wallets.models import Wallet, WalletStatus
from apps.transactions.models import Transaction, TransactionType, TransactionStatus
from apps.common.decorators import aatomic
from apps.common.exceptions import BodyValidationError, RequestError, ErrorCode
from django.utils import timezone


class DepositManager:
    """Service for managing deposit transactions"""

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
    @aatomic
    async def initiate_deposit(
        user: User,
        wallet_id: UUID,
        amount: Decimal,
        payment_method: str = "bank_transfer",
        callback_url: str = None,
        description: str = None,
    ) -> Tuple[Transaction, Dict[str, Any]]:
        """
        Initiate a deposit transaction.
        The payment_info_dict contains:
            - reference: Transaction reference
            - payment_url: URL for payment (None for internal)
            - status: Transaction status
            - provider_reference: Provider's reference
        """
        wallet = await DepositManager._get_wallet(wallet_id, user)
        if amount <= 0:
            raise BodyValidationError("amount", "Amount must be greater than 0")

        # Get appropriate deposit provider
        test_mode = DepositProviderFactory.get_test_mode_setting()
        provider = DepositProviderFactory.get_provider_for_currency(
            wallet.currency.code, test_mode=test_mode
        )

        # Check if provider supports this currency
        if not provider.supports_currency(wallet.currency.code):
            raise BodyValidationError(
                "currency",
                f"Deposits not supported for {wallet.currency.code}",
            )

        # Create pending transaction
        balance_before = wallet.balance
        reference = f"DEP-{wallet_id.hex[:8]}-{int(__import__('time').time())}"

        transaction = await Transaction.objects.acreate(
            to_user=user,
            to_wallet=wallet,
            transaction_type=TransactionType.DEPOSIT,
            net_amount=amount,
            amount=amount,
            status=TransactionStatus.PENDING,
            from_balance_before=balance_before,
            from_balance_after=balance_before,  # Not updated yet
            description=description or f"Deposit via {payment_method}",
            external_reference=reference,
            metadata={"provider": provider.get_provider_name()},
        )

        try:
            # Initiate deposit with provider
            payment_info = await provider.initiate_deposit(
                user_email=user.email,
                user_first_name=user.first_name or "",
                user_last_name=user.last_name or "",
                amount=amount,
                currency_code=wallet.currency.code,
                reference=reference,
                callback_url=callback_url,
            )

            # Update transaction with provider info (serialize decimals)
            serialized_payment_info = serialize_for_json(payment_info)
            transaction.metadata = transaction.metadata | {
                "provider_response": serialized_payment_info
            }

            await transaction.asave(update_fields=["metadata"])

            return transaction, payment_info

        except Exception as e:
            # Transaction will be automatically rolled back by @aatomic decorator
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to initiate deposit: {str(e)}",
            )

    @staticmethod
    @aatomic
    async def verify_and_complete_deposit(
        transaction_id: UUID = None, reference: str = None
    ) -> Transaction:
        """
        Verify and complete a deposit transaction.

        Can be called from:
        - Webhook handler (with reference)
        - Manual verification (with transaction_id or reference)
        """
        transaction = None
        if transaction_id:
            transaction = await Transaction.objects.select_related(
                "to_wallet__currency", "to_user"
            ).aget_or_none(transaction_id=transaction_id)
        elif reference:
            transaction = await Transaction.objects.select_related(
                "to_wallet__currency", "to_user"
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
        test_mode = DepositProviderFactory.get_test_mode_setting()
        provider = DepositProviderFactory.get_provider(
            transaction.metadata.get("provider") or "internal", test_mode=test_mode
        )

        try:
            verification_result = await provider.verify_deposit(
                transaction.external_reference
            )
            print(verification_result)
            if verification_result["status"] == "success":
                # Credit wallet
                wallet = transaction.to_wallet
                wallet.balance += transaction.amount
                wallet.available_balance += transaction.amount
                await wallet.asave(
                    update_fields=["balance", "available_balance", "updated_at"]
                )

                # Update transaction
                transaction.status = TransactionStatus.COMPLETED
                transaction.from_balance_after = wallet.balance
                transaction.completed_at = timezone.now()
                transaction.metadata = transaction.metadata | {
                    "provider_response": serialize_for_json(verification_result)
                }

            elif verification_result["status"] == "failed":
                transaction.status = TransactionStatus.FAILED
                transaction.failure_reason = "Payment verification failed"

            await transaction.asave(
                update_fields=[
                    "status",
                    "from_balance_after",
                    "completed_at",
                    "metadata",
                    "failure_reason",
                    "updated_at",
                ]
            )

            return transaction

        except Exception as e:
            # Transaction will be automatically rolled back by @aatomic decorator
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to verify deposit: {str(e)}",
            )
