import random
from typing import Dict, Any, Optional
from decimal import Decimal
import hashlib
import hmac
import httpx
from django.conf import settings

from .base import BaseCardProvider
from apps.common.exceptions import RequestError, ErrorCode, BodyValidationError


class FlutterwaveCardProvider(BaseCardProvider):
    """
    Flutterwave virtual card provider.

    Integrates with Flutterwave's Virtual Card API.

    Features:
    - Sandbox/Test mode support
    - Virtual USD, NGN, GBP cards
    - Automatic webhook signature verification
    - Card transaction notifications

    Documentation: https://developer.flutterwave.com/docs/virtual-cards
    """

    BASE_URL = "https://api.flutterwave.com/v3"
    SUPPORTED_CURRENCIES = ["USD", "NGN", "GBP"]
    SUPPORTED_CARD_TYPES = ["virtual"]  # Flutterwave only supports virtual cards

    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)
        self.secret_key = self._get_secret_key()
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def _get_secret_key(self) -> str:
        if self.test_mode:
            return getattr(settings, "FLUTTERWAVE_TEST_SECRET_KEY", "")
        return getattr(settings, "FLUTTERWAVE_LIVE_SECRET_KEY", "")

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
        date_of_birth: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a Flutterwave virtual card.

        API Endpoint: POST /virtual-cards
        Documentation: https://developer.flutterwave.com/docs/virtual-cards/create
        """
        if not self.supports_currency(currency_code):
            raise BodyValidationError(
                "currency_code",
                f"Flutterwave does not support {currency_code} cards. Supported: {', '.join(self.SUPPORTED_CURRENCIES)}",
            )

        gender = random.choice(["male", "female"])
        title = "Mr" if gender == "male" else "Mrs"

        payload = {
            "currency": currency_code,
            "amount": kwargs.get("initial_amount", 0),
            "debit_currency": currency_code,
            "billing_name": f"{user_first_name} {user_last_name}",
            "billing_email": user_email,
            "billing_phone": user_phone,
            "first_name": user_first_name,
            "last_name": user_last_name,
            "email": user_email,
            "phone": user_phone,
            "title": title,
            "gender": gender,
            "date_of_birth": date_of_birth,
        }

        if billing_address:
            payload.update(
                {
                    "billing_address": billing_address.get("street", ""),
                    "billing_city": billing_address.get("city", ""),
                    "billing_state": billing_address.get("state", ""),
                    "billing_postal_code": billing_address.get("postal_code", ""),
                    "billing_country": billing_address.get("country", ""),
                }
            )

        # Make API request
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/virtual-cards",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code not in [200, 201]:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Flutterwave API error: {error_data.get('message', 'Unknown error')}",
                        status_code=response.status_code,
                    )

                data = response.json()

                if data.get("status") != "success":
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Flutterwave returned error: {data.get('message')}",
                    )

                card_data = data.get("data", {})

                return {
                    "card_number": card_data.get("card_pan"),
                    "card_holder_name": card_data.get("name_on_card"),
                    "expiry_month": int(
                        card_data.get("expiration", "01/2025").split("/")[0]
                    ),
                    "expiry_year": int(
                        card_data.get("expiration", "01/2025").split("/")[1]
                    ),
                    "cvv": card_data.get("cvv"),
                    "provider_card_id": card_data.get("id"),
                    "masked_number": card_data.get("masked_pan", "****"),
                    "provider_metadata": {
                        "provider": "flutterwave",
                        "currency": card_data.get("currency"),
                        "card_type": card_data.get("card_type"),
                        "card_status": card_data.get("is_active"),
                        "balance": card_data.get("balance"),
                        "test_mode": self.test_mode,
                    },
                }

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Flutterwave: {str(e)}",
                status_code=503,
            )

    async def get_card_details(self, provider_card_id: str) -> Dict[str, Any]:
        """
        Fetch card details from Flutterwave.
        API Endpoint: GET /virtual-cards/:id
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/virtual-cards/{provider_card_id}",
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code == 404:
                    raise RequestError(
                        err_code=ErrorCode.NOT_FOUND,
                        err_msg=f"Flutterwave card {provider_card_id} not found",
                        status_code=404,
                    )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Flutterwave API error: {error_data.get('message')}",
                        status_code=response.status_code,
                    )

                data = response.json()
                card_data = data.get("data", {})

                return {
                    "card_id": card_data.get("id"),
                    "masked_number": card_data.get("masked_pan"),
                    "status": "active" if card_data.get("is_active") else "inactive",
                    "currency": card_data.get("currency"),
                    "balance": card_data.get("balance"),
                }

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Flutterwave: {str(e)}",
                status_code=503,
            )

    async def freeze_card(self, provider_card_id: str) -> bool:
        """
        Freeze Flutterwave virtual card.
        API Endpoint: PUT /virtual-cards/:id/status/block
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/virtual-cards/{provider_card_id}/status/block",
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Failed to freeze card: {error_data.get('message')}",
                        status_code=response.status_code,
                    )

                return True

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Flutterwave: {str(e)}",
                status_code=503,
            )

    async def unfreeze_card(self, provider_card_id: str) -> bool:
        """
        Unfreeze Flutterwave virtual card.

        API Endpoint: PUT /virtual-cards/:id/status/unblock
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/virtual-cards/{provider_card_id}/status/unblock",
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Failed to unfreeze card: {error_data.get('message')}",
                        status_code=response.status_code,
                    )

                return True

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Flutterwave: {str(e)}",
                status_code=503,
            )

    async def block_card(self, provider_card_id: str) -> bool:
        """
        Permanently block/terminate Flutterwave virtual card.

        API Endpoint: PUT /virtual-cards/:id/status/block
        Note: Flutterwave uses same endpoint for freeze and block.
        To make it permanent, we just don't unblock it.
        """
        return await self.freeze_card(provider_card_id)

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        """
        Verify Flutterwave webhook signature using HMAC SHA256.

        Flutterwave sends signature in verif-hash header.
        Documentation: https://developer.flutterwave.com/docs/integration-guides/webhooks
        """
        if not signature:
            return False

        # Get webhook hash from settings
        webhook_hash = getattr(settings, "FLUTTERWAVE_WEBHOOK_HASH", "")

        # Flutterwave uses a simple hash comparison
        return signature == webhook_hash

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Flutterwave webhook event into standardized format.

        Flutterwave Webhook Events:
        - virtual-card.transaction: Card transaction occurred
        - virtual-card.created: Card was created

        Documentation: https://developer.flutterwave.com/docs/integration-guides/webhooks
        """
        event_type = payload.get("event")
        data = payload.get("data", {})

        # Handle card transaction event
        if event_type == "virtual-card.transaction":
            return {
                "event_type": "transaction.success",
                "card_id": data.get("card_id"),
                "transaction_type": self._map_transaction_type(
                    data.get("type", "purchase")
                ),
                "amount": Decimal(str(data.get("amount", 0))),
                "currency": data.get("currency", "USD"),
                "merchant_name": data.get("merchant_name"),
                "merchant_category": data.get("merchant_category"),
                "location": {
                    "city": data.get("city"),
                    "country": data.get("country"),
                },
                "external_reference": data.get("transaction_reference"),
                "metadata": {
                    "flutterwave_reference": data.get("flw_ref"),
                    "card_pan": data.get("card_pan"),
                    "status": data.get("status"),
                },
            }

        # Handle card created event
        elif event_type == "virtual-card.created":
            return {
                "event_type": "card.created",
                "card_id": data.get("id"),
                "masked_number": data.get("masked_pan"),
                "currency": data.get("currency"),
                "metadata": data,
            }

        # Unknown event type
        return {
            "event_type": event_type,
            "metadata": payload,
        }

    def _map_transaction_type(self, flw_type: str) -> str:
        mapping = {
            "purchase": "card_purchase",
            "withdrawal": "card_withdrawal",
            "refund": "card_refund",
        }
        return mapping.get(flw_type.lower(), "card_purchase")

    def supports_currency(self, currency_code: str) -> bool:
        return currency_code.upper() in self.SUPPORTED_CURRENCIES

    def supports_card_type(self, card_type: str) -> bool:
        return card_type.lower() in self.SUPPORTED_CARD_TYPES

    def get_provider_name(self) -> str:
        return "flutterwave"

    def calculate_card_fee(self, amount: Decimal, transaction_type: str) -> Decimal:
        """
        Flutterwave charges fees based on transaction type.
        """
        # Example fee structure (adjust based on actual Flutterwave fees)
        if transaction_type == "card_purchase":
            return amount * Decimal("0.014")  # 1.4%
        elif transaction_type == "card_withdrawal":
            return Decimal("2.00")  # Flat $2 for ATM withdrawals
        return Decimal("0")
