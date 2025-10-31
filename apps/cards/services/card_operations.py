from uuid import UUID
from decimal import Decimal
from typing import Dict, Any
from django.utils import timezone

from apps.accounts.models import User
from apps.cards.models import Card
from apps.common.paginators import Paginator
from apps.common.schemas import PaginationQuerySchema
from apps.transactions.models import (
    Transaction,
    TransactionType,
    TransactionStatus,
    TransactionDirection,
)
from apps.common.exceptions import (
    NotFoundError,
    BodyValidationError,
    RequestError,
    ErrorCode,
)
from apps.common.decorators import aatomic
from apps.wallets.services.security_service import WalletSecurityService


class CardOperations:
    """Service for card operations like funding, transactions"""

    @staticmethod
    @aatomic
    async def fund_card(
        user: User,
        card_id: UUID,
        amount: Decimal,
        pin: str = None,
        description: str = None,
    ) -> Dict[str, Any]:
        # Get card
        card = await Card.objects.select_related(
            "wallet", "wallet__currency"
        ).aget_or_none(card_id=card_id, user=user)
        if not card:
            raise NotFoundError("Card not found")

        # Validate card can be funded
        if not card.can_transact:
            raise RequestError(
                err_code=ErrorCode.NOT_ALLOWED,
                err_msg="Card cannot be funded at this time",
            )

        wallet = card.wallet

        if wallet.requires_pin and not pin:
            raise BodyValidationError("pin", "Wallet PIN is required")

        if wallet.requires_pin:
            is_valid = await WalletSecurityService.verify_pin(wallet, pin)
            if not is_valid:
                raise BodyValidationError("pin", "Invalid PIN")

        if amount > wallet.available_balance:
            raise BodyValidationError("amount", "Insufficient wallet balance")

        balance_before = wallet.available_balance

        # Card Funding Model:
        # Money stays in wallet - card is just a spending instrument.
        # When card is used for purchases/withdrawals, money is deducted from wallet.
        # This funding transaction is for record-keeping and authorization tracking only.
        # No actual balance transfer occurs.

        # Create transaction record (for tracking purposes)
        transaction = await Transaction.objects.acreate(
            transaction_type=TransactionType.CARD_FUND,
            status=TransactionStatus.COMPLETED,
            direction=TransactionDirection.INTERNAL,
            amount=amount,
            fee_amount=Decimal("0"),
            net_amount=amount,
            from_user=user,
            to_user=user,
            from_wallet=wallet,
            to_wallet=wallet,  # Same wallet
            card=card,
            description=description or f"Card funding - {card.masked_number}",
            from_balance_before=balance_before,
            from_balance_after=balance_before,  # No change (internal allocation)
            to_balance_before=balance_before,
            to_balance_after=balance_before,
            initiated_at=timezone.now(),
            processed_at=timezone.now(),
            completed_at=timezone.now(),
        )

        return {
            "card_id": str(card.card_id),
            "amount_funded": float(amount),
            "wallet_balance_before": float(balance_before),
            "wallet_balance_after": float(balance_before),
            "transaction_id": str(transaction.transaction_id),
            "message": "Card funded successfully. Money remains in wallet and will be debited when card is used.",
        }

    @staticmethod
    async def get_card_transactions(
        user: User, card_id: UUID, page_params: PaginationQuerySchema
    ) -> Dict[str, Any]:
        card = await Card.objects.aget_or_none(card_id=card_id, user=user)
        if not card:
            raise NotFoundError("Card not found")

        # Get transactions
        queryset = (
            Transaction.objects.filter(card=card)
            .select_related("from_wallet", "from_wallet__currency")
            .order_by("-created_at")
        )
        return await Paginator.paginate_queryset(
            queryset, page_params.page, page_params.limit
        )
