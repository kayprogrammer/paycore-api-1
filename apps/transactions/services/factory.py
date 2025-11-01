from typing import Optional
from django.conf import settings

from .base import BaseDepositProvider
from .internal import InternalDepositProvider
from .paystack import PaystackDepositProvider
from apps.common.exceptions import BodyValidationError


class DepositProviderFactory:
    """
    Factory for creating deposit provider instances.

    This factory implements the Factory Design Pattern to create appropriate
    provider instances based on currency and configuration.

    Strategy:
    1. If USE_INTERNAL_PROVIDER=True → Always use Internal provider
    2. NGN → Paystack (if configured) → Internal (fallback)
    3. Other currencies → Internal

    The Internal provider serves as a universal fallback for development
    and testing without external dependencies.

    Usage:
        provider = DepositProviderFactory.get_provider_for_currency("NGN", test_mode=True)
        result = await provider.initiate_deposit(...)
    """

    # Provider configuration: currency → provider mapping
    CURRENCY_PROVIDER_MAP = {
        "NGN": "paystack",  # Use Paystack for NGN
        # Future: Add more currency providers
        # "USD": "stripe",
        # "EUR": "stripe",
        # "GBP": "stripe",
    }

    @classmethod
    def get_provider_for_currency(
        cls, currency_code: str, test_mode: bool = False
    ) -> BaseDepositProvider:
        """
        Get appropriate deposit provider for a currency.

        Args:
            currency_code: Currency code (NGN, USD, EUR, GBP, etc.)
            test_mode: If True, use sandbox/test mode

        Returns:
            BaseDepositProvider: Provider instance

        Priority:
            1. If USE_INTERNAL_PROVIDER=True → Internal
            2. If external provider configured → External
            3. Fallback → Internal
        """
        currency_code = currency_code.upper()

        # Check if internal provider should be used globally
        use_internal = getattr(settings, "USE_INTERNAL_PROVIDER", False)
        if use_internal:
            return InternalDepositProvider(test_mode=test_mode)

        # Get configured provider for this currency
        provider_name = cls.CURRENCY_PROVIDER_MAP.get(currency_code)

        if provider_name == "paystack":
            if cls._is_paystack_enabled():
                return PaystackDepositProvider(test_mode=test_mode)
            else:
                # Fallback to internal if Paystack not configured
                return InternalDepositProvider(test_mode=test_mode)

        # Default fallback: Internal provider
        return InternalDepositProvider(test_mode=test_mode)

    @classmethod
    def get_provider(
        cls, provider_name: str, test_mode: bool = False
    ) -> BaseDepositProvider:
        """
        Get provider instance by name.

        Args:
            provider_name: Provider name ("internal", "paystack", etc.)
            test_mode: If True, use sandbox/test mode

        Returns:
            BaseDepositProvider: Provider instance

        Raises:
            BodyValidationError: If provider name is invalid
        """
        provider_map = {
            "internal": InternalDepositProvider,
            "paystack": PaystackDepositProvider,
            # Future providers:
            # "flutterwave": FlutterwaveDepositProvider,
            # "stripe": StripeDepositProvider,
        }

        provider_class = provider_map.get(provider_name.lower())

        if not provider_class:
            raise BodyValidationError(
                "provider",
                f"Provider '{provider_name}' is not implemented. "
                f"Available providers: {list(provider_map.keys())}",
            )

        return provider_class(test_mode=test_mode)

    @classmethod
    def _is_paystack_enabled(cls) -> bool:
        """Check if Paystack is configured."""
        test_key = getattr(settings, "PAYSTACK_TEST_SECRET_KEY", None)
        live_key = getattr(settings, "PAYSTACK_LIVE_SECRET_KEY", None)
        return bool(test_key or live_key)

    @classmethod
    def get_supported_currencies(cls) -> dict:
        """Get supported currencies mapping."""
        return cls.CURRENCY_PROVIDER_MAP.copy()

    @classmethod
    def get_test_mode_setting(cls) -> bool:
        """Get test mode setting from Django settings."""
        return getattr(settings, "PAYMENT_PROVIDERS_TEST_MODE", True)
