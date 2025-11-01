import hmac
import hashlib
from typing import Dict, Any
from decimal import Decimal
from django.conf import settings
import httpx

from .base import BaseDepositProvider
from apps.common.exceptions import RequestError, ErrorCode


class PaystackDepositProvider(BaseDepositProvider):
    """
    Paystack deposit provider for NGN deposits.

    Integrates with Paystack's Transaction API to handle deposits via:
    - Card payments
    - Bank transfers
    - USSD
    - QR codes
    - Mobile money

    Features:
    - Initialize transactions
    - Verify payments
    - Handle webhooks
    - Support for NGN currency

    API Documentation: https://paystack.com/docs/api/transaction/
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

    async def initiate_deposit(
        self,
        user_email: str,
        user_first_name: str,
        user_last_name: str,
        amount: Decimal,
        currency_code: str,
        reference: str,
        callback_url: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Initialize Paystack transaction.

        Makes API call to Paystack's initialize endpoint.
        Returns payment URL for user to complete payment.
        """
        # Paystack expects amount in kobo (smallest currency unit)
        amount_in_kobo = int(amount * 100)

        payload = {
            "email": user_email,
            "amount": amount_in_kobo,
            "currency": currency_code,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {
                "first_name": user_first_name,
                "last_name": user_last_name,
                "custom_fields": [
                    {
                        "display_name": "Customer Name",
                        "variable_name": "customer_name",
                        "value": f"{user_first_name} {user_last_name}",
                    }
                ],
            },
            "channels": ["card", "bank", "ussd", "qr", "mobile_money", "bank_transfer"],
        }

        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/transaction/initialize",
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Paystack API error: {error_data.get('message', 'Unknown error')}",
                    )

                data = response.json()

                if not data.get("status"):
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR,
                        f"Paystack initialization failed: {data.get('message')}",
                    )

                result = data["data"]

                return {
                    "reference": reference,
                    "provider_reference": result["reference"],
                    "payment_url": result["authorization_url"],
                    "access_code": result["access_code"],
                    "status": "pending",
                    "amount": amount,
                    "currency": currency_code,
                    "channel": None,  # Not determined yet
                    "paid_at": None,
                    "metadata": {
                        "provider": "paystack",
                        "test_mode": self.test_mode,
                    },
                }

        except httpx.HTTPError as e:
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to connect to Paystack: {str(e)}",
            )

    async def verify_deposit(self, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Verify Paystack transaction.

        Makes API call to verify transaction status.
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/transaction/verify/{reference}",
                    headers=headers,
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

                # Map Paystack status to our standard status
                paystack_status = result["status"]
                status_map = {
                    "success": "success",
                    "failed": "failed",
                    "abandoned": "failed",
                    "pending": "pending",
                }
                status = status_map.get(paystack_status, "pending")

                # Convert amount from kobo to naira
                amount = Decimal(result["amount"]) / 100

                return {
                    "status": status,
                    "reference": reference,
                    "provider_reference": result["reference"],
                    "amount": amount,
                    "currency": result["currency"],
                    "paid_at": result.get("paid_at"),
                    "channel": result.get("channel"),
                    "customer_email": result["customer"]["email"],
                    "metadata": {
                        "provider": "paystack",
                        "gateway_response": result.get("gateway_response"),
                        "ip_address": result.get("ip_address"),
                        "fees": Decimal(result.get("fees", 0)) / 100,
                    },
                }

        except httpx.HTTPError as e:
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"Failed to verify with Paystack: {str(e)}",
            )

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        """
        Verify Paystack webhook signature.

        Uses HMAC SHA512 to verify webhook authenticity.
        """
        expected_signature = hmac.new(
            self.secret_key.encode("utf-8"),
            payload,
            hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Paystack webhook event.

        Args:
            payload: Paystack webhook payload

        Returns:
            Standardized event format
        """
        event = payload.get("event", "")
        data = payload.get("data", {})

        # Convert amount from kobo to naira
        amount = Decimal(data.get("amount", 0)) / 100

        return {
            "event_type": event,
            "reference": data.get("reference"),
            "status": "success" if event == "charge.success" else data.get("status"),
            "amount": amount,
            "currency": data.get("currency", "NGN"),
            "paid_at": data.get("paid_at"),
            "channel": data.get("channel"),
            "customer_email": data.get("customer", {}).get("email"),
            "metadata": data,
        }

    def supports_currency(self, currency_code: str) -> bool:
        """Check if currency is supported."""
        return currency_code.upper() in self.SUPPORTED_CURRENCIES

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "paystack"

    def calculate_deposit_fee(self, amount: Decimal) -> Decimal:
        """
        Calculate Paystack transaction fee.

        Paystack charges 1.5% + NGN 100 (capped at NGN 2,000)
        """
        fee = (amount * Decimal("0.015")) + Decimal("100")
        return min(fee, Decimal("2000"))
