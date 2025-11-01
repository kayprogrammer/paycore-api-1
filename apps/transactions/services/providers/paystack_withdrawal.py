from typing import Dict, Any
from decimal import Decimal
from django.conf import settings
import httpx

from apps.transactions.services.providers.base_withdrawal import BaseWithdrawalProvider
from apps.common.exceptions import RequestError, ErrorCode


class PaystackWithdrawalProvider(BaseWithdrawalProvider):
    """
    Paystack withdrawal provider for NGN bank transfers.

    Integrates with Paystack's Transfer API to handle withdrawals via:
    - Bank transfers to Nigerian banks
    - Transfer recipient management
    - Transfer verification

    Features:
    - Create transfer recipients
    - Initiate transfers
    - Verify transfers
    - Resolve account numbers
    - Fetch bank list

    API Documentation: https://paystack.com/docs/api/transfer/
    """

    SUPPORTED_CURRENCIES = ["NGN"]

    BASE_URL_TEST = "https://api.paystack.co"
    BASE_URL_LIVE = "https://api.paystack.co"

    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)
        self.secret_key = self._get_secret_key()
        self.base_url = self.BASE_URL_TEST if test_mode else self.BASE_URL_LIVE

    def _get_secret_key(self) -> str:
        """Get appropriate secret key based on mode"""
        if self.test_mode:
            key = getattr(settings, "PAYSTACK_TEST_SECRET_KEY", "")
        else:
            key = getattr(settings, "PAYSTACK_LIVE_SECRET_KEY", "")

        if not key:
            raise RequestError(
                ErrorCode.CONFIGURATION_ERROR,
                "Paystack secret key not configured",
            )
        return key

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

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
        """
        Initiate Paystack transfer.

        Steps:
        1. Create transfer recipient (or use existing)
        2. Initiate transfer
        3. Return transfer details

        Paystack requires amount in kobo (NGN * 100)
        """
        account_number = account_details.get("account_number")
        bank_code = account_details.get("bank_code")
        account_name = account_details.get("account_name")

        if not account_number or not bank_code:
            raise RequestError(
                ErrorCode.VALIDATION_ERROR,
                "account_number and bank_code are required",
            )

        # Convert amount to kobo
        amount_in_kobo = int(amount * 100)

        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Create transfer recipient
                recipient_payload = {
                    "type": "nuban",
                    "name": account_name or f"{user_first_name} {user_last_name}",
                    "account_number": account_number,
                    "bank_code": bank_code,
                    "currency": currency_code,
                }

                recipient_response = await client.post(
                    f"{self.base_url}/transferrecipient",
                    json=recipient_payload,
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                if recipient_response.status_code != 201:
                    error_data = recipient_response.json()
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Paystack recipient creation failed: {error_data.get('message', 'Unknown error')}",
                    )

                recipient_data = recipient_response.json()
                if not recipient_data.get("status"):
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Paystack recipient creation failed: {recipient_data.get('message')}",
                    )

                recipient = recipient_data["data"]
                recipient_code = recipient["recipient_code"]

                # Step 2: Initiate transfer
                transfer_payload = {
                    "source": "balance",
                    "reason": kwargs.get("description", "Withdrawal"),
                    "amount": amount_in_kobo,
                    "recipient": recipient_code,
                    "reference": reference,
                }

                transfer_response = await client.post(
                    f"{self.base_url}/transfer",
                    json=transfer_payload,
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                if transfer_response.status_code != 200:
                    error_data = transfer_response.json()
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Paystack transfer failed: {error_data.get('message', 'Unknown error')}",
                    )

                transfer_data = transfer_response.json()
                if not transfer_data.get("status"):
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Paystack transfer failed: {transfer_data.get('message')}",
                    )

                result = transfer_data["data"]

                # Map Paystack status to our standard status
                paystack_status = result["status"]
                status_map = {
                    "success": "completed",
                    "pending": "pending",
                    "otp": "pending",  # Requires OTP verification
                    "failed": "failed",
                    "reversed": "failed",
                }
                status = status_map.get(paystack_status, "pending")

                return {
                    "reference": reference,
                    "provider_reference": result.get(
                        "transfer_code", result.get("reference")
                    ),
                    "status": status,
                    "amount": amount,
                    "currency": currency_code,
                    "recipient": {
                        "account_number": account_number,
                        "account_name": recipient["details"]["account_name"],
                        "bank_code": bank_code,
                        "bank_name": recipient["details"]["bank_name"],
                    },
                    "transfer_code": result.get("transfer_code"),
                    "estimated_completion": "Instant to 1 business day",
                    "metadata": {
                        "provider": "paystack",
                        "test_mode": self.test_mode,
                        "recipient_code": recipient_code,
                        "paystack_status": paystack_status,
                    },
                }

        except httpx.HTTPError as e:
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to connect to Paystack: {str(e)}",
            )

    async def verify_withdrawal(self, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Verify Paystack transfer status.

        Can verify using either:
        - Transfer reference
        - Transfer code
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/transfer/verify/{reference}",
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Paystack verification error: {error_data.get('message')}",
                    )

                data = response.json()

                if not data.get("status"):
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Paystack verification failed: {data.get('message')}",
                    )

                result = data["data"]

                # Map Paystack status
                paystack_status = result["status"]
                status_map = {
                    "success": "success",
                    "pending": "pending",
                    "otp": "pending",
                    "failed": "failed",
                    "reversed": "failed",
                }
                status = status_map.get(paystack_status, "pending")

                # Convert amount from kobo
                amount = Decimal(result["amount"]) / 100

                return {
                    "reference": reference,
                    "provider_reference": result.get(
                        "transfer_code", result.get("reference")
                    ),
                    "status": status,
                    "amount": amount,
                    "currency": result["currency"],
                    "completed_at": result.get("transferred_at"),
                    "failure_reason": (
                        result.get("reason") if status == "failed" else None
                    ),
                    "metadata": {
                        "provider": "paystack",
                        "paystack_status": paystack_status,
                        "recipient": result.get("recipient"),
                    },
                }

        except httpx.HTTPError as e:
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to verify with Paystack: {str(e)}",
            )

    async def get_banks(self, currency_code: str = None) -> list:
        """
        Get list of Nigerian banks from Paystack.

        Paystack provides comprehensive list of banks with codes.
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {}
                if currency_code:
                    params["currency"] = currency_code.upper()
                else:
                    params["currency"] = "NGN"

                response = await client.get(
                    f"{self.base_url}/bank",
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Failed to fetch banks: {error_data.get('message')}",
                    )

                data = response.json()

                if not data.get("status"):
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Failed to fetch banks: {data.get('message')}",
                    )

                banks = data["data"]

                return [
                    {
                        "name": bank["name"],
                        "code": bank["code"],
                        "currency": params.get("currency", "NGN"),
                        "slug": bank.get("slug"),
                        "active": bank.get("active", True),
                    }
                    for bank in banks
                    if bank.get("active", True)  # Only return active banks
                ]

        except httpx.HTTPError as e:
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to connect to Paystack: {str(e)}",
            )

    async def verify_account_number(
        self, account_number: str, bank_code: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Verify account number and resolve account name.

        Uses Paystack's account resolution API to verify account details.
        """
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "account_number": account_number,
                    "bank_code": bank_code,
                }

                response = await client.get(
                    f"{self.base_url}/bank/resolve",
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Account verification failed: {error_data.get('message', 'Invalid account')}",
                    )

                data = response.json()

                if not data.get("status"):
                    raise RequestError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Account verification failed: {data.get('message', 'Invalid account')}",
                    )

                result = data["data"]

                return {
                    "account_number": result["account_number"],
                    "account_name": result["account_name"],
                    "bank_code": bank_code,
                    "bank_name": kwargs.get(
                        "bank_name", ""
                    ),  # Paystack doesn't return bank name
                }

        except httpx.HTTPError as e:
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to verify account: {str(e)}",
            )

    def supports_currency(self, currency_code: str) -> bool:
        """Check if currency is supported."""
        return currency_code.upper() in self.SUPPORTED_CURRENCIES

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "paystack"

    def calculate_withdrawal_fee(self, amount: Decimal) -> Decimal:
        """
        Calculate Paystack transfer fee.

        Paystack charges:
        - NGN 50 for transfers up to NGN 5,000
        - NGN 50 + 1% for transfers above NGN 5,000 (capped at NGN 100)
        """
        if amount <= Decimal("5000"):
            return Decimal("50")
        else:
            fee = Decimal("50") + (amount * Decimal("0.01"))
            return min(fee, Decimal("100"))
