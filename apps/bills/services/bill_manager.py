from typing import Dict, Any, Optional, List
from decimal import Decimal
from uuid import UUID
from asgiref.sync import sync_to_async

from apps.bills.models import (
    BillCategory,
    BillProvider,
    BillPackage,
    BillPayment,
    BillBeneficiary,
    BillPaymentStatus,
)
from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.paginators import Paginator
from apps.common.schemas import PaginationQuerySchema
from apps.wallets.models import Wallet
from apps.transactions.models import Transaction, TransactionType, TransactionStatus
from apps.common.exceptions import (
    NotFoundError,
    BodyValidationError,
    RequestError,
    ErrorCode,
)
from django.conf import settings
from apps.bills.services.providers.flutterwave import FlutterwaveBillProvider
from apps.bills.services.providers.internal import InternalBillPaymentProvider
import logging

logger = logging.getLogger(__name__)


class BillManager:
    """Bill payment management service"""

    @staticmethod
    def _get_payment_gateway(test_mode: bool = True):
        """
        Get the appropriate bill payment gateway based on settings.

        Returns:
            Internal provider if USE_INTERNAL_PROVIDER is True, else Flutterwave
        """
        use_internal = getattr(settings, "USE_INTERNAL_PROVIDER", False)

        if use_internal:
            return InternalBillPaymentProvider(test_mode=test_mode)
        else:
            return FlutterwaveBillProvider(test_mode=test_mode)

    @staticmethod
    async def get_provider(provider_id: UUID) -> BillProvider:
        provider = await BillProvider.objects.prefetch_related("packages").aget_or_none(
            provider_id=provider_id
        )
        if not provider:
            raise NotFoundError("Bill provider not found")
        if not provider.is_active:
            raise RequestError(
                err_code=ErrorCode.BILL_PROVIDER_UNAVAILABLE,
                err_msg="This bill provider is currently unavailable",
            )
        return provider

    @staticmethod
    async def get_package(package_id: UUID) -> BillPackage:
        """Get bill package by ID"""
        package = (
            await BillPackage.objects.select_related("provider")
            .filter(package_id=package_id)
            .afirst()
        )
        if not package:
            raise BodyValidationError("package", "Bill package not found")
        if not package.is_active:
            raise BodyValidationError(
                "package", "This package is currently unavailable"
            )
        return package

    @staticmethod
    async def list_providers(
        category: Optional[BillCategory] = None,
    ) -> List[BillProvider]:
        queryset = BillProvider.objects.filter(is_active=True)
        if category:
            queryset = queryset.filter(category=category)
        return await sync_to_async(list)(queryset)

    @staticmethod
    async def list_packages(provider_id: UUID) -> List[BillPackage]:
        return await sync_to_async(list)(
            BillPackage.objects.filter(
                provider__provider_id=provider_id, is_active=True
            ).order_by("display_order", "amount")
        )

    @staticmethod
    async def validate_customer(
        provider_id: UUID,
        customer_id: str,
    ) -> Dict[str, Any]:
        provider = await BillManager.get_provider(provider_id)
        gateway = BillManager._get_payment_gateway(test_mode=True)
        try:
            validation_result = await gateway.validate_customer(
                provider_code=provider.provider_code,
                customer_id=customer_id,
            )

            return validation_result

        except Exception as e:
            logger.error(f"Customer validation failed: {str(e)}")
            raise RequestError(
                err_code=ErrorCode.BILL_CUSTOMER_VALIDATION_FAILED,
                err_msg="Customer validation failed",
            )

    @staticmethod
    @aatomic
    async def create_bill_payment(
        user: User,
        wallet_id: UUID,
        provider_id: UUID,
        customer_id: str,
        amount: Optional[Decimal] = None,
        package_id: Optional[UUID] = None,
        **kwargs,
    ) -> BillPayment:
        provider = await BillManager.get_provider(provider_id)
        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=wallet_id, user=user
        )

        if not wallet:
            raise BodyValidationError("wallet", "Wallet not found")

        package = None
        if package_id:
            package = await BillManager.get_package(package_id)
            if package.provider_id != provider.id:
                raise BodyValidationError(
                    "package", "Package does not belong to this provider"
                )
            amount = package.amount
        elif amount is None:
            raise BodyValidationError("amount", "Amount or package_id is required")

        # Validate amount range
        if provider.supports_amount_range:
            if provider.min_amount and amount < provider.min_amount:
                raise BodyValidationError(
                    "amount", f"Amount must be at least {provider.min_amount}"
                )
            if provider.max_amount and amount > provider.max_amount:
                raise BodyValidationError(
                    "amount", f"Amount cannot exceed {provider.max_amount}"
                )

        # Calculate fees
        fee_amount = provider.calculate_fee(amount)
        total_amount = amount + fee_amount

        # Check wallet balance
        if wallet.balance < total_amount:
            raise BodyValidationError(
                "wallet",
                f"Insufficient balance. Required: {total_amount}, Available: {wallet.balance}",
            )

        # Create bill payment record
        bill_payment = await BillPayment.objects.acreate(
            user=user,
            wallet=wallet,
            provider=provider,
            package=package,
            category=provider.category,
            amount=amount,
            fee_amount=fee_amount,
            total_amount=total_amount,
            customer_id=customer_id,
            customer_email=kwargs.get("customer_email"),
            customer_phone=kwargs.get("customer_phone"),
            status=BillPaymentStatus.PROCESSING,
            save_beneficiary=kwargs.get("save_beneficiary", False),
            extra_data=kwargs.get("extra_data", {}),
        )

        # Deduct from wallet
        balance_before = wallet.balance
        wallet.balance -= total_amount
        await wallet.asave(update_fields=["balance", "updated_at"])
        balance_after = wallet.balance

        # Create transaction record
        transaction = await Transaction.objects.acreate(
            from_user=user,
            from_wallet=wallet,
            transaction_type=TransactionType.BILL_PAYMENT,
            amount=total_amount,
            status=TransactionStatus.PENDING,
            from_balance_before=balance_before,
            from_balance_after=balance_after,
            fee_amount=fee_amount,
            net_amount=amount,
            description=f"Bill payment to {provider.name} for {customer_id}",
            external_reference=str(bill_payment.payment_id),
        )

        bill_payment.transaction = transaction
        await bill_payment.asave(update_fields=["transaction", "updated_at"])

        # Process payment with gateway
        try:
            gateway = BillManager._get_payment_gateway(test_mode=True)

            payment_result = await gateway.process_payment(
                provider_code=provider.provider_code,
                customer_id=customer_id,
                amount=amount,
                reference=str(bill_payment.payment_id),
                email=kwargs.get("customer_email", user.email),
                phone_number=kwargs.get("customer_phone", ""),
                biller_name=provider.name,
            )

            bill_payment.provider_reference = payment_result.get("provider_reference")
            bill_payment.customer_name = payment_result.get("customer_name", "")
            bill_payment.token = payment_result.get("token")
            bill_payment.token_units = payment_result.get("token_units")
            bill_payment.provider_response = payment_result.get("extra_data", {})
            bill_payment.mark_completed()
            await bill_payment.asave(
                update_fields=[
                    "provider_reference",
                    "customer_name",
                    "token",
                    "token_units",
                    "provider_response",
                    "status",
                    "completed_at",
                    "updated_at",
                ]
            )

            # Update transaction status
            transaction.status = TransactionStatus.COMPLETED
            transaction.metadata = bill_payment.provider_response
            await transaction.asave(update_fields=["status", "metadata", "updated_at"])

            # Save beneficiary if requested
            if kwargs.get("save_beneficiary") and kwargs.get("beneficiary_nickname"):
                await BillManager._save_beneficiary(
                    user=user,
                    provider=provider,
                    customer_id=customer_id,
                    customer_name=payment_result.get("customer_name", ""),
                    nickname=kwargs.get("beneficiary_nickname"),
                )

            logger.info(f"Bill payment completed: {bill_payment.payment_id}")

        except Exception as e:
            # Mark payment as failed
            logger.error(f"Bill payment failed: {str(e)}")
            bill_payment.mark_failed(str(e))
            await bill_payment.asave(
                update_fields=["status", "failed_at", "failure_reason", "updated_at"]
            )

            # Update transaction status
            transaction.status = TransactionStatus.FAILED
            await transaction.asave(update_fields=["status", "updated_at"])

            # Refund wallet
            wallet.balance += total_amount
            await wallet.asave(update_fields=["balance", "updated_at"])

            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR, f"Bill payment failed: {str(e)}"
            )

        return bill_payment

    @staticmethod
    async def _save_beneficiary(
        user: User,
        provider: BillProvider,
        customer_id: str,
        customer_name: str,
        nickname: str,
    ):
        try:
            beneficiary, created = await BillBeneficiary.objects.aget_or_create(
                user=user,
                provider=provider,
                customer_id=customer_id,
                defaults={
                    "nickname": nickname,
                    "customer_name": customer_name,
                },
            )

            if not created:
                # Update existing beneficiary
                beneficiary.nickname = nickname
                beneficiary.customer_name = customer_name
                await beneficiary.asave(
                    update_fields=["nickname", "customer_name", "updated_at"]
                )

        except Exception as e:
            logger.error(f"Failed to save beneficiary: {str(e)}")
            # Don't fail the payment if beneficiary save fails

    @staticmethod
    async def get_user_payments(
        user: User,
        category: Optional[str] = None,
        status: Optional[str] = None,
        page_params: PaginationQuerySchema = None,
    ) -> List[BillPayment]:
        queryset = BillPayment.objects.filter(user=user).select_related(
            "provider", "package", "transaction"
        )

        if category:
            queryset = queryset.filter(category=category)
        if status:
            queryset = queryset.filter(status=status)
        paginated_data = await Paginator.paginate_queryset(
            queryset.order_by("-created_at"), page_params.page, page_params.limit
        )
        return paginated_data

    @staticmethod
    async def get_payment_by_id(user: User, payment_id: UUID) -> BillPayment:
        payment = await BillPayment.objects.select_related(
            "provider", "package", "transaction"
        ).aget_or_none(payment_id=payment_id, user=user)

        if not payment:
            raise NotFoundError("Bill payment not found")
        return payment
