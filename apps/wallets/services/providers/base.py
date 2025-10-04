from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from decimal import Decimal


class BaseAccountProvider(ABC):
    """
    Abstract base class for virtual account providers.

    This abstraction allows for easy switching between different payment providers
    (Paystack, Flutterwave, Wise, etc.) while maintaining a consistent interface.

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
    async def create_account(
        self,
        user_email: str,
        user_first_name: str,
        user_last_name: str,
        user_phone: Optional[str],
        currency_code: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a virtual account for a user.

        Args:
            user_email: User's email address
            user_first_name: User's first name
            user_last_name: User's last name
            user_phone: User's phone number (optional)
            currency_code: Currency code (NGN, USD, EUR, GBP, etc.)
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict containing:
                - account_number: The generated account number
                - account_name: The account holder name
                - bank_name: The bank name
                - provider_account_id: Provider's internal account ID
                - provider_metadata: Additional provider-specific data

        Raises:
            RequestError: If account creation fails
            ValidationError: If input validation fails
        """
        pass

    @abstractmethod
    async def verify_account(self, provider_account_id: str) -> Dict[str, Any]:
        """
        Verify an account exists and get its details.

        Args:
            provider_account_id: Provider's internal account ID

        Returns:
            Dict containing account details

        Raises:
            NotFoundError: If account not found
            RequestError: If verification fails
        """
        pass

    @abstractmethod
    async def deactivate_account(self, provider_account_id: str) -> bool:
        """
        Deactivate/close a virtual account.

        Args:
            provider_account_id: Provider's internal account ID

        Returns:
            bool: True if successful

        Raises:
            NotFoundError: If account not found
            RequestError: If deactivation fails
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
                - event_type: Type of event (payment.success, etc.)
                - account_number: Account that received payment
                - amount: Amount received
                - sender_account_number: Sender's account number
                - sender_account_name: Sender's account name
                - sender_bank_name: Sender's bank name
                - external_reference: Provider's transaction reference
                - currency_code: Currency code
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
            str: Provider name (e.g., "paystack", "flutterwave", "wise")
        """
        pass

    def calculate_deposit_fee(self, amount: Decimal) -> Decimal:
        """
        Calculate deposit fee for this provider.

        Default implementation returns 0 (no fee).
        Override in specific providers if they charge fees.

        Args:
            amount: Deposit amount

        Returns:
            Decimal: Fee amount
        """
        return Decimal("0")

    def is_test_mode(self) -> bool:
        """Check if provider is in test/sandbox mode."""
        return self.test_mode
