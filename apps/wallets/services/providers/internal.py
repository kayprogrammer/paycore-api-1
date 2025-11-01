from typing import Dict, Any, Optional
from decimal import Decimal
import random, time, asyncio

from .base import BaseAccountProvider
from apps.wallets.models import Wallet
from apps.common.exceptions import NotFoundError


class InternalAccountProvider(BaseAccountProvider):
    """
    Internal account provider for currencies without external provider support.

    Used for USD, EUR, GBP, NGN and other currencies where we manage account numbers
    internally without external payment gateway integration.

    This provider is production-ready and serves as a fallback when external
    providers (like Paystack) are unavailable or not configured.

    Features:
    - Generates unique account numbers (10 digits starting with 90)
    - Supports all major currencies
    - No external API dependencies
    - Immediate account creation

    Account Number Format: 90XXXXXXXX (10 digits starting with 90)
    """

    SUPPORTED_CURRENCIES = [
        "NGN",  # Nigerian Naira
        "USD",  # US Dollar
        "EUR",  # Euro
        "GBP",  # British Pound
        "KES",  # Kenyan Shilling
        "GHS",  # Ghanaian Cedi
        "ZAR",  # South African Rand
    ]  # Can support any currency internally

    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)

    async def create_account(
        self,
        user_email: str,
        user_first_name: str,
        user_last_name: str,
        user_phone: Optional[str],
        currency_code: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create an internal virtual account.

        Generates a unique account number and returns account details immediately
        without requiring external API calls.
        """
        # Add small delay to simulate realistic API behavior
        await asyncio.sleep(0.05)

        # Generate unique account number
        account_number = await self._generate_account_number()
        account_name = f"{user_first_name} {user_last_name}".strip().upper()

        # Bank name is always PayCore for internal accounts
        bank_name = "PayCore"

        return {
            "account_number": account_number,
            "account_name": account_name,
            "bank_name": bank_name,
            "provider_account_id": account_number,  # For internal, account_number IS the ID
            "provider_metadata": {
                "provider": "internal",
                "currency": currency_code,
                "test_mode": self.test_mode,
                "created_by": user_email,
                "phone": user_phone,
                "created_at": time.time(),
                "account_type": "internal_virtual_account",
            },
        }

    async def verify_account(self, provider_account_id: str) -> Dict[str, Any]:
        wallet = await Wallet.objects.aget_or_none(account_number=provider_account_id)

        if not wallet:
            raise NotFoundError(err_msg=f"Account {provider_account_id} not found")

        return {
            "account_number": wallet.account_number,
            "account_name": wallet.account_name,
            "bank_name": wallet.bank_name,
            "status": wallet.status,
            "currency": wallet.currency.code,
        }

    async def deactivate_account(self, provider_account_id: str) -> bool:
        """
        Deactivate internal account.

        For internal accounts, this is a no-op since account lifecycle
        is managed by the Wallet model directly.
        """
        # No external API to call for internal accounts
        # Account status is managed via Wallet.status field
        return True

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        """
        Verify webhook signature.

        Internal accounts don't receive external webhooks, so this always returns True.
        All deposits to internal accounts are handled via API calls, not webhooks.
        """
        return True

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse webhook event.

        Internal accounts don't receive webhooks. This method is included for
        interface compliance but should not be called in practice.
        """
        # Internal accounts use direct API deposits, not webhooks
        return {
            "event_type": "internal.deposit",
            "account_number": payload.get("account_number"),
            "amount": payload.get("amount"),
            "sender_account_number": payload.get("sender_account_number"),
            "sender_account_name": payload.get("sender_account_name"),
            "sender_bank_name": payload.get("sender_bank_name"),
            "external_reference": payload.get("reference"),
            "currency_code": payload.get("currency_code"),
            "metadata": payload.get("metadata", {}),
        }

    def supports_currency(self, currency_code: str) -> bool:
        """
        Check if currency is supported.

        Internal provider can support any currency since we manage accounts internally.
        """
        return True  # Internal provider supports all currencies

    def get_provider_name(self) -> str:
        return "internal"

    def calculate_deposit_fee(self, amount: Decimal) -> Decimal:
        return Decimal("0")

    async def _generate_account_number(self) -> str:
        max_attempts = 10
        attempts = 0

        while True:
            # Generate 10-digit account number starting with 90
            account_number = "90" + "".join(
                [str(random.randint(0, 9)) for _ in range(8)]
            )

            # Check if unique
            if not await Wallet.objects.filter(account_number=account_number).aexists():
                return account_number

            attempts += 1
            if attempts >= max_attempts:
                # Fallback: use timestamp if random generation fails after max attempts
                return f"90{int(time.time()) % 100000000:08d}"
