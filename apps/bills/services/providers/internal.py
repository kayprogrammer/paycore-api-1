import asyncio
import random
import time
from typing import Dict, Any
from decimal import Decimal

from .base import BaseBillPaymentProvider
from apps.bills.models import BillProvider, BillPackage, BillCategory


class InternalBillPaymentProvider(BaseBillPaymentProvider):
    """
    Internal bill payment provider for development and fallback purposes.

    This provider simulates bill payments without making external API calls.
    Uses actual BillProvider and BillPackage data from the database that was
    seeded using the seed_bill_providers management command.

    Perfect for:
    - Development when external bill payment providers are not available
    - Testing bill payment workflows without incurring costs
    - Fallback when external providers have issues

    Features:
    - Uses real providers and packages from database
    - Validates customer IDs (mock validation)
    - Simulates successful bill payments
    - Generates realistic tokens for electricity/cable
    - Supports all bill categories
    - No external dependencies

    Note: Make sure to run 'python manage.py seed_bill_providers' first
    to populate the database with providers and packages.
    """

    SUPPORTED_CATEGORIES = [
        BillCategory.AIRTIME,
        BillCategory.DATA,
        BillCategory.ELECTRICITY,
        BillCategory.CABLE_TV,
        BillCategory.INTERNET,
        BillCategory.EDUCATION,
        BillCategory.INSURANCE,
    ]

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
        first_names = [
            "John",
            "Jane",
            "Ahmed",
            "Fatima",
            "Chidi",
            "Amaka",
            "Tunde",
            "Bola",
        ]
        last_names = [
            "Smith",
            "Doe",
            "Mohammed",
            "Ibrahim",
            "Okafor",
            "Adeyemi",
            "Williams",
        ]
        return f"{random.choice(first_names)} {random.choice(last_names)}"

    async def validate_customer(
        self, provider_code: str, customer_id: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Validate customer details (mock validation).

        Always returns valid for development purposes.
        """
        # Add small delay to simulate API call
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
        if "electric" in provider_code.lower() or any(
            electric in provider_code.lower()
            for electric in ["ekedc", "ikedc", "aedc", "phed"]
        ):
            response.update(
                {
                    "customer_type": random.choice(["Prepaid", "Postpaid"]),
                    "address": "123 Mock Street, Lagos",
                    "balance": str(Decimal(random.uniform(0, 5000))),
                }
            )

        # Add extra fields for cable TV
        elif any(tv in provider_code.lower() for tv in ["dstv", "gotv", "startimes"]):
            response.update(
                {
                    "customer_type": "Active",
                    "current_package": "Premium Package",
                    "renewal_date": "2025-12-31",
                }
            )

        return response

    async def process_payment(
        self,
        provider_code: str,
        customer_id: str,
        amount: Decimal,
        reference: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Process bill payment (mock processing).

        Always succeeds and returns realistic response data.
        """
        # Add small delay to simulate API call
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
        if any(
            electric in provider_code.lower()
            for electric in ["electric", "ekedc", "ikedc", "aedc", "phed"]
        ):
            token = self._generate_token(amount)
            # Calculate mock units (rough estimate: 1 Naira = 1 unit)
            units = float(amount)
            response.update(
                {
                    "token": token,
                    "token_units": f"{units:.2f} kWh",
                }
            )

        # Add token for cable TV
        elif any(tv in provider_code.lower() for tv in ["dstv", "gotv", "startimes"]):
            response.update(
                {
                    "token": "Your subscription has been renewed successfully",
                    "renewal_date": "2026-01-31",
                }
            )

        return response

    async def query_transaction(self, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Query transaction status (mock query).

        Always returns successful status.
        """
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
        """
        Get list of available services from database.

        Returns providers grouped by category.
        """
        providers = BillProvider.objects.filter(is_active=True).values(
            "category", "name", "slug", "provider_code"
        )

        # Group by category
        services = {}
        for provider in providers:
            category = provider["category"]
            if category not in services:
                services[category] = []
            services[category].append(
                {
                    "name": provider["name"],
                    "slug": provider["slug"],
                    "code": provider["provider_code"],
                }
            )

        return services

    def get_data_bundles(self, provider_code: str) -> list:
        """
        Get available data bundles for a telecom provider from database.

        Args:
            provider_code: Provider code (e.g., "BIL122" for MTN Data)

        Returns:
            List of data bundles from database
        """
        packages = (
            BillPackage.objects.filter(
                provider__provider_code=provider_code,
                provider__category=BillCategory.DATA,
                is_active=True,
            )
            .values("name", "code", "amount", "validity_period")
            .order_by("display_order")
        )

        return [
            {
                "name": pkg["name"],
                "code": pkg["code"],
                "amount": pkg["amount"],
                "validity": pkg["validity_period"],
            }
            for pkg in packages
        ]

    def get_cable_packages(self, provider_code: str) -> list:
        """
        Get available cable TV packages from database.

        Args:
            provider_code: Cable provider code (e.g., "BIL114" for DSTV)

        Returns:
            List of cable packages from database
        """
        packages = (
            BillPackage.objects.filter(
                provider__provider_code=provider_code,
                provider__category=BillCategory.CABLE_TV,
                is_active=True,
            )
            .values("name", "code", "amount", "validity_period")
            .order_by("display_order")
        )

        return [
            {
                "name": pkg["name"],
                "code": pkg["code"],
                "amount": pkg["amount"],
                "validity": pkg["validity_period"],
            }
            for pkg in packages
        ]

    def supports_category(self, category: str) -> bool:
        """Check if category is supported."""
        return category in self.SUPPORTED_CATEGORIES

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "internal"

    def calculate_provider_fee(self, amount: Decimal, service_type: str) -> Decimal:
        """Internal provider has no fees."""
        return Decimal("0")
