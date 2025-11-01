from abc import ABC, abstractmethod
from typing import Dict, Any
from decimal import Decimal


class BaseDepositProvider(ABC):
    """
    Abstract base class for deposit payment providers.

    This abstraction allows for easy switching between different payment gateways
    (Internal, Paystack, Flutterwave, Stripe, etc.) while maintaining a consistent interface.

    Principles:
    - Single Responsibility: Each provider handles only its own integration
    - Open/Closed: Open for extension (new providers), closed for modification
    - Liskov Substitution: All providers can be used interchangeably
    - Dependency Inversion: Code depends on abstraction, not concrete implementations
    """

    def __init__(self, test_mode: bool = False):
        """
        Initialize provider with test/production mode.

        Args:
            test_mode: If True, use sandbox/test credentials. If False, use production.
        """
        self.test_mode = test_mode

    @abstractmethod
    async def initiate_deposit(
        self,
        user_email: str,
        user_first_name: str,
        user_last_name: str,
        amount: Decimal,
        currency_code: str,
        reference: str,
        callback_url: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Initiate a deposit transaction.

        Args:
            user_email: User's email address
            user_first_name: User's first name
            user_last_name: User's last name
            amount: Deposit amount
            currency_code: Currency code (NGN, USD, EUR, GBP, etc.)
            reference: Unique transaction reference
            callback_url: URL to redirect user after payment
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict containing:
                - reference: Payment reference
                - payment_url: URL for user to complete payment (None for internal)
                - status: Payment status (pending, completed, failed)
                - provider_reference: Provider's internal reference
                - access_code: Payment access code (for some providers)
                - metadata: Additional provider-specific data

        Raises:
            RequestError: If initiation fails
            ValidationError: If input validation fails
        """
        pass

    @abstractmethod
    async def verify_deposit(self, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Verify deposit transaction status.

        Args:
            reference: Transaction reference
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict containing:
                - status: Transaction status (success, pending, failed)
                - amount: Transaction amount
                - currency: Currency code
                - paid_at: Payment timestamp
                - channel: Payment channel used
                - customer_email: Customer email
                - provider_reference: Provider's reference
                - metadata: Additional transaction data

        Raises:
            NotFoundError: If transaction not found
            RequestError: If verification fails
        """
        pass

    @abstractmethod
    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        """
        Verify webhook signature from provider.

        Args:
            payload: Raw webhook payload (bytes)
            signature: Signature header from webhook
            **kwargs: Additional provider-specific parameters

        Returns:
            bool: True if signature is valid
        """
        pass

    @abstractmethod
    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse webhook event into standardized format.

        Args:
            payload: Raw webhook payload

        Returns:
            Dict containing:
                - event_type: Type of event (charge.success, etc.)
                - reference: Transaction reference
                - status: Transaction status
                - amount: Transaction amount
                - currency: Currency code
                - paid_at: Payment timestamp
                - metadata: Additional event data
        """
        pass

    @abstractmethod
    def supports_currency(self, currency_code: str) -> bool:
        """
        Check if provider supports a specific currency.

        Args:
            currency_code: Currency code (NGN, USD, EUR, GBP, etc.)

        Returns:
            bool: True if currency is supported
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get provider name.

        Returns:
            str: Provider name (e.g., "internal", "paystack", "flutterwave")
        """
        pass

    def calculate_deposit_fee(self, amount: Decimal) -> Decimal:
        """
        Calculate transaction fee for this provider.

        Default implementation returns 0 (no fee).
        Override in specific providers if they charge fees.

        Args:
            amount: Transaction amount

        Returns:
            Decimal: Fee amount
        """
        return Decimal("0")

    def is_test_mode(self) -> bool:
        """Check if provider is in test/sandbox mode."""
        return self.test_mode
