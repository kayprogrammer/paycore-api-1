from typing import Optional
from django.conf import settings

from .base import BaseAccountProvider
from .internal import InternalAccountProvider
from .paystack import PaystackAccountProvider
from apps.wallets.models import AccountProvider
from apps.common.exceptions import BodyValidationError


class AccountProviderFactory:
    """
    Factory for creating account provider instances.

    This factory implements the Factory Design Pattern to create appropriate
    provider instances based on currency and configuration.

    Strategy:
    1. NGN → Paystack (if enabled) or Internal (fallback)
    2. USD/EUR/GBP → Internal
    3. Other currencies → Internal

    Usage:
        provider = AccountProviderFactory.get_provider_for_currency("NGN", test_mode=True)
        account_data = await provider.create_account(...)
    """

    # Provider configuration: currency → provider mapping
    CURRENCY_PROVIDER_MAP = {
        "NGN": AccountProvider.PAYSTACK,  # Use Paystack for NGN
        "USD": AccountProvider.INTERNAL,  # Use internal for USD
        "EUR": AccountProvider.INTERNAL,  # Use internal for EUR
        "GBP": AccountProvider.INTERNAL,  # Use internal for GBP
    }

    @classmethod
    def get_provider_for_currency(
        cls, currency_code: str, test_mode: bool = False
    ) -> BaseAccountProvider:
        """
        Get appropriate provider for a currency.

        Args:
            currency_code: Currency code (NGN, USD, EUR, GBP, etc.)
            test_mode: If True, use sandbox/test mode

        Returns:
            BaseAccountProvider: Provider instance

        Raises:
            ValidationError: If currency is not supported
        """
        currency_code = currency_code.upper()

        # Check if internal provider should be used globally
        use_internal = getattr(settings, "USE_INTERNAL_PROVIDER", False)
        if use_internal:
            return cls.get_provider(AccountProvider.INTERNAL, test_mode)

        # Get configured provider for this currency
        provider_type = cls.CURRENCY_PROVIDER_MAP.get(
            currency_code, AccountProvider.INTERNAL
        )

        # Check if Paystack is enabled in settings
        if provider_type == AccountProvider.PAYSTACK:
            if not cls._is_paystack_enabled():
                # Fallback to internal if Paystack not configured
                provider_type = AccountProvider.INTERNAL

        return cls.get_provider(provider_type, test_mode)

    @classmethod
    def get_provider(
        cls, provider_type: str, test_mode: bool = False
    ) -> BaseAccountProvider:
        provider_map = {
            AccountProvider.INTERNAL: InternalAccountProvider,
            AccountProvider.PAYSTACK: PaystackAccountProvider,
            # Future providers
            # AccountProvider.FLUTTERWAVE: FlutterwaveAccountProvider,
            # AccountProvider.WISE: WiseAccountProvider,
        }

        provider_class = provider_map.get(provider_type)

        if not provider_class:
            raise BodyValidationError(
                "provider",
                f"Provider '{provider_type}' is not implemented. "
                f"Available providers: {list(provider_map.keys())}",
            )

        return provider_class(test_mode=test_mode)

    @classmethod
    def _is_paystack_enabled(cls) -> bool:
        test_key = getattr(settings, "PAYSTACK_TEST_SECRET_KEY", None)
        live_key = getattr(settings, "PAYSTACK_LIVE_SECRET_KEY", None)
        return bool(test_key or live_key)

    @classmethod
    def get_supported_currencies(cls) -> dict:
        return cls.CURRENCY_PROVIDER_MAP.copy()

    @classmethod
    def add_currency_provider(cls, currency_code: str, provider_type: str) -> None:
        cls.CURRENCY_PROVIDER_MAP[currency_code.upper()] = provider_type

    @classmethod
    def get_test_mode_setting(cls) -> bool:
        return getattr(settings, "PAYMENT_PROVIDERS_TEST_MODE", True)
