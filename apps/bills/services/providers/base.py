from abc import ABC, abstractmethod
from typing import Dict, Any
from decimal import Decimal


class BaseBillPaymentProvider(ABC):
    """
    Abstract base class for bill payment providers.

    This abstraction allows for easy switching between different bill payment gateways
    (Flutterwave, Paystack, VTPass, Baxi, etc.) while maintaining a consistent interface.

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
    async def validate_customer(
        self, provider_code: str, customer_id: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Validate customer details before payment.

        Args:
            provider_code: Provider's service code (e.g., "ekedc-electric", "dstv")
            customer_id: Customer ID/number (meter number, smartcard, phone)
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict containing:
                - is_valid: bool
                - customer_name: str
                - customer_id: str
                - customer_type: Optional[str]
                - address: Optional[str]
                - balance: Optional[str] (for prepaid meters)
                - extra_info: Dict[str, Any]

        Raises:
            ValidationError: If validation fails
            RequestError: If API request fails
        """
        pass

    @abstractmethod
    async def process_payment(
        self,
        provider_code: str,
        customer_id: str,
        amount: Decimal,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process bill payment.

        Args:
            provider_code: Provider's service code
            customer_id: Customer ID/number
            amount: Payment amount
            reference: Unique payment reference
            **kwargs: Additional parameters (email, phone, package_code, etc.)

        Returns:
            Dict containing:
                - success: bool
                - provider_reference: str
                - token: Optional[str] (for electricity, etc.)
                - token_units: Optional[str]
                - customer_name: str
                - amount: Decimal
                - fee: Decimal
                - message: str
                - extra_data: Dict[str, Any]

        Raises:
            RequestError: If payment fails
            InsufficientFundsError: If insufficient balance
        """
        pass

    @abstractmethod
    async def query_transaction(self, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Query transaction status.

        Args:
            reference: Payment reference
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict containing:
                - status: str (success, failed, pending)
                - provider_reference: str
                - amount: Decimal
                - customer_id: str
                - customer_name: str
                - token: Optional[str]
                - message: str

        Raises:
            NotFoundError: If transaction not found
            RequestError: If query fails
        """
        pass

    @abstractmethod
    def get_available_services(self) -> Dict[str, list]:
        """
        Get list of available services from provider.

        Returns:
            Dict with categories as keys and list of services:
            {
                "airtime": [...],
                "data": [...],
                "electricity": [...],
                "cable_tv": [...]
            }
        """
        pass

    @abstractmethod
    def get_data_bundles(self, provider_code: str) -> list:
        """
        Get available data bundles for a telecom provider.

        Args:
            provider_code: Telecom provider code (e.g., "mtn", "airtel")

        Returns:
            List of data bundles with name, code, amount, validity
        """
        pass

    @abstractmethod
    def get_cable_packages(self, provider_code: str) -> list:
        """
        Get available cable TV packages.

        Args:
            provider_code: Cable provider code (e.g., "dstv", "gotv")

        Returns:
            List of cable packages with name, code, amount, validity
        """
        pass

    @abstractmethod
    def supports_category(self, category: str) -> bool:
        """
        Check if provider supports a bill category.

        Args:
            category: Bill category (airtime, data, electricity, etc.)

        Returns:
            bool: True if category is supported
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get provider name.

        Returns:
            str: Provider name (e.g., "flutterwave", "paystack", "vtpass")
        """
        pass

    def calculate_provider_fee(self, amount: Decimal, service_type: str) -> Decimal:
        """
        Calculate provider's transaction fee.

        Default implementation returns 0 (no fee).
        Override in specific providers if they charge fees.

        Args:
            amount: Transaction amount
            service_type: Type of service

        Returns:
            Decimal: Fee amount
        """
        return Decimal("0")

    def is_test_mode(self) -> bool:
        """Check if provider is in test/sandbox mode."""
        return self.test_mode
