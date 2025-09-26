import json
import logging
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import hmac
import hashlib

from .services import KYCValidationService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def onfido_webhook(request):
    """Handle Onfido webhook notifications"""
    try:
        # Verify webhook signature
        if not verify_onfido_signature(request):
            logger.warning("Invalid Onfido webhook signature")
            return HttpResponseBadRequest("Invalid signature")

        # Parse webhook payload
        payload = json.loads(request.body.decode("utf-8"))

        # Process the webhook
        service = KYCValidationService()
        success = service.process_webhook_update(payload)

        if success:
            return HttpResponse("OK", status=200)
        else:
            return HttpResponseBadRequest("Processing failed")

    except json.JSONDecodeError:
        logger.error("Invalid JSON in Onfido webhook")
        return HttpResponseBadRequest("Invalid JSON")
    except Exception as e:
        logger.error(f"Onfido webhook processing error: {str(e)}")
        return HttpResponse("Internal Server Error", status=500)


def verify_onfido_signature(request):
    """Verify Onfido webhook signature"""
    webhook_token = getattr(settings, "ONFIDO_WEBHOOK_TOKEN", None)
    if not webhook_token:
        logger.warning("ONFIDO_WEBHOOK_TOKEN not configured")
        return False

    signature = request.headers.get("X-SHA2-Signature", "")
    if not signature:
        return False

    # Calculate expected signature
    expected_signature = hmac.new(
        webhook_token.encode("utf-8"), request.body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@csrf_exempt
@require_http_methods(["POST"])
def generic_kyc_webhook(request):
    """Generic webhook handler for other KYC providers"""
    try:
        payload = json.loads(request.body.decode("utf-8"))

        # Add provider-specific signature verification here
        # if not verify_provider_signature(request, provider_name):
        #     return HttpResponseBadRequest("Invalid signature")

        service = KYCValidationService()
        success = service.process_webhook_update(payload)

        if success:
            return HttpResponse("OK", status=200)
        else:
            return HttpResponseBadRequest("Processing failed")

    except Exception as e:
        logger.error(f"Generic KYC webhook error: {str(e)}")
        return HttpResponse("Internal Server Error", status=500)
