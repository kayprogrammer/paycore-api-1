from typing import List, Optional
from uuid import UUID

from apps.accounts.models import User
from apps.cards.models import Card, CardStatus
from apps.wallets.models import Wallet
from apps.common.exceptions import (
    ErrorCode,
    NotFoundError,
    RequestError,
    BodyValidationError,
)
from apps.cards.schemas import CreateCardSchema, UpdateCardSchema
from apps.cards.services.providers.factory import CardProviderFactory
from asgiref.sync import sync_to_async
from apps.notifications.services.dispatcher import (
    UnifiedNotificationDispatcher,
    NotificationEventType,
    NotificationChannel,
)
from django.conf import settings


class CardManager:
    """Service for managing card creation, updates, and lifecycle"""

    @staticmethod
    async def create_card(user: User, data: CreateCardSchema) -> Card:
        """
        Create a new card for a user using appropriate provider.

        Strategy:
        - USD → Flutterwave or Sudo (based on configuration)
        - NGN → Flutterwave or Sudo
        - GBP → Flutterwave
        """
        if not user.phone:
            raise RequestError(
                ErrorCode.NOT_ALLOWED, "Update your phone number first in profile"
            )
        # Get and validate wallet
        wallet = await Wallet.objects.select_related("currency", "user").aget_or_none(
            wallet_id=data.wallet_id, user=user
        )
        if not wallet:
            raise NotFoundError(err_msg="Wallet not found")

        if wallet.currency.code != data.currency_code:
            raise BodyValidationError(
                "currency_code",
                f"Card currency must match wallet currency ({wallet.currency.code})",
            )

        test_mode = CardProviderFactory.get_test_mode_setting()
        provider = CardProviderFactory.get_provider_for_currency(
            wallet.currency.code, test_mode=test_mode
        )

        card_data = await provider.create_card(
            user_email=user.email,
            user_first_name=user.first_name or "",
            user_last_name=user.last_name or "",
            user_phone=user.phone,
            currency_code=wallet.currency.code,
            card_type=data.card_type,
            card_brand=data.card_brand,
            billing_address=(
                data.billing_address.model_dump() if data.billing_address else None
            ),
            date_of_birth=user.dob.strftime("%Y-%m-%d") if user.dob else None,
        )

        card = await Card.objects.acreate(
            user=user,
            wallet=wallet,
            card_type=data.card_type,
            card_brand=data.card_brand,
            card_number=card_data["card_number"],
            card_holder_name=card_data["card_holder_name"],
            expiry_month=card_data["expiry_month"],
            expiry_year=card_data["expiry_year"],
            cvv=card_data["cvv"],
            card_provider=provider.get_provider_name(),
            provider_card_id=card_data["provider_card_id"],
            provider_metadata=card_data["provider_metadata"],
            is_test_mode=test_mode,
            spending_limit=data.spending_limit,
            daily_limit=data.daily_limit,
            monthly_limit=data.monthly_limit,
            nickname=data.nickname,
            created_for_merchant=data.created_for_merchant,
            billing_address=(
                data.billing_address.model_dump() if data.billing_address else {}
            ),
            status=(
                CardStatus.ACTIVE
                if settings.USE_INTERNAL_PROVIDER
                else CardStatus.INACTIVE
            ),
        )

        # Send card creation notification
        await sync_to_async(UnifiedNotificationDispatcher.dispatch)(
            user=user,
            event_type=NotificationEventType.CARD_ISSUED,
            channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
            title="Card Issued Successfully",
            message=f"Your {data.card_brand} {data.card_type} card has been issued successfully",
            context_data={
                "card_id": str(card.card_id),
                "card_type": card.card_type,
                "card_brand": card.card_brand,
                "card_number": f"****{card.card_number[-4:]}",
                "currency": wallet.currency.code,
            },
        )

        return card

    @staticmethod
    async def get_user_cards(
        user: User,
        status: Optional[str] = None,
        card_type: Optional[str] = None,
    ) -> List[Card]:
        queryset = Card.objects.select_related("wallet", "wallet__currency").filter(
            user=user
        )
        if status:
            queryset = queryset.filter(status=status)
        if card_type:
            queryset = queryset.filter(card_type=card_type)

        return await sync_to_async(list)(queryset.order_by("-created_at"))

    @staticmethod
    async def get_card(user: User, card_id: UUID) -> Card:
        card = await Card.objects.select_related(
            "wallet", "wallet__currency"
        ).aget_or_none(card_id=card_id, user=user)
        if not card:
            raise NotFoundError("Card not found")
        return card

    @staticmethod
    async def update_card(user: User, card_id: UUID, data: UpdateCardSchema) -> Card:
        card = await CardManager.get_card(user, card_id)

        update_fields = []
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                if field == "billing_address" and value:
                    setattr(
                        card,
                        field,
                        value.model_dump() if hasattr(value, "model_dump") else value,
                    )
                else:
                    setattr(card, field, value)
                update_fields.append(field)

        if update_fields:
            update_fields.append("updated_at")
            await card.asave(update_fields=update_fields)

        return card

    @staticmethod
    async def freeze_card(user: User, card_id: UUID) -> Card:
        card = await CardManager.get_card(user, card_id)

        if card.is_frozen:
            raise BodyValidationError("card", "Card is already frozen")

        if card.status == CardStatus.BLOCKED:
            raise BodyValidationError("card", "Cannot freeze a blocked card")

        test_mode = CardProviderFactory.get_test_mode_setting()
        provider = CardProviderFactory.get_provider(
            card.card_provider, test_mode=test_mode
        )
        await provider.freeze_card(card.provider_card_id)

        card.freeze()
        await card.asave(update_fields=["is_frozen", "updated_at"])

        return card

    @staticmethod
    async def unfreeze_card(user: User, card_id: UUID) -> Card:
        card = await CardManager.get_card(user, card_id)

        if not card.is_frozen:
            return card

        test_mode = CardProviderFactory.get_test_mode_setting()
        provider = CardProviderFactory.get_provider(
            card.card_provider, test_mode=test_mode
        )
        await provider.unfreeze_card(card.provider_card_id)

        card.is_frozen = False
        await card.asave(update_fields=["is_frozen", "updated_at"])

        return card

    @staticmethod
    async def block_card(user: User, card_id: UUID) -> Card:
        card = await CardManager.get_card(user, card_id)

        if card.status == CardStatus.BLOCKED:
            return card

        # Get provider and block card
        test_mode = CardProviderFactory.get_test_mode_setting()
        provider = CardProviderFactory.get_provider(
            card.card_provider, test_mode=test_mode
        )
        await provider.block_card(card.provider_card_id)

        card.status = CardStatus.BLOCKED
        await card.asave(update_fields=["status", "updated_at"])

        return card

    @staticmethod
    async def activate_card(user: User, card_id: UUID) -> Card:
        """
        Activate a card.

        Note: Most card providers create cards in an inactive state.
        Activation is typically a local status update that authorizes the user
        to start using the card. The provider's card itself is already functional.
        """
        card = await CardManager.get_card(user, card_id)

        if card.status == CardStatus.ACTIVE:
            return card

        if card.status == CardStatus.BLOCKED:
            raise RequestError(ErrorCode.NOT_ALLOWED, "Cannot activate a blocked card")

        if card.is_expired:
            raise RequestError(ErrorCode.NOT_ALLOWED, "Cannot activate an expired card")

        card.status = CardStatus.ACTIVE
        await card.asave(update_fields=["status", "updated_at"])

        return card

    @staticmethod
    async def delete_card(user: User, card_id: UUID) -> None:
        """
        Delete a card (permanent termination).

        This blocks the card with the provider and locally, keeping the record
        for audit/transaction history purposes.
        """
        card = await CardManager.get_card(user, card_id)

        if card.status != CardStatus.BLOCKED:
            test_mode = CardProviderFactory.get_test_mode_setting()
            provider = CardProviderFactory.get_provider(
                card.card_provider, test_mode=test_mode
            )
            await provider.block_card(card.provider_card_id)

            card.status = CardStatus.BLOCKED
            await card.asave(update_fields=["status", "updated_at"])

        # Keep the record for audit/transaction history purposes
        # In production, you might soft-delete by adding a deleted_at field
