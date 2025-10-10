from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from decimal import Decimal


class BaseCardProvider(ABC):
    """
    Abstract base class for card providers.

    This abstraction allows for easy switching between different card providers
    (Flutterwave, Sudo, Stripe, etc.) while maintaining a consistent interface.

    Principles:
    - Single Responsibility: Each provider handles only its own integration
    - Open/Closed: Open for extension (new providers), closed for modification
    - Liskov Substitution: All providers can be used interchangeably
    - Dependency Inversion: Code depends on abstraction, not concrete implementations
    """

    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode

    @abstractmethod
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
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a virtual or physical card.

        Args:
            user_email: User's email address
            user_first_name: User's first name
            user_last_name: User's last name
            user_phone: User's phone number
            currency_code: Card currency (USD, NGN, EUR, GBP)
            card_type: Type of card (virtual, physical)
            card_brand: Card brand (visa, mastercard, verve)
            billing_address: Billing address details
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict containing:
                - card_number: The card number (encrypted/tokenized)
                - card_holder_name: Cardholder name
                - expiry_month: Expiry month (1-12)
                - expiry_year: Expiry year
                - cvv: Card CVV (encrypted)
                - provider_card_id: Provider's internal card ID
                - provider_metadata: Additional provider-specific data
                - masked_number: Masked card number for display

        Raises:
            RequestError: If card creation fails
            ValidationError: If input validation fails
        """
        pass

    @abstractmethod
    async def get_card_details(self, provider_card_id: str) -> Dict[str, Any]:
        """
        Get card details from provider.

        Args:
            provider_card_id: Provider's internal card ID

        Returns:
            Dict containing card details

        Raises:
            NotFoundError: If card not found
            RequestError: If request fails
        """
        pass

    @abstractmethod
    async def freeze_card(self, provider_card_id: str) -> bool:
        """
        Freeze a card (temporary block).

        Args:
            provider_card_id: Provider's internal card ID

        Returns:
            bool: True if successful

        Raises:
            NotFoundError: If card not found
            RequestError: If freeze fails
        """
        pass

    @abstractmethod
    async def unfreeze_card(self, provider_card_id: str) -> bool:
        """
        Unfreeze a previously frozen card.

        Args:
            provider_card_id: Provider's internal card ID

        Returns:
            bool: True if successful

        Raises:
            NotFoundError: If card not found
            RequestError: If unfreeze fails
        """
        pass

    @abstractmethod
    async def block_card(self, provider_card_id: str) -> bool:
        """
        Permanently block/terminate a card.

        Args:
            provider_card_id: Provider's internal card ID

        Returns:
            bool: True if successful

        Raises:
            NotFoundError: If card not found
            RequestError: If block fails
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
                - event_type: Type of event (transaction.success, card.created, etc.)
                - card_id: Provider's card ID
                - transaction_type: Type of transaction (purchase, withdrawal, refund)
                - amount: Transaction amount
                - currency: Transaction currency
                - merchant_name: Merchant name
                - merchant_category: Merchant category
                - location: Transaction location
                - external_reference: Provider's transaction reference
                - metadata: Additional event data
        """
        pass

    @abstractmethod
    def supports_currency(self, currency_code: str) -> bool:
        """
        Check if provider supports a specific currency.

        Args:
            currency_code: Currency code (USD, NGN, EUR, GBP, etc.)

        Returns:
            bool: True if currency is supported
        """
        pass

    @abstractmethod
    def supports_card_type(self, card_type: str) -> bool:
        """
        Check if provider supports a specific card type.

        Args:
            card_type: Card type (virtual, physical)

        Returns:
            bool: True if card type is supported
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get provider name.

        Returns:
            str: Provider name (e.g., "flutterwave", "sudo", "stripe")
        """
        pass

    def calculate_card_fee(self, amount: Decimal, transaction_type: str) -> Decimal:
        """
        Calculate transaction fee for this provider.

        Default implementation returns 0 (no fee).
        Override in specific providers if they charge fees.

        Args:
            amount: Transaction amount
            transaction_type: Type of transaction

        Returns:
            Decimal: Fee amount
        """
        return Decimal("0")

    def is_test_mode(self) -> bool:
        """Check if provider is in test/sandbox mode."""
        return self.test_mode
