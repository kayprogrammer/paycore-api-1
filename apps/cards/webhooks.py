from typing import Dict, Any
from decimal import Decimal
from ninja import Router
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json

from apps.cards.models import Card, CardStatus
from apps.cards.services.providers.factory import CardProviderFactory
from apps.transactions.models import Transaction, TransactionType, TransactionStatus
import logging

logger = logging.getLogger(__name__)

webhook_router = Router(tags=["Card Webhooks (2)"])


@webhook_router.post("/webhooks/flutterwave", auth=None)
@csrf_exempt
async def flutterwave_webhook(request: HttpRequest):
    """
    Handle Flutterwave card webhooks.

    Events:
    - card.transaction: Card transaction occurred
    - card.created: Card was created
    - card.frozen: Card was frozen
    - card.blocked: Card was blocked

    Documentation: https://developer.flutterwave.com/docs/integration-guides/webhooks
    """
    try:
        raw_body = request.body
        signature = request.headers.get("verif-hash")

        if not signature:
            logger.warning("Flutterwave webhook received without signature")
            return JsonResponse(
                {"status": "error", "message": "Missing signature"}, status=400
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in Flutterwave webhook")
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON"}, status=400
            )

        provider = CardProviderFactory.get_provider("flutterwave")

        is_valid = await provider.verify_webhook_signature(
            payload=raw_body,
            signature=signature,
        )

        if not is_valid:
            logger.warning(f"Invalid Flutterwave webhook signature: {signature}")
            return JsonResponse(
                {"status": "error", "message": "Invalid signature"}, status=401
            )

        event_data = provider.parse_webhook_event(payload)
        event_type = event_data.get("event_type")

        logger.info(f"Processing Flutterwave webhook: {event_type}")

        if event_type == "transaction.success":
            await _handle_card_transaction(event_data, "flutterwave")

        elif event_type in ["card.created", "card.frozen", "card.blocked"]:
            await _handle_card_lifecycle_event(event_data, "flutterwave")
        else:
            logger.warning(f"Unknown Flutterwave event type: {event_type}")
        return JsonResponse({"status": "success"}, status=200)

    except Exception as e:
        logger.error(f"Error processing Flutterwave webhook: {str(e)}", exc_info=True)
        return JsonResponse(
            {"status": "error", "message": "Internal error"}, status=500
        )


@webhook_router.post("/webhooks/sudo", auth=None)
@csrf_exempt
async def sudo_webhook(request: HttpRequest):
    """
    Handle Sudo Africa card webhooks.

    Events:
    - card.transaction: Card transaction occurred
    - card.created: Card was created
    - card.frozen: Card was frozen
    - card.unfrozen: Card was unfrozen

    Documentation: https://docs.sudo.africa/reference/webhooks
    """
    try:
        raw_body = request.body
        signature = request.headers.get("X-Sudo-Signature")

        if not signature:
            logger.warning("Sudo webhook received without signature")
            return JsonResponse(
                {"status": "error", "message": "Missing signature"}, status=400
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in Sudo webhook")
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON"}, status=400
            )

        provider = CardProviderFactory.get_provider("sudo")
        is_valid = await provider.verify_webhook_signature(
            payload=raw_body,
            signature=signature,
        )

        if not is_valid:
            logger.warning(f"Invalid Sudo webhook signature: {signature}")
            return JsonResponse(
                {"status": "error", "message": "Invalid signature"}, status=401
            )

        event_data = provider.parse_webhook_event(payload)
        event_type = event_data.get("event_type")

        logger.info(f"Processing Sudo webhook: {event_type}")

        if event_type == "transaction.success":
            await _handle_card_transaction(event_data, "sudo")

        elif event_type in ["card.created", "card.frozen", "card.unfrozen"]:
            await _handle_card_lifecycle_event(event_data, "sudo")

        else:
            logger.warning(f"Unknown Sudo event type: {event_type}")

        return JsonResponse({"status": "success"}, status=200)

    except Exception as e:
        logger.error(f"Error processing Sudo webhook: {str(e)}", exc_info=True)
        return JsonResponse(
            {"status": "error", "message": "Internal error"}, status=500
        )


