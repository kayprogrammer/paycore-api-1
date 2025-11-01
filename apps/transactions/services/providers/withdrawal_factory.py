from django.conf import settings

from apps.transactions.services.providers.base_withdrawal import BaseWithdrawalProvider
from apps.transactions.services.providers.internal_withdrawal import (
    InternalWithdrawalProvider,
)
from apps.transactions.services.providers.paystack_withdrawal import (
    PaystackWithdrawalProvider,
)
from apps.common.exceptions import RequestError, ErrorCode


class WithdrawalProviderFactory:
    """
    Factory for creating withdrawal provider instances.

    Handles provider selection based on:
    - Currency
    - USE_INTERNAL_PROVIDER setting
    - Provider availability
    """

    # Map currencies to their default withdrawal providers
    CURRENCY_PROVIDER_MAP = {
        "NGN": "paystack",  # Nigerian Naira -> Paystack
        "KES": "internal",  # Kenyan Shilling -> Internal (future: Flutterwave)
        "GHS": "internal",  # Ghanaian Cedi -> Internal (future: Flutterwave)
        "ZAR": "internal",  # South African Rand -> Internal (future: Flutterwave)
        "USD": "internal",  # US Dollar -> Internal (future: Stripe)
    }

    @classmethod
    def get_provider_for_currency(
        cls, currency_code: str, test_mode: bool = False
    ) -> BaseWithdrawalProvider:
        """
        Get appropriate withdrawal provider for currency.

        Args:
            currency_code: Currency code (NGN, USD, etc.)
            test_mode: Whether to use test mode

        Returns:
            BaseWithdrawalProvider instance

        Raises:
            RequestError: If no provider available for currency
        """
        currency_code = currency_code.upper()

        # Check if internal provider should be used globally
        use_internal = getattr(settings, "USE_INTERNAL_PROVIDER", False)
        if use_internal:
            return InternalWithdrawalProvider(test_mode=test_mode)

        # Get configured provider for this currency
        provider_name = cls.CURRENCY_PROVIDER_MAP.get(currency_code)

        if not provider_name:
            raise RequestError(
                ErrorCode.UNSUPPORTED_OPERATION,
                f"Withdrawals not supported for currency: {currency_code}",
            )

        # Return appropriate provider
        if provider_name == "paystack":
            if cls._is_paystack_enabled():
                return PaystackWithdrawalProvider(test_mode=test_mode)
            else:
                # Fallback to internal if Paystack not configured
                return InternalWithdrawalProvider(test_mode=test_mode)

        # Default to internal provider
        return InternalWithdrawalProvider(test_mode=test_mode)

    @classmethod
    def get_provider(
        cls, provider_name: str, test_mode: bool = False
    ) -> BaseWithdrawalProvider:
        """
        Get specific withdrawal provider by name.

        Args:
            provider_name: Provider name (internal, paystack, etc.)
            test_mode: Whether to use test mode

        Returns:
            BaseWithdrawalProvider instance

        Raises:
            RequestError: If provider not found
        """
        provider_name = provider_name.lower()

        if provider_name == "internal":
            return InternalWithdrawalProvider(test_mode=test_mode)
        elif provider_name == "paystack":
            if cls._is_paystack_enabled():
                return PaystackWithdrawalProvider(test_mode=test_mode)
            else:
                raise RequestError(
                    ErrorCode.CONFIGURATION_ERROR,
                    "Paystack provider not configured",
                )
        else:
            raise RequestError(
                ErrorCode.VALIDATION_ERROR,
                f"Unknown withdrawal provider: {provider_name}",
            )

    @classmethod
    def _is_paystack_enabled(cls) -> bool:
        """Check if Paystack is configured."""
        test_key = getattr(settings, "PAYSTACK_TEST_SECRET_KEY", "")
        live_key = getattr(settings, "PAYSTACK_LIVE_SECRET_KEY", "")
        return bool(test_key or live_key)

    @classmethod
    def get_test_mode_setting(cls) -> bool:
        """Get global test mode setting."""
        return getattr(settings, "PAYMENT_TEST_MODE", True)

    @classmethod
    def get_supported_currencies(cls) -> list:
        """Get list of supported currencies for withdrawals."""
        return list(cls.CURRENCY_PROVIDER_MAP.keys())
