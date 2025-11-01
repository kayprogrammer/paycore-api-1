import random
import time
from typing import Dict, Any
from decimal import Decimal

from .base import BaseBillPaymentProvider


class InternalBillPaymentProvider(BaseBillPaymentProvider):
    """
    Internal bill payment provider for development and fallback purposes.

    This provider simulates bill payments without making external API calls.
    Perfect for:
    - Development when external bill payment providers are not available
    - Testing bill payment workflows without incurring costs
    - Fallback when external providers have issues

    Features:
    - Validates customer IDs (mock validation)
    - Simulates successful bill payments
    - Generates realistic tokens for electricity/cable
    - Supports all bill categories
    - No external dependencies

    Categories supported: airtime, data, electricity, cable_tv, internet, betting
    """

    SUPPORTED_CATEGORIES = [
        "airtime",
        "data",
        "electricity",
        "cable_tv",
        "internet",
        "betting",
        "education",
        "insurance",
    ]

    # Mock services for different categories
    MOCK_SERVICES = {
        "airtime": ["mtn", "airtel", "glo", "9mobile"],
        "data": ["mtn-data", "airtel-data", "glo-data", "9mobile-data"],
        "electricity": ["ekedc", "ikedc", "aedc", "phed", "ibadan-electric"],
        "cable_tv": ["dstv", "gotv", "startimes", "showmax"],
        "internet": ["spectranet", "smile", "swift"],
        "betting": ["bet9ja", "sportybet", "1xbet", "betway"],
    }

    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)

    def _generate_token(self, amount: Decimal) -> str:
        """Generate a mock token for electricity/cable"""
        # Token format: XXXX-XXXX-XXXX-XXXX
        parts = []
        for _ in range(4):
            part = "".join([str(random.randint(0, 9)) for _ in range(4)])
            parts.append(part)
        return "-".join(parts)

    def _generate_provider_reference(self) -> str:
        """Generate a mock provider reference"""
        timestamp = int(time.time())
        random_suffix = random.randint(100000, 999999)
        return f"INT{timestamp}{random_suffix}"

    def _generate_customer_name(self, customer_id: str) -> str:
        """Generate a mock customer name"""
        first_names = ["John", "Jane", "Ahmed", "Fatima", "Chidi", "Amaka", "Tunde", "Bola"]
        last_names = ["Smith", "Doe", "Mohammed", "Ibrahim", "Okafor", "Adeyemi", "Williams"]
        return f"{random.choice(first_names)} {random.choice(last_names)}"

    async def validate_customer(
        self, provider_code: str, customer_id: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Validate customer details (mock validation).

        Always returns valid for development purposes.
        """
        # Add small delay to simulate API call
        import asyncio
        await asyncio.sleep(0.1)

        customer_name = self._generate_customer_name(customer_id)

        # Mock response based on service type
        response = {
            "is_valid": True,
            "customer_name": customer_name,
            "customer_id": customer_id,
            "provider_code": provider_code,
        }

        # Add extra fields for electricity
        if "electric" in provider_code.lower() or "ekedc" in provider_code.lower():
            response.update({
                "customer_type": random.choice(["Prepaid", "Postpaid"]),
                "address": "123 Mock Street, Lagos",
                "balance": str(Decimal(random.uniform(0, 5000))),
            })

        # Add extra fields for cable TV
        elif any(tv in provider_code.lower() for tv in ["dstv", "gotv", "startimes"]):
            response.update({
                "customer_type": "Active",
                "current_package": "Premium Package",
                "renewal_date": "2025-12-31",
            })

        return response

    async def process_payment(
        self,
        provider_code: str,
        customer_id: str,
        amount: Decimal,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process bill payment (mock processing).

        Always succeeds and returns realistic response data.
        """
        # Add small delay to simulate API call
        import asyncio
        await asyncio.sleep(0.2)

        provider_reference = self._generate_provider_reference()
        customer_name = self._generate_customer_name(customer_id)

        response = {
            "success": True,
            "provider_reference": provider_reference,
            "customer_name": customer_name,
            "customer_id": customer_id,
            "amount": amount,
            "fee": Decimal("0"),  # Internal provider has no fees
            "message": "Payment successful",
            "extra_data": {
                "provider": "internal",
                "provider_code": provider_code,
                "test_mode": self.test_mode,
                "processed_at": time.time(),
            },
        }

        # Add token for electricity bills
        if "electric" in provider_code.lower() or any(word in provider_code.lower() for word in ["ekedc", "ikedc", "aedc", "phed"]):
            token = self._generate_token(amount)
            # Calculate mock units (rough estimate: 1 Naira = 1 unit)
            units = float(amount)
            response.update({
                "token": token,
                "token_units": f"{units:.2f} kWh",
            })

        # Add token for cable TV
        elif any(tv in provider_code.lower() for tv in ["dstv", "gotv", "startimes"]):
            response.update({
                "token": "Your subscription has been renewed successfully",
                "renewal_date": "2026-01-31",
            })

        return response

    async def query_transaction(self, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Query transaction status (mock query).

        Always returns successful status.
        """
        import asyncio
        await asyncio.sleep(0.05)

        return {
            "status": "success",
            "provider_reference": self._generate_provider_reference(),
            "amount": Decimal("1000"),  # Mock amount
            "customer_id": "MOCK12345",
            "customer_name": self._generate_customer_name("MOCK12345"),
            "token": self._generate_token(Decimal("1000")),
            "message": "Transaction successful",
        }

    def get_available_services(self) -> Dict[str, list]:
        """Get list of mock available services."""
        return self.MOCK_SERVICES.copy()

    def get_data_bundles(self, provider_code: str) -> list:
        """Get mock data bundles for a telecom provider."""
        return [
            {
                "name": "100MB Daily",
                "code": "100mb",
                "amount": Decimal("100"),
                "validity": "1 day",
            },
            {
                "name": "1GB Weekly",
                "code": "1gb",
                "amount": Decimal("500"),
                "validity": "7 days",
            },
            {
                "name": "5GB Monthly",
                "code": "5gb",
                "amount": Decimal("2000"),
                "validity": "30 days",
            },
            {
                "name": "10GB Monthly",
                "code": "10gb",
                "amount": Decimal("3500"),
                "validity": "30 days",
            },
        ]

    def get_cable_packages(self, provider_code: str) -> list:
        """Get mock cable TV packages."""
        packages = {
            "dstv": [
                {"name": "Padi", "code": "padi", "amount": Decimal("2500"), "validity": "30 days"},
                {"name": "Yanga", "code": "yanga", "amount": Decimal("3500"), "validity": "30 days"},
                {"name": "Confam", "code": "confam", "amount": Decimal("6000"), "validity": "30 days"},
                {"name": "Compact", "code": "compact", "amount": Decimal("10500"), "validity": "30 days"},
                {"name": "Premium", "code": "premium", "amount": Decimal("24500"), "validity": "30 days"},
            ],
            "gotv": [
                {"name": "Lite", "code": "lite", "amount": Decimal("1100"), "validity": "30 days"},
                {"name": "Jinja", "code": "jinja", "amount": Decimal("2250"), "validity": "30 days"},
                {"name": "Jolli", "code": "jolli", "amount": Decimal("3300"), "validity": "30 days"},
                {"name": "Max", "code": "max", "amount": Decimal("4850"), "validity": "30 days"},
            ],
            "startimes": [
                {"name": "Nova", "code": "nova", "amount": Decimal("1200"), "validity": "30 days"},
                {"name": "Basic", "code": "basic", "amount": Decimal("2100"), "validity": "30 days"},
                {"name": "Smart", "code": "smart", "amount": Decimal("3000"), "validity": "30 days"},
            ],
        }
        return packages.get(provider_code.lower(), [])

    def supports_category(self, category: str) -> bool:
        """Check if category is supported."""
        return category.lower() in self.SUPPORTED_CATEGORIES

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "internal"

    def calculate_provider_fee(self, amount: Decimal, service_type: str) -> Decimal:
        """Internal provider has no fees."""
        return Decimal("0")
