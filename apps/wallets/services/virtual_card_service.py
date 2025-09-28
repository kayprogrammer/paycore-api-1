from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from typing import List, Dict, Any
import secrets
import string
from datetime import datetime, timedelta

from apps.accounts.models import User
from apps.wallets.models import Wallet, VirtualCard, WalletStatus
from apps.common.exceptions import RequestError, ErrorCode


class VirtualCardService:
    """Service for managing virtual cards"""

    @staticmethod
    def _generate_card_number() -> str:
        """Generate a secure virtual card number"""
        # In production, this would integrate with a card issuing service
        # For now, generate a test card number with proper format
        prefix = "4111"  # Test Visa prefix
        middle = "".join(secrets.choice(string.digits) for _ in range(8))
        last_four = "".join(secrets.choice(string.digits) for _ in range(4))
        return f"{prefix}{middle}{last_four}"

    @staticmethod
    def _generate_cvv() -> str:
        """Generate a CVV code"""
        return "".join(secrets.choice(string.digits) for _ in range(3))

    @staticmethod
    def _generate_expiry() -> tuple[int, int]:
        """Generate expiry month and year (3 years from now)"""
        future_date = datetime.now() + timedelta(days=1095)  # 3 years
        return future_date.month, future_date.year

    @staticmethod
    async def create_virtual_card(
        user: User,
        wallet_id: str,
        nickname: str = None,
        spending_limit: Decimal = None,
        created_for_merchant: str = None,
    ) -> VirtualCard:
        """Create a new virtual card for a wallet"""

        # Get wallet
        try:
            wallet = await Wallet.objects.aget(wallet_id=wallet_id, user=user)
        except Wallet.DoesNotExist:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg="Wallet not found",
                status_code=404,
            )

        if wallet.status != WalletStatus.ACTIVE:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Cannot create virtual card for inactive wallet",
                status_code=400,
            )

        # Check virtual card limit (max 5 per wallet)
        existing_cards_count = await VirtualCard.objects.filter(
            wallet=wallet, is_active=True
        ).acount()

        if existing_cards_count >= 5:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Maximum virtual cards limit reached (5 per wallet)",
                status_code=400,
            )

        # Generate card details
        card_number = VirtualCardService._generate_card_number()
        cvv = VirtualCardService._generate_cvv()
        expiry_month, expiry_year = VirtualCardService._generate_expiry()

        # Create virtual card
        virtual_card = await VirtualCard.objects.acreate(
            wallet=wallet,
            card_number=card_number,
            card_holder_name=f"{user.first_name} {user.last_name}".upper(),
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            cvv=make_password(cvv),  # Encrypt CVV
            spending_limit=spending_limit,
            nickname=nickname,
            created_for_merchant=created_for_merchant,
            is_active=True,
        )

        return virtual_card

    @staticmethod
    async def get_user_virtual_cards(
        user: User, wallet_id: str = None
    ) -> List[VirtualCard]:
        """Get user's virtual cards"""

        filters = {"wallet__user": user}
        if wallet_id:
            filters["wallet__wallet_id"] = wallet_id

        cards = []
        async for card in VirtualCard.objects.filter(**filters).select_related(
            "wallet"
        ):
            cards.append(card)

        return cards

    @staticmethod
    async def get_virtual_card(user: User, card_id: str) -> VirtualCard:
        """Get a specific virtual card"""

        try:
            card = await VirtualCard.objects.select_related("wallet").aget(
                id=card_id, wallet__user=user
            )
        except VirtualCard.DoesNotExist:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg="Virtual card not found",
                status_code=404,
            )

        return card

    @staticmethod
    async def update_virtual_card(
        user: User,
        card_id: str,
        nickname: str = None,
        spending_limit: Decimal = None,
        is_active: bool = None,
        is_frozen: bool = None,
    ) -> VirtualCard:
        """Update virtual card settings"""

        card = await VirtualCardService.get_virtual_card(user, card_id)

        if nickname is not None:
            card.nickname = nickname
        if spending_limit is not None:
            card.spending_limit = spending_limit
        if is_active is not None:
            card.is_active = is_active
        if is_frozen is not None:
            card.is_frozen = is_frozen

        await card.asave()
        return card

    @staticmethod
    async def freeze_virtual_card(user: User, card_id: str) -> VirtualCard:
        """Freeze a virtual card"""

        card = await VirtualCardService.get_virtual_card(user, card_id)
        card.is_frozen = True
        await card.asave()

        return card

    @staticmethod
    async def unfreeze_virtual_card(user: User, card_id: str) -> VirtualCard:
        """Unfreeze a virtual card"""

        card = await VirtualCardService.get_virtual_card(user, card_id)
        card.is_frozen = False
        await card.asave()

        return card

    @staticmethod
    async def deactivate_virtual_card(user: User, card_id: str) -> VirtualCard:
        """Deactivate a virtual card"""

        card = await VirtualCardService.get_virtual_card(user, card_id)
        card.is_active = False
        card.is_frozen = True
        await card.asave()

        return card

    @staticmethod
    async def get_card_details(
        user: User, card_id: str, show_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Get virtual card details with optional sensitive data"""

        card = await VirtualCardService.get_virtual_card(user, card_id)

        card_data = {
            "card_id": str(card.id),
            "wallet_id": str(card.wallet.wallet_id),
            "wallet_name": card.wallet.name,
            "card_holder_name": card.card_holder_name,
            "masked_number": card.masked_number,
            "expiry_month": card.expiry_month,
            "expiry_year": card.expiry_year,
            "nickname": card.nickname,
            "spending_limit": card.spending_limit,
            "total_spent": card.total_spent,
            "is_active": card.is_active,
            "is_frozen": card.is_frozen,
            "is_expired": card.is_expired(),
            "created_for_merchant": card.created_for_merchant,
            "last_used_at": card.last_used_at,
            "created_at": card.created_at,
        }

        # Only show sensitive data if explicitly requested and card is active
        if show_sensitive and card.is_active and not card.is_frozen:
            card_data.update(
                {
                    "card_number": card.card_number,
                    # CVV is hashed, so we can't retrieve it
                    "cvv_available": bool(card.cvv),
                }
            )

        return card_data

    @staticmethod
    async def can_use_card(card: VirtualCard, amount: Decimal) -> tuple[bool, str]:
        """Check if virtual card can be used for a transaction"""

        if not card.is_active:
            return False, "Card is not active"

        if card.is_frozen:
            return False, "Card is frozen"

        if card.is_expired():
            return False, "Card has expired"

        # Check wallet status
        if card.wallet.status != WalletStatus.ACTIVE:
            return False, "Associated wallet is not active"

        # Check spending limit
        if card.spending_limit and (card.total_spent + amount) > card.spending_limit:
            return False, f"Transaction would exceed card spending limit"

        # Check wallet balance
        if card.wallet.available_balance < amount:
            return False, "Insufficient wallet balance"

        return True, None

    @staticmethod
    async def process_card_transaction(
        card: VirtualCard,
        amount: Decimal,
        merchant: str = None,
        description: str = None,
    ) -> Dict[str, Any]:
        """Process a virtual card transaction"""

        # Validate transaction
        can_use, error_msg = await VirtualCardService.can_use_card(card, amount)
        if not can_use:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR, err_msg=error_msg, status_code=400
            )

        # Import here to avoid circular imports
        from .wallet_operations import WalletOperations

        # Debit from wallet
        await WalletOperations.update_balance(
            card.wallet,
            amount,
            "debit",
            f"Virtual card transaction: {description or merchant}",
        )

        # Update card usage
        card.total_spent += amount
        card.last_used_at = timezone.now()
        await card.asave()

        return {
            "transaction_id": secrets.token_urlsafe(16),
            "card_id": str(card.id),
            "amount": amount,
            "merchant": merchant,
            "description": description,
            "wallet_balance": card.wallet.balance,
            "card_total_spent": card.total_spent,
            "timestamp": timezone.now().isoformat(),
        }

    @staticmethod
    async def get_card_transactions(
        user: User, card_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get virtual card transaction history"""

        # This would typically query a transactions table
        # For now, return a placeholder structure
        card = await VirtualCardService.get_virtual_card(user, card_id)

        # In a real implementation, this would query actual transaction records
        return [
            {
                "transaction_id": "placeholder",
                "card_id": str(card.id),
                "amount": card.total_spent,
                "merchant": "Sample Merchant",
                "description": "Sample transaction",
                "timestamp": (
                    card.last_used_at.isoformat() if card.last_used_at else None
                ),
                "status": "completed",
            }
        ]

    @staticmethod
    async def regenerate_card_details(user: User, card_id: str) -> VirtualCard:
        """Regenerate card number and CVV for security"""

        card = await VirtualCardService.get_virtual_card(user, card_id)

        if not card.is_active:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Cannot regenerate details for inactive card",
                status_code=400,
            )

        # Generate new details
        card.card_number = VirtualCardService._generate_card_number()
        card.cvv = make_password(VirtualCardService._generate_cvv())

        # Extend expiry by 3 years
        expiry_month, expiry_year = VirtualCardService._generate_expiry()
        card.expiry_month = expiry_month
        card.expiry_year = expiry_year

        await card.asave()

        return card
