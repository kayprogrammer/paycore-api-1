import asyncio
import random
import time
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta

from .base import BaseCardProvider


class InternalCardProvider(BaseCardProvider):
    """
    Internal card provider for development and fallback purposes.

    This provider simulates card creation and management without making external API calls.
    Perfect for:
    - Development when external card providers are not available
    - Testing without incurring API costs
    - Fallback when external providers have issues

    Features:
    - Generates realistic card numbers (following Luhn algorithm)
    - Supports virtual and physical cards
    - Supports multiple currencies (USD, NGN, EUR, GBP, etc.)
    - No external dependencies
    - Immediate card creation

    Card Number Format: 16 digits, valid Luhn checksum
    """

    SUPPORTED_CURRENCIES = [
        "USD",  # US Dollar
        "NGN",  # Nigerian Naira
        "EUR",  # Euro
        "GBP",  # British Pound
        "KES",  # Kenyan Shilling
        "GHS",  # Ghanaian Cedi
        "ZAR",  # South African Rand
    ]

    SUPPORTED_CARD_TYPES = ["virtual", "physical"]

    # Card BIN prefixes for different brands
    CARD_BINS = {
        "visa": ["4"],
        "mastercard": ["51", "52", "53", "54", "55"],
        "verve": ["506"],
    }

    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)

    def _generate_card_number(self, card_brand: str) -> str:
        """
        Generate a valid card number using Luhn algorithm.

        Args:
            card_brand: Card brand (visa, mastercard, verve)

        Returns:
            str: Valid 16-digit card number
        """
        # Get BIN prefix for the card brand
        bins = self.CARD_BINS.get(card_brand.lower(), ["4"])
        bin_prefix = random.choice(bins)

        # Generate remaining digits (leaving space for checksum)
        remaining_length = 15 - len(bin_prefix)
        number = bin_prefix + "".join(
            [str(random.randint(0, 9)) for _ in range(remaining_length)]
        )

        # Calculate Luhn checksum
        def luhn_checksum(card_number):
            def digits_of(n):
                return [int(d) for d in str(n)]

            digits = digits_of(card_number)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d * 2))
            return checksum % 10

        # Add checksum digit
        checksum = luhn_checksum(number + "0")
        check_digit = (10 - checksum) % 10
        return number + str(check_digit)

    def _mask_card_number(self, card_number: str) -> str:
        """Mask card number for display (show last 4 digits)."""
        return f"****  ****  ****  {card_number[-4:]}"

    def _generate_cvv(self) -> str:
        """Generate a random 3-digit CVV."""
        return "".join([str(random.randint(0, 9)) for _ in range(3)])

    def _generate_expiry_date(self) -> tuple:
        """Generate expiry date (3 years from now)."""
        expiry = datetime.now() + timedelta(days=365 * 3)
        return expiry.month, expiry.year

    async def create_card(
        self,
        user_email: str,
        user_first_name: str,
        user_last_name: str,
        user_phone: str,
        currency_code: str,
        card_type: str,
        card_brand: str,
        billing_address: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create an internal virtual/physical card.

        Generates realistic card details without external API calls.
        """
        # Add small delay to simulate API behavior
        await asyncio.sleep(0.1)

        # Generate card details
        card_number = self._generate_card_number(card_brand)
        cvv = self._generate_cvv()
        expiry_month, expiry_year = self._generate_expiry_date()
        card_holder_name = f"{user_first_name} {user_last_name}".upper()
        masked_number = self._mask_card_number(card_number)

        # Generate provider card ID
        provider_card_id = (
            f"internal_card_{int(time.time())}_{random.randint(1000, 9999)}"
        )

        return {
            "card_number": card_number,  # In production, this should be encrypted
            "card_holder_name": card_holder_name,
            "expiry_month": expiry_month,
            "expiry_year": expiry_year,
            "cvv": cvv,  # In production, this should be encrypted
            "provider_card_id": provider_card_id,
            "masked_number": masked_number,
            "provider_metadata": {
                "provider": "internal",
                "currency": currency_code,
                "card_type": card_type,
                "card_brand": card_brand,
                "test_mode": self.test_mode,
                "created_by": user_email,
                "phone": user_phone,
                "billing_address": billing_address,
                "created_at": time.time(),
            },
        }

    async def get_card_details(self, provider_card_id: str) -> Dict[str, Any]:
        """
        Get card details.

        For internal provider, we return mock data since we don't store
        card details externally.
        """
        await asyncio.sleep(0.05)

        return {
            "card_id": provider_card_id,
            "status": "active",
            "card_type": "virtual",
            "currency": "USD",
            "balance": Decimal("0.00"),
            "masked_number": "****  ****  ****  1234",
        }

    async def freeze_card(self, provider_card_id: str) -> bool:
        """
        Freeze a card.

        For internal cards, this is a no-op since card status
        is managed by the Card model directly.
        """
        await asyncio.sleep(0.05)
        return True

    async def unfreeze_card(self, provider_card_id: str) -> bool:
        """
        Unfreeze a card.

        For internal cards, this is a no-op since card status
        is managed by the Card model directly.
        """
        await asyncio.sleep(0.05)
        return True

    async def block_card(self, provider_card_id: str) -> bool:
        """
        Permanently block a card.

        For internal cards, this is a no-op since card status
        is managed by the Card model directly.
        """
        await asyncio.sleep(0.05)
        return True

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        """
        Verify webhook signature.

        Internal cards don't receive external webhooks, so this always returns True.
        All transactions are handled via API calls, not webhooks.
        """
        return True

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse webhook event.

        Internal cards don't receive webhooks. This method is included for
        interface compliance but should not be called in practice.
        """
        return {
            "event_type": payload.get("event_type", "internal.transaction"),
            "card_id": payload.get("card_id"),
            "transaction_type": payload.get("transaction_type"),
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "merchant_name": payload.get("merchant_name"),
            "merchant_category": payload.get("merchant_category"),
            "location": payload.get("location"),
            "external_reference": payload.get("reference"),
            "metadata": payload,
        }

    def supports_currency(self, currency_code: str) -> bool:
        """Check if currency is supported."""
        return currency_code.upper() in self.SUPPORTED_CURRENCIES

    def supports_card_type(self, card_type: str) -> bool:
        """Check if card type is supported."""
        return card_type.lower() in self.SUPPORTED_CARD_TYPES

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "internal"

    def calculate_card_fee(self, amount: Decimal, transaction_type: str) -> Decimal:
        """Internal provider has no fees."""
        return Decimal("0")
