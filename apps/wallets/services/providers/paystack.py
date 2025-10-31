from typing import Dict, Any, Optional
from decimal import Decimal
import hashlib
import hmac
import httpx
from django.conf import settings

from .base import BaseAccountProvider
from apps.common.exceptions import RequestError, ErrorCode, BodyValidationError


class PaystackAccountProvider(BaseAccountProvider):
    """
    Paystack virtual account provider.

    Integrates with Paystack's Dedicated Virtual Account API for NGN accounts.

    Features:
    - Sandbox/Test mode support
    - Automatic webhook signature verification
    - NGN virtual account creation
    - Real-time deposit notifications

    Documentation: https://paystack.com/docs/api/dedicated-virtual-account
    """

    BASE_URL = "https://api.paystack.co"
    SUPPORTED_CURRENCIES = ["NGN"]  # Paystack only supports NGN for virtual accounts

    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)
        self.secret_key = self._get_secret_key()
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def _get_secret_key(self) -> str:
        if self.test_mode:
            return settings.PAYSTACK_TEST_SECRET_KEY
        return settings.PAYSTACK_LIVE_SECRET_KEY

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
        Create a Paystack dedicated virtual account.

        API Endpoint: POST /dedicated_account
        Documentation: https://paystack.com/docs/api/dedicated-virtual-account/#create
        """
        if not self.supports_currency(currency_code):
            raise BodyValidationError(
                "currency_code",
                f"Paystack does not support {currency_code}. Only NGN is supported.",
            )

        # Prepare request payload
        payload = {
            "email": user_email,
            "first_name": user_first_name,
            "last_name": user_last_name,
            "preferred_bank": kwargs.get(
                "preferred_bank", "wema-bank"
            ),  # Default to Wema
        }

        # Add phone if provided (optional for Paystack)
        if user_phone:
            payload["phone"] = user_phone

        # Make API request
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/dedicated_account",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Paystack API error: {error_data.get('message', 'Unknown error')}",
                        status_code=response.status_code,
                    )

                data = response.json()

                if not data.get("status"):
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Paystack returned error: {data.get('message')}",
                        status_code=400,
                    )

                # Extract account details
                account_data = data.get("data", {})

                return {
                    "account_number": account_data.get("account_number"),
                    "account_name": account_data.get("account_name"),
                    "bank_name": account_data.get("bank", {}).get("name", "Wema Bank"),
                    "provider_account_id": str(account_data.get("id")),
                    "provider_metadata": {
                        "provider": "paystack",
                        "customer_code": account_data.get("customer", {}).get(
                            "customer_code"
                        ),
                        "bank_id": account_data.get("bank", {}).get("id"),
                        "bank_slug": account_data.get("bank", {}).get("slug"),
                        "currency": account_data.get("currency", "NGN"),
                        "active": account_data.get("active", True),
                        "test_mode": self.test_mode,
                    },
                }

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Paystack: {str(e)}",
                status_code=503,
            )

    async def verify_account(self, provider_account_id: str) -> Dict[str, Any]:
        """
        Fetch dedicated virtual account details from Paystack.

        API Endpoint: GET /dedicated_account/:id
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/dedicated_account/{provider_account_id}",
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code == 404:
                    raise RequestError(
                        err_code=ErrorCode.NOT_FOUND,
                        err_msg=f"Paystack account {provider_account_id} not found",
                        status_code=404,
                    )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Paystack API error: {error_data.get('message')}",
                        status_code=response.status_code,
                    )

                data = response.json()
                account_data = data.get("data", {})

                return {
                    "account_number": account_data.get("account_number"),
                    "account_name": account_data.get("account_name"),
                    "bank_name": account_data.get("bank", {}).get("name"),
                    "status": "active" if account_data.get("active") else "inactive",
                    "currency": account_data.get("currency", "NGN"),
                }

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Paystack: {str(e)}",
                status_code=503,
            )

    async def deactivate_account(self, provider_account_id: str) -> bool:
        """
        Deactivate Paystack dedicated virtual account by deactivating the customer.

        Paystack doesn't have a direct endpoint to deactivate virtual accounts.
        Instead, we set the customer to inactive which effectively deactivates all
        associated dedicated virtual accounts.

        API Endpoint: PUT /customer/:customer_code
        Documentation: https://paystack.com/docs/api/customer/#deactivate
        """
        try:
            # First, get the dedicated account to retrieve customer code
            async with httpx.AsyncClient() as client:
                # Get account details
                response = await client.get(
                    f"{self.BASE_URL}/dedicated_account/{provider_account_id}",
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code == 404:
                    # Account doesn't exist, consider it deactivated
                    return True

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Paystack API error: {error_data.get('message')}",
                        status_code=response.status_code,
                    )

                data = response.json()
                account_data = data.get("data", {})
                customer_code = account_data.get("customer", {}).get("customer_code")

                if not customer_code:
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg="Could not retrieve customer code from Paystack account",
                        status_code=400,
                    )

                # Deactivate the customer (this deactivates all their virtual accounts)
                deactivate_response = await client.put(
                    f"{self.BASE_URL}/customer/{customer_code}",
                    json={"active": False},
                    headers=self.headers,
                    timeout=30.0,
                )

                if deactivate_response.status_code != 200:
                    error_data = deactivate_response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Failed to deactivate customer: {error_data.get('message')}",
                        status_code=deactivate_response.status_code,
                    )

                return True

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Paystack: {str(e)}",
                status_code=503,
            )

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        """
        Verify Paystack webhook signature using HMAC SHA512.

        Paystack sends signature in x-paystack-signature header.
        Documentation: https://paystack.com/docs/payments/webhooks/#verify-signature
        """
        if not signature:
            return False

        # Compute expected signature
        expected_signature = hmac.new(
            self.secret_key.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha512,
        ).hexdigest()

        # Compare signatures (constant-time comparison to prevent timing attacks)
        return hmac.compare_digest(expected_signature, signature)

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Paystack webhook event into standardized format.

        Paystack Webhook Events:
        - charge.success: Payment received to virtual account
        - dedicatedaccount.assign.success: Virtual account created
        - dedicatedaccount.assign.failed: Virtual account creation failed

        Documentation: https://paystack.com/docs/payments/webhooks/#supported-events
        """
        event_type = payload.get("event")
        data = payload.get("data", {})

        # Handle charge.success (payment received)
        if event_type == "charge.success":
            metadata = data.get("metadata", {})
            authorization = data.get("authorization", {})

            return {
                "event_type": "payment.success",
                "account_number": authorization.get("receiver_bank_account_number"),
                "amount": Decimal(str(data.get("amount", 0)))
                / 100,  # Paystack uses kobo (1/100 NGN)
                "sender_account_number": authorization.get("account_number"),
                "sender_account_name": authorization.get("account_name"),
                "sender_bank_name": authorization.get("bank"),
                "external_reference": data.get("reference"),
                "currency_code": data.get("currency", "NGN"),
                "metadata": {
                    "paystack_reference": data.get("reference"),
                    "customer_code": data.get("customer", {}).get("customer_code"),
                    "channel": data.get("channel"),
                    "paid_at": data.get("paid_at"),
                    "fees": Decimal(str(data.get("fees", 0))) / 100,
                },
            }

        # Handle dedicated account events
        elif event_type in [
            "dedicatedaccount.assign.success",
            "dedicatedaccount.assign.failed",
        ]:
            return {
                "event_type": event_type,
                "account_number": data.get("account_number"),
                "account_name": data.get("account_name"),
                "bank_name": data.get("bank", {}).get("name"),
                "customer_code": data.get("customer", {}).get("customer_code"),
                "currency_code": data.get("currency", "NGN"),
                "metadata": data,
            }

        # Unknown event type
        return {
            "event_type": event_type,
            "metadata": payload,
        }

    def supports_currency(self, currency_code: str) -> bool:
        return currency_code.upper() in self.SUPPORTED_CURRENCIES

    def get_provider_name(self) -> str:
        return "paystack"

    def calculate_deposit_fee(self, amount: Decimal) -> Decimal:
        fee = amount * Decimal("0.015")  # 1.5%
        cap = Decimal("2000")  # NGN 2,000 cap
        return min(fee, cap)
