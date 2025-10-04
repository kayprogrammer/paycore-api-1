from typing import List, Optional
from uuid import UUID

from apps.accounts.models import User
from apps.cards.models import Card, CardStatus
from apps.wallets.models import Wallet
from apps.common.exceptions import (
    ErrorCode,
    NotFoundError,
    RequestError,
    ValidationError,
)
from apps.cards.schemas import CreateCardSchema, UpdateCardSchema
from asgiref.sync import sync_to_async


class CardManager:
    """Service for managing card creation, updates, and lifecycle"""

    @staticmethod
    async def create_card(user: User, data: CreateCardSchema) -> Card:
        wallet = await Wallet.objects.select_related("currency", "user").aget_or_none(
            wallet_id=data.wallet_id, user=user
        )
        if not wallet:
            raise NotFoundError(err_msg="Wallet not found")

        if wallet.currency.code != data.currency_code:
            raise ValidationError(
                "currency_code",
                f"Card currency must match wallet currency ({wallet.currency.code})",
            )

        # For now, create a test card with dummy details
        # TODO: Integrate with card provider based on currency
        card = await Card.objects.acreate(
            user=user,
            wallet=wallet,
            card_type=data.card_type,
            card_brand=data.card_brand,
            card_number="4111111111111111",  # TODO: Get from provider
            card_holder_name=user.full_name,
            expiry_month=12,  # TODO: Get from provider
            expiry_year=2029,  # TODO: Get from provider
            cvv="123",  # TODO: Get from provider
            card_provider="internal",  # TODO: Use provider factory
            provider_card_id="test_card_id",  # TODO: Get from provider
            is_test_mode=True,
            spending_limit=data.spending_limit,
            daily_limit=data.daily_limit,
            monthly_limit=data.monthly_limit,
            nickname=data.nickname,
            created_for_merchant=data.created_for_merchant,
            billing_address=(
                data.billing_address.model_dump() if data.billing_address else {}
            ),
            status=CardStatus.INACTIVE,  # Cards start inactive, must be activated
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

        # Update fields
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
            return card

        if card.status == CardStatus.BLOCKED:
            raise RequestError(ErrorCode.NOT_ALLOWED, "Cannot freeze a blocked card")

        card.is_frozen = True
        await card.asave(update_fields=["is_frozen", "updated_at"])
        return card

    @staticmethod
    async def unfreeze_card(user: User, card_id: UUID) -> Card:
        card = await CardManager.get_card(user, card_id)
        if not card.is_frozen:
            return card
        card.is_frozen = False
        await card.asave(update_fields=["is_frozen", "updated_at"])
        return card

    @staticmethod
    async def block_card(user: User, card_id: UUID) -> Card:
        card = await CardManager.get_card(user, card_id)
        if card.status == CardStatus.BLOCKED:
            return card

        card.status = CardStatus.BLOCKED
        # TODO: Call provider API to block card
        await card.asave(update_fields=["status", "updated_at"])
        return card

    @staticmethod
    async def activate_card(user: User, card_id: UUID) -> Card:
        """Activate a card"""
        card = await CardManager.get_card(user, card_id)

        if card.status == CardStatus.ACTIVE:
            return card

        if card.status == CardStatus.BLOCKED:
            raise RequestError(ErrorCode.NOT_ALLOWED, "Cannot activate a blocked card")

        if card.is_expired:
            raise RequestError(ErrorCode.NOT_ALLOWED, "Cannot activate an expired card")

        card.status = CardStatus.ACTIVE
        # TODO: Call provider API to activate card
        await card.asave(update_fields=["status", "updated_at"])
        return card

    @staticmethod
    async def delete_card(user: User, card_id: UUID) -> None:
        card = await CardManager.get_card(user, card_id)

        if card.status != CardStatus.BLOCKED:
            card.status = CardStatus.BLOCKED
            await card.asave(update_fields=["status", "updated_at"])

        # TODO: Call provider API to terminate card
        # For now, we just block it and keep the record
        # In production, you might soft-delete or actually delete
