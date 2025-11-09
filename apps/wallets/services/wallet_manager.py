import time
from uuid import UUID
from django.contrib.auth.hashers import make_password, check_password
from typing import Optional, List
import random

from apps.accounts.models import User
from apps.common.utils import set_dict_attr
from apps.wallets.models import Wallet, Currency, WalletStatus
from apps.common.exceptions import (
    NotFoundError,
    RequestError,
    ErrorCode,
    BodyValidationError,
)
from asgiref.sync import sync_to_async

from apps.wallets.schemas import CreateWalletSchema, UpdateWalletSchema
from apps.wallets.services.providers.factory import AccountProviderFactory
from apps.notifications.services.dispatcher import (
    UnifiedNotificationDispatcher,
    NotificationChannel,
    NotificationEventType,
)


class WalletManager:
    """Service for managing wallet creation, activation, and settings"""

    @staticmethod
    async def generate_account_number() -> str:
        max_attempts = 10
        attempts = 0

        while True:
            account_number = "90" + "".join(
                [str(random.randint(0, 9)) for _ in range(8)]
            )

            # Check if unique
            if not await Wallet.objects.filter(account_number=account_number).aexists():
                return account_number

            attempts += 1
            if attempts >= max_attempts:
                # Fallback: use timestamp if random generation fails after max attempts
                return f"90{int(time.time()) % 100000000:08d}"

    @staticmethod
    async def create_wallet(user: User, data: CreateWalletSchema) -> Wallet:
        # Get currency
        currency = await Currency.objects.aget_or_none(
            code=data.currency_code, is_active=True
        )
        if not currency:
            raise BodyValidationError(
                "currency_code", f"Currency {data.currency_code} not found or inactive"
            )

        if data.is_default:
            existing_default = await Wallet.objects.aget_or_none(
                user=user, currency=currency, is_default=True
            )
            if existing_default:
                existing_default.is_default = False
                await existing_default.asave()

        existing_wallet = await Wallet.objects.aget_or_none(
            user=user,
            currency=currency,
            is_default=data.is_default,
            wallet_type=data.wallet_type,
        )
        if existing_wallet:
            raise BodyValidationError(
                "wallet_type",
                f"User already has a {data.wallet_type} wallet for {currency.code}",
            )

        # Get appropriate provider for currency
        test_mode = AccountProviderFactory.get_test_mode_setting()
        provider = AccountProviderFactory.get_provider_for_currency(
            currency.code, test_mode=test_mode
        )

        # Create virtual account via provider
        account_data = await provider.create_account(
            user_email=user.email,
            user_first_name=user.first_name or "",
            user_last_name=user.last_name or "",
            user_phone=getattr(user, "phone", None),
            currency_code=currency.code,
        )

        # Create wallet with provider account details
        wallet = await Wallet.objects.acreate(
            user=user,
            currency=currency,
            account_number=account_data["account_number"],
            account_name=account_data["account_name"],
            bank_name=account_data["bank_name"],
            account_provider=provider.get_provider_name(),
            provider_account_id=account_data["provider_account_id"],
            provider_metadata=account_data["provider_metadata"],
            is_test_mode=test_mode,
            **data.model_dump(exclude={"currency_code"}),
        )

        # Send wallet creation notification
        await sync_to_async(UnifiedNotificationDispatcher.dispatch)(
            user=user,
            event_type=NotificationEventType.WALLET_CREATED,
            channels=[
                NotificationChannel.IN_APP,
                NotificationChannel.PUSH,
                NotificationChannel.EMAIL,
            ],
            title="Wallet Created Successfully",
            message=f"Your {currency.code} wallet has been created successfully",
            context_data={
                "wallet_id": str(wallet.wallet_id),
                "wallet_type": wallet.wallet_type,
                "currency": currency.code,
                "account_number": wallet.account_number,
                "bank_name": wallet.bank_name,
            },
        )

        return wallet

    @staticmethod
    async def get_user_wallets(
        user: User,
        currency_code: str = None,
        wallet_type: str = None,
        status: str = None,
    ) -> List[Wallet]:
        """Get user's wallets with optional filtering"""

        filters = {"user": user}

        if currency_code:
            filters["currency__code"] = currency_code
        if wallet_type:
            filters["wallet_type"] = wallet_type
        if status:
            filters["status"] = status
        return await sync_to_async(list)(
            Wallet.objects.filter(**filters).select_related("currency")
        )

    @staticmethod
    async def get_default_wallet(user: User, currency_code: str) -> Optional[Wallet]:
        """Get user's default wallet for a currency"""
        return (
            await Wallet.objects.filter()
            .select_related("currency")
            .aget_or_none(
                user=user,
                currency__code=currency_code,
                is_default=True,
                status=WalletStatus.ACTIVE,
            )
        )

    @staticmethod
    async def set_default_wallet(user: User, wallet_id: str) -> Wallet:
        """Set a wallet as default for its currency"""

        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError(err_msg="Wallet not found")

        # Remove default from other wallets of same currency
        await Wallet.objects.filter(
            user=user, currency_id=wallet.currency_id, is_default=True
        ).aupdate(is_default=False)

        # Set this wallet as default
        wallet.is_default = True
        await wallet.asave()
        return wallet

    @staticmethod
    async def update_wallet_settings(
        user: User, wallet_id: UUID, data: UpdateWalletSchema
    ) -> Wallet:
        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=wallet_id, user=user
        )
        if not wallet:
            raise NotFoundError("Wallet not found")
        wallet = set_dict_attr(
            wallet, data.model_dump(exclude_none=True, exclude_unset=True)
        )
        await wallet.asave()
        return wallet

    @staticmethod
    async def set_wallet_pin(user: User, wallet_id: UUID, pin: str) -> Wallet:
        """Set or update wallet PIN"""

        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError("Wallet not found")

        wallet.pin_hash = make_password(str(pin))
        wallet.requires_pin = True
        await wallet.asave()
        return wallet

    @staticmethod
    async def verify_wallet_pin(user: User, wallet_id: str, pin: str) -> bool:
        """Verify wallet PIN"""

        try:
            wallet = await Wallet.objects.aget(wallet_id=wallet_id, user=user)
        except Wallet.DoesNotExist:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg="Wallet not found",
                status_code=404,
            )

        if not wallet.pin_hash:
            return False

        return check_password(pin, wallet.pin_hash)

    @staticmethod
    async def change_wallet_status(
        user: User, wallet_id: UUID, status: WalletStatus, admin_action: bool = False
    ) -> Wallet:
        """Change wallet status (activate, freeze, suspend, etc.)"""

        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError(
                "Wallet not found",
            )

        # Some status changes require admin privileges
        restricted_statuses = [WalletStatus.SUSPENDED, WalletStatus.CLOSED]
        if status in restricted_statuses and not admin_action:
            raise RequestError(
                err_code=ErrorCode.UNAUTHORIZED_USER,
                err_msg="Insufficient permissions for this action",
                status_code=403,
            )

        wallet.status = status
        await wallet.asave()
        return wallet

    @staticmethod
    async def delete_wallet(user: User, wallet_id: UUID) -> bool:
        """Soft delete a wallet (change status to CLOSED)"""

        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError("Wallet not found")

        # Check if wallet has balance
        if wallet.balance > 0:
            raise RequestError(
                err_code=ErrorCode.NOT_ALLOWED,
                err_msg="Cannot delete wallet with remaining balance",
            )

        # Check if it's the last active wallet for this currency
        other_active_wallets = (
            await Wallet.objects.filter(
                user=user, currency_id=wallet.currency_id, status=WalletStatus.ACTIVE
            )
            .exclude(wallet_id=wallet_id)
            .acount()
        )

        if other_active_wallets == 0:
            raise RequestError(
                err_code=ErrorCode.NOT_ALLOWED,
                err_msg="Cannot delete the last active wallet for this currency",
            )

        wallet.status = WalletStatus.CLOSED
        await wallet.asave()
        return True

    @staticmethod
    async def reset_spending_limits(user: User, wallet_id: str) -> Wallet:
        """Reset daily/monthly spending counters"""

        try:
            wallet = await Wallet.objects.aget(wallet_id=wallet_id, user=user)
        except Wallet.DoesNotExist:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg="Wallet not found",
                status_code=404,
            )

        wallet.reset_daily_limits()
        wallet.reset_monthly_limits()

        return wallet
