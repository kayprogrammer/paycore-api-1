import httpx
import logging
from typing import Dict, Any
from decimal import Decimal
from django.conf import settings

from apps.bills.services.providers.base import BaseBillPaymentProvider
from apps.common.exceptions import (
    RequestError,
    BodyValidationError,
    NotFoundError,
    ErrorCode,
)

logger = logging.getLogger(__name__)


class FlutterwaveBillProvider(BaseBillPaymentProvider):
    """
    Flutterwave Bills Payment integration.

    Documentation: https://developer.flutterwave.com/docs/bills-payment

    Supported Services:
    - Airtime (MTN, Airtel, Glo, 9mobile)
    - Data bundles
    - Electricity (EKEDC, IKEDC, AEDC, etc.)
    - Cable TV (DSTV, GOtv, StarTimes)
    - Internet services

    """

    BASE_URL_PRODUCTION = "https://api.flutterwave.com/v3"
    BASE_URL_TEST = (
        "https://api.flutterwave.com/v3"  # Flutterwave uses same URL for test
    )

    def __init__(self, test_mode: bool = False):
        super().__init__(test_mode)
        self.api_key = self._get_api_key()
        self.base_url = self.BASE_URL_TEST if test_mode else self.BASE_URL_PRODUCTION

    def _get_api_key(self) -> str:
        """Get API key based on mode"""
        if self.test_mode:
            api_key = getattr(settings, "FLUTTERWAVE_TEST_SECRET_KEY", "")
        else:
            api_key = getattr(settings, "FLUTTERWAVE_LIVE_SECRET_KEY", "")

        if not api_key:
            raise ValueError(
                f"Flutterwave {'test' if self.test_mode else 'live'} API key not configured"
            )
        return api_key

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def validate_customer(
        self, provider_code: str, customer_id: str, **kwargs
    ) -> Dict[str, Any]:
        """Validate customer details"""
        url = f"{self.base_url}/bill-items/{provider_code}/validate"

        payload = {
            "customer": customer_id,
            "code": provider_code,
        }

        # Add optional parameters
        if "item_code" in kwargs:
            payload["item_code"] = kwargs["item_code"]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url, json=payload, headers=self._get_headers()
                )

                data = response.json()

                if response.status_code != 200 or data.get("status") != "success":
                    logger.error(f"Flutterwave validation failed: {data}")
                    raise BodyValidationError(
                        "customer_id", data.get("message", "Customer validation failed")
                    )

                # Parse response
                customer_data = data.get("data", {})
                response_code = customer_data.get("response_code", "")

                return {
                    "is_valid": response_code == "00",
                    "customer_name": customer_data.get("customer_name", ""),
                    "customer_id": customer_id,
                    "customer_type": customer_data.get("customer_type"),
                    "address": customer_data.get("address"),
                    "balance": customer_data.get("outstanding_balance"),
                    "extra_info": {
                        "minimum_amount": customer_data.get("minimum_amount"),
                        "maximum_amount": customer_data.get("maximum_amount"),
                        "response_message": customer_data.get("response_message"),
                    },
                }

        except httpx.RequestError as e:
            logger.error(f"Flutterwave API request failed: {str(e)}")
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                "Failed to validate customer. Please try again.",
            )

    async def process_payment(
        self,
        provider_code: str,
        customer_id: str,
        amount: Decimal,
        reference: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Process bill payment"""
        url = f"{self.base_url}/bills"

        payload = {
            "country": kwargs.get("country", "NG"),
            "customer": customer_id,
            "amount": float(amount),
            "recurrence": "ONCE",
            "type": provider_code,
            "reference": reference,
        }

        # Add optional fields
        if "email" in kwargs:
            payload["email"] = kwargs["email"]
        if "phone_number" in kwargs:
            payload["phone_number"] = kwargs["phone_number"]
        if "biller_name" in kwargs:
            payload["biller_name"] = kwargs["biller_name"]

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url, json=payload, headers=self._get_headers()
                )

                data = response.json()

                if response.status_code != 200 or data.get("status") != "success":
                    logger.error(f"Flutterwave payment failed: {data}")
                    error_message = data.get("message", "Payment failed")
                    raise RequestError(ErrorCode.EXTERNAL_SERVICE_ERROR, error_message)

                # Parse response
                payment_data = data.get("data", {})

                return {
                    "success": True,
                    "provider_reference": payment_data.get("flw_ref", ""),
                    "token": payment_data.get("token"),
                    "token_units": payment_data.get("units"),
                    "customer_name": payment_data.get("customer_name", ""),
                    "amount": Decimal(str(payment_data.get("amount", amount))),
                    "fee": Decimal(str(payment_data.get("fee", 0))),
                    "message": payment_data.get(
                        "response_message", "Payment successful"
                    ),
                    "extra_data": {
                        "network": payment_data.get("network"),
                        "phone_number": payment_data.get("phone_number"),
                        "transaction_date": payment_data.get("transaction_date"),
                    },
                }

        except httpx.RequestError as e:
            logger.error(f"Flutterwave API request failed: {str(e)}")
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                "Payment processing failed. Please try again.",
            )

    async def query_transaction(self, reference: str, **kwargs) -> Dict[str, Any]:
        """Query transaction status"""
        url = f"{self.base_url}/transactions/{reference}/verify"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._get_headers())

                data = response.json()

                if response.status_code == 404:
                    raise NotFoundError("transaction", "Transaction not found")

                if response.status_code != 200:
                    logger.error(f"Flutterwave query failed: {data}")
                    raise RequestError(
                        ErrorCode.EXTERNAL_SERVICE_ERROR, "Failed to query transaction"
                    )

                # Parse response
                txn_data = data.get("data", {})
                status = txn_data.get("status", "").lower()

                # Map Flutterwave status to our status
                status_map = {
                    "successful": "success",
                    "success": "success",
                    "failed": "failed",
                    "pending": "pending",
                }

                return {
                    "status": status_map.get(status, "pending"),
                    "provider_reference": txn_data.get("flw_ref", ""),
                    "amount": Decimal(str(txn_data.get("amount", 0))),
                    "customer_id": txn_data.get("customer_id", ""),
                    "customer_name": txn_data.get("customer_name", ""),
                    "token": txn_data.get("token"),
                    "message": txn_data.get("processor_response", ""),
                }

        except httpx.RequestError as e:
            logger.error(f"Flutterwave API request failed: {str(e)}")
            raise RequestError(
                ErrorCode.EXTERNAL_SERVICE_ERROR, "Failed to query transaction"
            )

    def get_available_services(self) -> Dict[str, list]:
        """Get available services"""
        # This would typically be fetched from the API
        # For now, returning a static list of common services
        return {
            "airtime": [
                {"name": "MTN Airtime", "code": "BIL099"},
                {"name": "Airtel Airtime", "code": "BIL102"},
                {"name": "Glo Airtime", "code": "BIL103"},
                {"name": "9mobile Airtime", "code": "BIL104"},
            ],
            "data": [
                {"name": "MTN Data", "code": "BIL122"},
                {"name": "Airtel Data", "code": "BIL108"},
                {"name": "Glo Data", "code": "BIL109"},
                {"name": "9mobile Data", "code": "BIL110"},
            ],
            "electricity": [
                {"name": "EKEDC Prepaid", "code": "BIL119"},
                {"name": "EKEDC Postpaid", "code": "BIL120"},
                {"name": "IKEDC Prepaid", "code": "BIL121"},
                {"name": "AEDC Prepaid", "code": "BIL123"},
            ],
            "cable_tv": [
                {"name": "DSTV", "code": "BIL114"},
                {"name": "GOtv", "code": "BIL115"},
                {"name": "StarTimes", "code": "BIL116"},
            ],
        }

    def get_data_bundles(self, provider_code: str) -> list:
        """Get data bundles for a provider"""
        # This would be fetched from Flutterwave API
        # Placeholder implementation
        return []

    def get_cable_packages(self, provider_code: str) -> list:
        """Get cable TV packages"""
        # This would be fetched from Flutterwave API
        # Placeholder implementation
        return []

    def supports_category(self, category: str) -> bool:
        """Check if category is supported"""
        supported = ["airtime", "data", "electricity", "cable_tv", "internet"]
        return category in supported

    def get_provider_name(self) -> str:
        """Get provider name"""
        return "flutterwave"

    def calculate_provider_fee(self, amount: Decimal, service_type: str) -> Decimal:
        """
        Calculate Flutterwave's fee.

        Flutterwave typically charges a small fee for bill payments,
        but the exact fee structure varies by service type.
        """
        # Flutterwave fee structure (example - verify with actual rates)
        if service_type in ["airtime", "data"]:
            # Flat fee for airtime/data
            return Decimal("20.00")  # ₦20
        elif service_type in ["electricity", "cable_tv"]:
            # Percentage fee capped
            fee = amount * Decimal("0.01")  # 1%
            return min(fee, Decimal("100.00"))  # Cap at ₦100
        else:
            return Decimal("50.00")  # Default fee