async def _handle_card_transaction(event_data: Dict[str, Any], provider_name: str):
    """
    Handle card transaction webhook event.

    Creates a Transaction record and updates card spending limits.
    """
    try:
        # Get card by provider card ID
        provider_card_id = event_data.get("card_id")
        card = await Card.objects.select_related(
            "wallet", "wallet__currency", "user"
        ).aget_or_none(
            provider_card_id=provider_card_id,
            card_provider=provider_name,
        )

        if not card:
            logger.warning(
                f"Card not found for {provider_name} transaction: {provider_card_id}"
            )
            return

        # Check if transaction already exists (idempotency)
        external_reference = event_data.get("external_reference")
        existing = await Transaction.objects.filter(
            external_reference=external_reference
        ).aexists()

        if existing:
            logger.info(f"Transaction {external_reference} already processed, skipping")
            return

        # Extract transaction details
        amount = event_data.get("amount", Decimal("0"))
        currency = event_data.get("currency")
        transaction_type = event_data.get(
            "transaction_type", TransactionType.CARD_PURCHASE
        )
        merchant_name = event_data.get("merchant_name")
        merchant_category = event_data.get("merchant_category")
        location = event_data.get("location", {})
        metadata = event_data.get("metadata", {})

        wallet = card.wallet
        balance_before = wallet.balance

        # Deduct amount from wallet
        if amount > wallet.balance:
            logger.error(
                f"Insufficient balance for card transaction: {amount} > {wallet.balance}"
            )
            # Transaction still recorded but marked as failed
            transaction_status = TransactionStatus.FAILED
            balance_after = balance_before
        else:
            # Deduct from wallet
            wallet.balance -= amount
            await wallet.asave(update_fields=["balance", "updated_at"])
            balance_after = wallet.balance
            transaction_status = TransactionStatus.COMPLETED

            # Update card spending limits
            card.total_spent += amount
            card.daily_spent += amount
            card.monthly_spent += amount
            card.last_used_at = timezone.now()
            await card.asave(
                update_fields=[
                    "total_spent",
                    "daily_spent",
                    "monthly_spent",
                    "last_used_at",
                    "updated_at",
                ]
            )

        # Create transaction record
        transaction = await Transaction.objects.acreate(
            user=card.user,
            wallet=wallet,
            card=card,
            transaction_type=transaction_type,
            amount=amount,
            currency=wallet.currency,
            status=transaction_status,
            from_balance_before=balance_before,
            from_balance_after=balance_after,
            merchant_name=merchant_name,
            merchant_category=merchant_category,
            transaction_location=location,
            external_reference=external_reference,
            provider_response=metadata,
            description=f"{transaction_type.replace('_', ' ').title()} at {merchant_name or 'merchant'}",
        )
        logger.info(
            f"Card transaction recorded: {transaction.transaction_id} - {amount} {currency}"
        )
    except Exception as e:
        logger.error(
            f"Error handling card transaction webhook: {str(e)}", exc_info=True
        )


async def _handle_card_lifecycle_event(event_data: Dict[str, Any], provider_name: str):
    """
    Handle card lifecycle webhook events (created, frozen, blocked, etc.).

    Updates local card status to match provider status.
    """
    try:
        # Get card by provider card ID
        provider_card_id = event_data.get("card_id")
        card = await Card.objects.aget_or_none(
            provider_card_id=provider_card_id,
            card_provider=provider_name,
        )

        if not card:
            logger.warning(
                f"Card not found for {provider_name} lifecycle event: {provider_card_id}"
            )
            return

        event_type = event_data.get("event_type")

        # Update card status based on event
        if event_type == "card.frozen":
            card.is_frozen = True
            await card.asave(update_fields=["is_frozen", "updated_at"])
            logger.info(f"Card {card.card_id} marked as frozen")

        elif event_type == "card.unfrozen":
            card.is_frozen = False
            await card.asave(update_fields=["is_frozen", "updated_at"])
            logger.info(f"Card {card.card_id} marked as unfrozen")

        elif event_type == "card.blocked":
            card.status = CardStatus.BLOCKED
            await card.asave(update_fields=["status", "updated_at"])
            logger.info(f"Card {card.card_id} marked as blocked")

        else:
            logger.info(f"Card lifecycle event: {event_type} for {card.card_id}")

    except Exception as e:
        logger.error(f"Error handling card lifecycle webhook: {str(e)}", exc_info=True)
