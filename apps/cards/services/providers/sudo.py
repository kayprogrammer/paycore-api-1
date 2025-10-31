from typing import Dict, Any, Optional
from decimal import Decimal
import hashlib
import hmac
import httpx
from django.conf import settings

from .base import BaseCardProvider
from apps.common.exceptions import RequestError, ErrorCode, BodyValidationError


class SudoCardProvider(BaseCardProvider):
    """
    Sudo Africa card provider.

    Integrates with Sudo's Virtual Card API.

    Features:
    - Sandbox/Test mode support
    - Virtual USD, NGN cards
    - Automatic webhook signature verification
    - Card transaction notifications

    Documentation: https://docs.sudo.africa/reference/cards
    """

    BASE_URL = "https://api.sudo.africa/cards/v1"
    SANDBOX_URL = "https://api.sandbox.sudo.africa/cards/v1"
    SUPPORTED_CURRENCIES = ["USD", "NGN"]
    SUPPORTED_CARD_TYPES = ["virtual"]  # Sudo supports virtual cards

    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)
        self.secret_key = self._get_secret_key()
        self.base_url = self.SANDBOX_URL if test_mode else self.BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def _get_secret_key(self) -> str:
        if self.test_mode:
            return getattr(settings, "SUDO_TEST_SECRET_KEY", "")
        return getattr(settings, "SUDO_LIVE_SECRET_KEY", "")

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
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a Sudo virtual card.

        API Endpoint: POST /cards
        Documentation: https://docs.sudo.africa/reference/create-card
        """
        if not self.supports_currency(currency_code):
            raise BodyValidationError(
                "currency_code",
                f"Sudo does not support {currency_code} cards. "
                f"Supported: {', '.join(self.SUPPORTED_CURRENCIES)}",
            )

        if not self.supports_card_type(card_type):
            raise BodyValidationError("card_type", f"Sudo only supports virtual cards")

        payload = {
            "type": card_brand.lower(),  # visa, mastercard
            "currency": currency_code,
            "issuing_app_id": kwargs.get("issuing_app_id"),  # Required by Sudo
            "metadata": {
                "customer_email": user_email,
                "customer_name": f"{user_first_name} {user_last_name}",
                "customer_phone": user_phone,
            },
        }

        if billing_address:
            payload["billing_address"] = {
                "line1": billing_address.get("street", ""),
                "city": billing_address.get("city", ""),
                "state": billing_address.get("state", ""),
                "postal_code": billing_address.get("postal_code", ""),
                "country": billing_address.get("country", ""),
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/cards",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code not in [200, 201]:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Sudo API error: {error_data.get('message', 'Unknown error')}",
                        status_code=response.status_code,
                    )

                data = response.json()

                if not data.get("success"):
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Sudo returned error: {data.get('message')}",
                    )

                card_data = data.get("data", {})

                return {
                    "card_number": card_data.get("card_number"),
                    "card_holder_name": card_data.get("name_on_card"),
                    "expiry_month": int(card_data.get("expiry_month", 12)),
                    "expiry_year": int(card_data.get("expiry_year", 2029)),
                    "cvv": card_data.get("cvv"),
                    "provider_card_id": card_data.get("id"),
                    "masked_number": card_data.get("masked_pan", "****"),
                    "provider_metadata": {
                        "provider": "sudo",
                        "currency": card_data.get("currency"),
                        "card_type": card_data.get("type"),
                        "status": card_data.get("status"),
                        "brand": card_data.get("brand"),
                        "test_mode": self.test_mode,
                    },
                }

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Sudo: {str(e)}",
                status_code=503,
            )

    async def get_card_details(self, provider_card_id: str) -> Dict[str, Any]:
        """
        Fetch card details from Sudo.

        API Endpoint: GET /cards/:id
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/cards/{provider_card_id}",
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code == 404:
                    raise RequestError(
                        err_code=ErrorCode.NOT_FOUND,
                        err_msg=f"Sudo card {provider_card_id} not found",
                        status_code=404,
                    )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Sudo API error: {error_data.get('message')}",
                        status_code=response.status_code,
                    )

                data = response.json()
                card_data = data.get("data", {})

                return {
                    "card_id": card_data.get("id"),
                    "masked_number": card_data.get("masked_pan"),
                    "status": card_data.get("status"),
                    "currency": card_data.get("currency"),
                    "brand": card_data.get("brand"),
                }

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Sudo: {str(e)}",
                status_code=503,
            )

    async def freeze_card(self, provider_card_id: str) -> bool:
        """
        Freeze Sudo virtual card.

        API Endpoint: POST /cards/:id/freeze
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/cards/{provider_card_id}/freeze",
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
                err_msg=f"Failed to connect to Sudo: {str(e)}",
                status_code=503,
            )

    async def unfreeze_card(self, provider_card_id: str) -> bool:
        """
        Unfreeze Sudo virtual card.

        API Endpoint: POST /cards/:id/unfreeze
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/cards/{provider_card_id}/unfreeze",
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
                err_msg=f"Failed to connect to Sudo: {str(e)}",
                status_code=503,
            )

    async def block_card(self, provider_card_id: str) -> bool:
        """
        Permanently block/terminate Sudo virtual card.

        API Endpoint: POST /cards/:id/terminate
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/cards/{provider_card_id}/terminate",
                    headers=self.headers,
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    raise RequestError(
                        err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        err_msg=f"Failed to terminate card: {error_data.get('message')}",
                        status_code=response.status_code,
                    )

                return True

        except httpx.RequestError as e:
            raise RequestError(
                err_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                err_msg=f"Failed to connect to Sudo: {str(e)}",
                status_code=503,
            )

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, **kwargs
    ) -> bool:
        """
        Verify Sudo webhook signature using HMAC SHA256.

        Sudo sends signature in X-Sudo-Signature header.
        Documentation: https://docs.sudo.africa/reference/webhooks
        """
        if not signature:
            return False

        # Get webhook secret from settings
        webhook_secret = getattr(settings, "SUDO_WEBHOOK_SECRET", "")

        # Compute expected signature
        expected_signature = hmac.new(
            webhook_secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Compare signatures (constant-time comparison)
        return hmac.compare_digest(expected_signature, signature)

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Sudo webhook event into standardized format.

        Sudo Webhook Events:
        - card.transaction: Card transaction occurred
        - card.created: Card was created
        - card.frozen: Card was frozen
        - card.unfrozen: Card was unfrozen

        Documentation: https://docs.sudo.africa/reference/webhooks
        """
        event_type = payload.get("event")
        data = payload.get("data", {})

        # Handle card transaction event
        if event_type == "card.transaction":
            return {
                "event_type": "transaction.success",
                "card_id": data.get("card_id"),
                "transaction_type": self._map_transaction_type(
                    data.get("type", "purchase")
                ),
                "amount": Decimal(str(data.get("amount", 0))),
                "currency": data.get("currency", "USD"),
                "merchant_name": data.get("merchant", {}).get("name"),
                "merchant_category": data.get("merchant", {}).get("category"),
                "location": {
                    "city": data.get("merchant", {}).get("city"),
                    "country": data.get("merchant", {}).get("country"),
                },
                "external_reference": data.get("reference"),
                "metadata": {
                    "sudo_reference": data.get("id"),
                    "authorization_code": data.get("authorization_code"),
                    "status": data.get("status"),
                },
            }

        # Handle card lifecycle events
        elif event_type in ["card.created", "card.frozen", "card.unfrozen"]:
            return {
                "event_type": event_type,
                "card_id": data.get("id"),
                "masked_number": data.get("masked_pan"),
                "status": data.get("status"),
                "metadata": data,
            }

        # Unknown event type
        return {
            "event_type": event_type,
            "metadata": payload,
        }

    def _map_transaction_type(self, sudo_type: str) -> str:
        """Map Sudo transaction type to our standard types."""
        mapping = {
            "purchase": "card_purchase",
            "withdrawal": "card_withdrawal",
            "atm": "card_withdrawal",
            "refund": "card_refund",
            "reversal": "card_reversal",
        }
        return mapping.get(sudo_type.lower(), "card_purchase")

    def supports_currency(self, currency_code: str) -> bool:
        """Check if Sudo supports the currency."""
        return currency_code.upper() in self.SUPPORTED_CURRENCIES

    def supports_card_type(self, card_type: str) -> bool:
        """Check if Sudo supports the card type."""
        return card_type.lower() in self.SUPPORTED_CARD_TYPES

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "sudo"

    def calculate_card_fee(self, amount: Decimal, transaction_type: str) -> Decimal:
        """
        Calculate Sudo card fee.

        Sudo charges fees based on transaction type.
        """
        # Example fee structure (adjust based on actual Sudo fees)
        if transaction_type == "card_purchase":
            return amount * Decimal("0.015")  # 1.5%
        elif transaction_type == "card_withdrawal":
            return Decimal("2.50")  # Flat $2.50 for ATM withdrawals
        return Decimal("0")
