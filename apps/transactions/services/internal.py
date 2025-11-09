import asyncio
import time
from typing import Dict, Any
from decimal import Decimal
from django.conf import settings

from .base import BaseDepositProvider


class InternalDepositProvider(BaseDepositProvider):
    """
    Internal deposit provider for development and testing purposes.

    This provider simulates deposits without external payment gateway.
    Perfect for:
    - Development when payment gateways are not configured
    - Testing deposit workflows without real transactions
    - Automated testing and CI/CD pipelines

    Features:
    - Instant deposit completion (no external payment required)
    - Supports all major currencies
    - No transaction fees
    - No external dependencies

    Note: This should only be used in development/test environments.
    For production, use real payment providers (Paystack, Flutterwave, etc.)
    """

    SUPPORTED_CURRENCIES = [
        # Fiat Currencies (African)
        "NGN",  # Nigerian Naira
        "KES",  # Kenyan Shilling
        "GHS",  # Ghanaian Cedi
        "ZAR",  # South African Rand
        "EGP",  # Egyptian Pound
        # Fiat Currencies (Major)
        "USD",  # US Dollar
        "EUR",  # Euro
        "GBP",  # British Pound
        "CAD",  # Canadian Dollar
        "AUD",  # Australian Dollar
        # Cryptocurrencies
        "BTC",  # Bitcoin
        "ETH",  # Ethereum
        "USDT",  # Tether
        "USDC",  # USD Coin
        "BNB",  # Binance Coin
    ]

    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)

    def _generate_provider_reference(self) -> str:
        """Generate a mock provider reference"""
        timestamp = int(time.time())
        return f"INT_DEP_{timestamp}"

    async def initiate_deposit(
        self,
        user_email: str,
        user_first_name: str,
        user_last_name: str,
        amount: Decimal,
        currency_code: str,
        reference: str,
        callback_url: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Initiate internal deposit.

        If USE_INTERNAL_PROVIDER is True, returns pending status and
        schedules auto-confirmation after 15 seconds via Celery.
        Otherwise, completes instantly.
        """
        # Add small delay to simulate processing
        await asyncio.sleep(0.1)

        provider_reference = self._generate_provider_reference()

        # Check if we should use delayed auto-confirmation
        use_internal_provider = getattr(settings, "USE_INTERNAL_PROVIDER", False)

        if use_internal_provider:
            # Return pending status - will be auto-confirmed after 15 seconds
            return {
                "reference": reference,
                "provider_reference": provider_reference,
                "payment_url": None,  # No external payment required
                "access_code": None,
                "status": "pending",  # Pending - will be confirmed by Celery task
                "amount": amount,
                "currency": currency_code,
                "channel": "internal",
                "metadata": {
                    "provider": "internal",
                    "test_mode": self.test_mode,
                    "auto_confirm": True,
                    "message": "Internal deposit - will be auto-confirmed in 15 seconds",
                },
            }
        else:
            # Instant completion for non-USE_INTERNAL_PROVIDER environments
            return {
                "reference": reference,
                "provider_reference": provider_reference,
                "payment_url": None,  # No external payment required
                "access_code": None,
                "status": "completed",  # Instantly completed
                "amount": amount,
                "currency": currency_code,
                "channel": "internal",
                "paid_at": time.time(),
                "metadata": {
                    "provider": "internal",
                    "test_mode": self.test_mode,
                    "auto_completed": True,
                    "message": "Internal deposit - automatically completed for testing",
                },
            }

    async def verify_deposit(self, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Verify internal deposit (always returns success).

        Args:
            reference: Transaction reference

        Returns:
            Success status for any internal deposit
        """
        await asyncio.sleep(0.05)

        return {
            "status": "success",
            "reference": reference,
            "provider_reference": self._generate_provider_reference(),
            "amount": Decimal("0"),  # Amount unknown in verification
            "currency": "NGN",
            "paid_at": time.time(),
            "channel": "internal",
            "customer_email": "test@example.com",
            "metadata": {
                "provider": "internal",
                "verified": True,
            },
        }

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        """
        Verify webhook signature (internal provider doesn't use webhooks).

        Returns:
            Always True for internal provider
        """
        return True

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse webhook event (internal provider doesn't receive webhooks).

        Args:
            payload: Raw webhook payload

        Returns:
            Standardized event format
        """
        return {
            "event_type": "charge.success",
            "reference": payload.get("reference", ""),
            "status": "success",
            "amount": Decimal(str(payload.get("amount", 0))),
            "currency": payload.get("currency", "NGN"),
            "paid_at": time.time(),
            "metadata": payload,
        }

    def supports_currency(self, currency_code: str) -> bool:
        """Check if currency is supported."""
        return currency_code.upper() in self.SUPPORTED_CURRENCIES

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "internal"

    def calculate_deposit_fee(self, amount: Decimal) -> Decimal:
        """Internal provider has no fees."""
        return Decimal("0")
