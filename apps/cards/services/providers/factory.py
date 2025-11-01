from typing import Optional
from django.conf import settings

from .base import BaseCardProvider
from .internal import InternalCardProvider
from .flutterwave import FlutterwaveCardProvider
from .sudo import SudoCardProvider
from apps.cards.models import CardProvider
from apps.common.exceptions import BodyValidationError


class CardProviderFactory:
    """
    Factory for creating card provider instances.

    This factory implements the Factory Design Pattern to create appropriate
    provider instances based on currency and configuration.

    Strategy:
    1. USD → Flutterwave (if configured) → Sudo (if configured) → Internal (fallback)
    2. NGN → Flutterwave (if configured) → Sudo (if configured) → Internal (fallback)
    3. GBP → Flutterwave (if configured) → Internal (fallback)
    4. Other currencies → Internal (fallback)

    The Internal provider serves as a universal fallback when external providers
    are unavailable or not configured, allowing development to continue without
    external dependencies.

    Usage:
        provider = CardProviderFactory.get_provider_for_currency("USD", test_mode=True)
        card_data = await provider.create_card(...)
    """

    # Provider configuration: currency → provider mapping
    # You can customize this based on your preference
    CURRENCY_PROVIDER_MAP = {
        "USD": CardProvider.FLUTTERWAVE,  # Use Flutterwave for USD
        "NGN": CardProvider.FLUTTERWAVE,  # Use Flutterwave for NGN
        "GBP": CardProvider.FLUTTERWAVE,  # Use Flutterwave for GBP
        # EUR: No provider supports EUR cards yet
    }

    @classmethod
    def get_provider_for_currency(
        cls, currency_code: str, test_mode: bool = False
    ) -> BaseCardProvider:
        currency_code = currency_code.upper()

        # Check if internal provider should be used globally
        use_internal = getattr(settings, "USE_INTERNAL_PROVIDER", False)
        if use_internal:
            return cls.get_provider(CardProvider.INTERNAL, test_mode)

        # Get configured provider for this currency
        provider_type = cls.CURRENCY_PROVIDER_MAP.get(currency_code)

        if not provider_type:
            # Fallback to internal provider for unsupported currencies
            provider_type = CardProvider.INTERNAL

        # Check if provider is enabled in settings
        if provider_type == CardProvider.FLUTTERWAVE:
            if not cls._is_flutterwave_enabled():
                # Fallback to Sudo if available
                if currency_code in ["USD", "NGN"] and cls._is_sudo_enabled():
                    provider_type = CardProvider.SUDO
                else:
                    # Fallback to internal provider
                    provider_type = CardProvider.INTERNAL
        elif provider_type == CardProvider.SUDO:
            if not cls._is_sudo_enabled():
                # Fallback to internal provider
                provider_type = CardProvider.INTERNAL

        return cls.get_provider(provider_type, test_mode)

    @classmethod
    def get_provider(
        cls, provider_type: str, test_mode: bool = False
    ) -> BaseCardProvider:
        """
        Get provider instance by provider type.

        Args:
            provider_type: Provider type (flutterwave, sudo, stripe, paystack)
            test_mode: If True, use sandbox/test mode

        Returns:
            BaseCardProvider: Provider instance

        Raises:
            ValidationError: If provider type is invalid or not implemented
        """
        provider_map = {
            CardProvider.INTERNAL: InternalCardProvider,
            CardProvider.FLUTTERWAVE: FlutterwaveCardProvider,
            CardProvider.SUDO: SudoCardProvider,
            # Future providers
            # CardProvider.STRIPE: StripeCardProvider,
            # CardProvider.PAYSTACK: PaystackCardProvider,
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
    def _is_flutterwave_enabled(cls) -> bool:
        test_key = getattr(settings, "FLUTTERWAVE_TEST_SECRET_KEY", None)
        live_key = getattr(settings, "FLUTTERWAVE_LIVE_SECRET_KEY", None)
        return bool(test_key or live_key)

    @classmethod
    def _is_sudo_enabled(cls) -> bool:
        test_key = getattr(settings, "SUDO_TEST_SECRET_KEY", None)
        live_key = getattr(settings, "SUDO_LIVE_SECRET_KEY", None)
        return bool(test_key or live_key)

    @classmethod
    def get_supported_currencies(cls) -> dict:
        return cls.CURRENCY_PROVIDER_MAP.copy()

    @classmethod
    def add_currency_provider(cls, currency_code: str, provider_type: str) -> None:
        cls.CURRENCY_PROVIDER_MAP[currency_code.upper()] = provider_type

    @classmethod
    def get_test_mode_setting(cls) -> bool:
        return getattr(settings, "CARD_PROVIDERS_TEST_MODE", True)

    @classmethod
    def get_available_providers(cls) -> list:
        available = []

        if cls._is_flutterwave_enabled():
            available.append("flutterwave")

        if cls._is_sudo_enabled():
            available.append("sudo")

        return available
