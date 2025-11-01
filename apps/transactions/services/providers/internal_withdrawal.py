import asyncio
import time
import random
from decimal import Decimal
from typing import Dict, Any

from apps.transactions.services.providers.base_withdrawal import BaseWithdrawalProvider


class InternalWithdrawalProvider(BaseWithdrawalProvider):
    """Internal withdrawal provider for testing (instant completion)"""

    # Mock Nigerian banks for testing
    NIGERIAN_BANKS = [
        {"name": "Access Bank", "code": "044", "currency": "NGN"},
        {"name": "GTBank", "code": "058", "currency": "NGN"},
        {"name": "First Bank", "code": "011", "currency": "NGN"},
        {"name": "Zenith Bank", "code": "057", "currency": "NGN"},
        {"name": "UBA", "code": "033", "currency": "NGN"},
        {"name": "Ecobank", "code": "050", "currency": "NGN"},
        {"name": "Fidelity Bank", "code": "070", "currency": "NGN"},
        {"name": "Union Bank", "code": "032", "currency": "NGN"},
        {"name": "Stanbic IBTC", "code": "221", "currency": "NGN"},
        {"name": "Sterling Bank", "code": "232", "currency": "NGN"},
    ]

    # Mock Kenyan banks
    KENYAN_BANKS = [
        {"name": "Equity Bank", "code": "KE-EQU", "currency": "KES"},
        {"name": "KCB Bank", "code": "KE-KCB", "currency": "KES"},
        {"name": "Cooperative Bank", "code": "KE-COOP", "currency": "KES"},
        {"name": "NCBA Bank", "code": "KE-NCBA", "currency": "KES"},
    ]

    # Mock Ghanaian banks
    GHANAIAN_BANKS = [
        {"name": "GCB Bank", "code": "GH-GCB", "currency": "GHS"},
        {"name": "Ecobank Ghana", "code": "GH-ECO", "currency": "GHS"},
        {"name": "Zenith Bank Ghana", "code": "GH-ZEN", "currency": "GHS"},
    ]

    ALL_BANKS = NIGERIAN_BANKS + KENYAN_BANKS + GHANAIAN_BANKS

    def _generate_provider_reference(self) -> str:
        """Generate a mock provider reference"""
        timestamp = int(time.time())
        random_suffix = random.randint(1000, 9999)
        return f"INT-WTH-{timestamp}-{random_suffix}"

    async def initiate_withdrawal(
        self,
        user_email: str,
        user_first_name: str,
        user_last_name: str,
        amount: Decimal,
        currency_code: str,
        reference: str,
        account_details: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """Initiate internal withdrawal (instant completion for testing)"""
        await asyncio.sleep(0.15)  # Simulate API call

        provider_reference = self._generate_provider_reference()
        account_number = account_details.get("account_number", "0000000000")
        bank_code = account_details.get("bank_code", "000")
        account_name = account_details.get("account_name", "Unknown Account")

        # Find bank name
        bank_name = "Unknown Bank"
        for bank in self.ALL_BANKS:
            if bank["code"] == bank_code:
                bank_name = bank["name"]
                break

        return {
            "reference": reference,
            "provider_reference": provider_reference,
            "status": "completed",  # Instantly completed for testing
            "amount": amount,
            "currency": currency_code,
            "recipient": {
                "account_number": account_number,
                "account_name": account_name.upper(),
                "bank_code": bank_code,
                "bank_name": bank_name,
            },
            "transfer_code": provider_reference,
            "completed_at": time.time(),
            "metadata": {
                "provider": "internal",
                "test_mode": self.test_mode,
                "auto_completed": True,
                "message": "Internal withdrawal - automatically completed for testing",
                "initiated_by": user_email,
            },
        }

    async def verify_withdrawal(self, reference: str, **kwargs) -> Dict[str, Any]:
        """Verify internal withdrawal (always successful)"""
        await asyncio.sleep(0.05)

        return {
            "reference": reference,
            "provider_reference": reference,
            "status": "success",
            "amount": Decimal("0.00"),  # Unknown without context
            "currency": "NGN",
            "completed_at": time.time(),
            "metadata": {
                "provider": "internal",
                "test_mode": self.test_mode,
                "message": "Internal withdrawal verified",
            },
        }

    async def get_banks(self, currency_code: str = None) -> list:
        """Get list of mock banks"""
        await asyncio.sleep(0.05)

        if currency_code:
            currency_code = currency_code.upper()
            return [
                bank for bank in self.ALL_BANKS if bank["currency"] == currency_code
            ]

        return self.ALL_BANKS

    async def verify_account_number(
        self, account_number: str, bank_code: str, **kwargs
    ) -> Dict[str, Any]:
        """Verify account number (returns mock data)"""
        await asyncio.sleep(0.1)

        # Find bank name
        bank_name = "Unknown Bank"
        for bank in self.ALL_BANKS:
            if bank["code"] == bank_code:
                bank_name = bank["name"]
                break

        # Generate a realistic account name
        first_names = ["JOHN", "JANE", "MICHAEL", "SARAH", "DAVID", "MARY"]
        last_names = ["DOE", "SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES"]

        random.seed(account_number)  # Consistent name for same account number
        account_name = f"{random.choice(first_names)} {random.choice(last_names)}"

        return {
            "account_number": account_number,
            "account_name": account_name,
            "bank_code": bank_code,
            "bank_name": bank_name,
        }
