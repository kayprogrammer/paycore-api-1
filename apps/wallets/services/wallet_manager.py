from uuid import UUID
from django.contrib.auth.hashers import make_password, check_password
from typing import Optional, List

from apps.accounts.models import User
from apps.common.utils import set_dict_attr
from apps.wallets.models import Wallet, Currency, WalletStatus
from apps.common.exceptions import (
    NotFoundError,
    RequestError,
    ErrorCode,
    ValidationError,
)
from asgiref.sync import sync_to_async

from apps.wallets.schemas import CreateWalletSchema, UpdateWalletSchema


class WalletManager:
    """Service for managing wallet creation, activation, and settings"""

    @staticmethod
    async def create_wallet(user: User, data: CreateWalletSchema) -> Wallet:
        """Create a new wallet for a user"""

        # Get currency
        currency = await Currency.objects.aget_or_none(
            code=data.currency_code, is_active=True
        )
        if not currency:
            raise ValidationError(
                "currency_code", f"Currency {data.currency_code} not found or inactive"
            )

        # Check if user already has a default wallet for this currency
        if data.is_default:
            existing_default = await Wallet.objects.aget_or_none(
                user=user, currency=currency, is_default=True
            )
            if existing_default:
                existing_default.is_default = False
                await existing_default.asave()

        # Create wallet
        existing_wallet = await Wallet.objects.aget_or_none(
            user=user,
            currency=currency,
            is_default=data.is_default,
            wallet_type=data.wallet_type,
        )
        if existing_wallet:
            raise ValidationError(
                "wallet_type",
                f"User already has a {data.wallet_type} wallet for {currency.code}",
            )

        wallet = await Wallet.objects.acreate(
            user=user, currency=currency, **data.model_dump(exclude={"currency_code"})
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
        wallet = set_dict_attr(wallet, data.model_dump())
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
