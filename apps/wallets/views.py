import json
from uuid import UUID
from asgiref.sync import sync_to_async
from ninja import Router
from apps.wallets.models import AccountProvider, Currency, WalletStatus, WalletType
from apps.wallets.services.providers.factory import AccountProviderFactory
from apps.wallets.services.wallet_manager import WalletManager
from apps.wallets.services.wallet_operations import WalletOperations
from apps.wallets.services.security_service import WalletSecurityService
from apps.wallets.services.deposit_service import DepositService
from apps.wallets.schemas import (
    CreateWalletSchema,
    CreateWalletResponseSchema,
    UpdateWalletSchema,
    SetWalletPinSchema,
    ChangeWalletPinSchema,
    WalletStatusSchema,
    WalletListResponseSchema,
    HoldFundsSchema,
    ReleaseFundsSchema,
    BalanceDataResponseSchema,
    TransactionAuthSchema,
    AuthDataResponseSchema,
    WalletSecuritySchema,
    SecurityDataResponseSchema,
    DisableSecuritySchema,
    WalletSummaryDataResponseSchema,
    DepositWebhookSchema,
    DepositWebhookDataResponseSchema,
    CurrencyListResponseSchema,
)
from apps.common.responses import CustomResponse
from apps.common.schemas import ResponseSchema
from apps.common.exceptions import RequestError, ErrorCode
from apps.common.cache import cacheable, invalidate_cache

wallet_router = Router(tags=["Wallets (20)"])


# =============== CURRENCY ENDPOINTS ===============
@wallet_router.get(
    "/currencies",
    summary="Get all active currencies",
    description="Retrieve a list of all active currencies available for wallet creation",
    response={200: CurrencyListResponseSchema},
    auth=None,
)
@cacheable(key="currencies:list", ttl=3600)  # Cache for 1 hour
async def list_currencies(request):
    currencies = await sync_to_async(list)(
        Currency.objects.filter(is_active=True).order_by("code")
    )
    return CustomResponse.success(
        message="Currencies retrieved successfully", data=currencies
    )


# =============== WALLET MANAGEMENT ENDPOINTS ===============
@wallet_router.post(
    "/create",
    summary="Create a new wallet",
    description="""
        Create a new wallet for the authenticated user
    """,
    response={201: CreateWalletResponseSchema},
)
@invalidate_cache(patterns=["wallets:list:{{user_id}}:*"])
async def create_wallet(request, data: CreateWalletSchema):
    user = request.auth
    wallet = await WalletManager.create_wallet(user, data)
    return CustomResponse.success(
        message="Wallet created successfully", data=wallet, status_code=201
    )


@wallet_router.get(
    "/list",
    summary="Get user wallets",
    description="Retrieve all wallets for the authenticated user",
    response={200: WalletListResponseSchema},
)
@cacheable(key="wallets:list:{{user_id}}", ttl=60)
async def list_wallets(
    request,
    currency_code: str = None,
    wallet_type: WalletType = None,
    status: WalletStatus = None,
):
    user = request.auth

    wallets = await WalletManager.get_user_wallets(
        user=user, currency_code=currency_code, wallet_type=wallet_type, status=status
    )
    return CustomResponse.success(
        message="Wallets retrieved successfully", data=wallets
    )


@wallet_router.get(
    "/wallet/{wallet_id}",
    summary="Get wallet details",
    description="Get detailed information about a specific wallet",
    response={200: CreateWalletResponseSchema},
)
@cacheable(key="wallets:detail:{{wallet_id}}:{{user_id}}", ttl=60)
async def get_wallet(request, wallet_id: UUID):
    user = request.auth

    balance_info = await WalletOperations.get_wallet_balance(user, wallet_id)

    return CustomResponse.success(
        message="Wallet details retrieved successfully", data=balance_info
    )


@wallet_router.put(
    "/wallet/{wallet_id}",
    summary="Update wallet settings",
    description="Update wallet configuration and settings",
    response={200: CreateWalletResponseSchema},
)
@invalidate_cache(
    patterns=["wallets:detail:{{wallet_id}}:*", "wallets:list:{{user_id}}:*"]
)
async def update_wallet(request, wallet_id: UUID, data: UpdateWalletSchema):
    user = request.auth

    wallet = await WalletManager.update_wallet_settings(user, wallet_id, data)
    return CustomResponse.success(message="Wallet updated successfully", data=wallet)


@wallet_router.post(
    "/wallet/{wallet_id}/set-default",
    summary="Set wallet as default",
    description="Set a wallet as the default for its currency",
    response=ResponseSchema,
)
async def set_default_wallet(request, wallet_id: UUID):
    user = request.auth
    await WalletManager.set_default_wallet(user, wallet_id)
    return CustomResponse.success(message="Wallet set as default successfully")


@wallet_router.post(
    "/wallet/{wallet_id}/status",
    summary="Change wallet status",
    description="Change wallet status (activate, freeze, etc.)",
    response=ResponseSchema,
)
async def change_wallet_status(request, wallet_id: UUID, data: WalletStatusSchema):
    user = request.auth
    await WalletManager.change_wallet_status(user, wallet_id, data.status)
    return CustomResponse.success(message="Wallet status updated successfully")


@wallet_router.delete(
    "/wallet/{wallet_id}",
    summary="Delete wallet",
    description="Soft delete a wallet (requires zero balance)",
    response=ResponseSchema,
)
async def delete_wallet(request, wallet_id: UUID):
    user = request.auth
    await WalletManager.delete_wallet(user, wallet_id)
    return CustomResponse.success(message="Wallet deleted successfully")


# =============== WALLET OPERATIONS ENDPOINTS ===============
@wallet_router.get(
    "/wallet/{wallet_id}/balance",
    summary="Get wallet balance",
    description="Get detailed balance information for a wallet",
    response={200: BalanceDataResponseSchema},
)
async def get_wallet_balance(request, wallet_id: UUID):
    user = request.auth
    balance_info = await WalletOperations.get_wallet_balance(user, wallet_id)
    return CustomResponse.success(
        message="Balance retrieved successfully", data=balance_info
    )


@wallet_router.post(
    "/wallet/{wallet_id}/hold",
    summary="Place funds on hold",
    description="Place a temporary hold on wallet funds",
    response=ResponseSchema,
)
async def hold_funds(request, wallet_id: UUID, data: HoldFundsSchema):
    user = request.auth
    hold_result = await WalletOperations.hold_funds(user, wallet_id, data)
    return CustomResponse.success(
        message="Funds placed on hold successfully", data=hold_result
    )


@wallet_router.post(
    "/wallet/{wallet_id}/release",
    summary="Release held funds",
    description="Release previously held funds",
    response=ResponseSchema,
)
async def release_funds(request, wallet_id: UUID, data: ReleaseFundsSchema):
    user = request.auth

    release_result = await WalletOperations.release_hold(
        user=user, wallet_id=wallet_id, amount=data.amount, reference=data.reference
    )

    return CustomResponse.success(
        message="Funds released successfully", data=release_result
    )


@wallet_router.get(
    "/summary",
    summary="Get wallet summary",
    description="Get summary of all user wallets with totals",
    response={200: WalletSummaryDataResponseSchema},
)
async def get_wallet_summary(request):
    user = request.auth
    summary = await WalletOperations.get_wallet_summary(user)
    return CustomResponse.success(
        message="Wallet summary retrieved successfully", data=summary
    )


# =============== SECURITY ENDPOINTS ===============
@wallet_router.post(
    "/wallet/{wallet_id}/auth",
    summary="Verify transaction authorization",
    description="Verify user authorization for wallet transactions",
    response={200: AuthDataResponseSchema},
)
async def verify_transaction_auth(
    request, wallet_id: UUID, data: TransactionAuthSchema
):
    user = request.auth

    auth_result = await WalletSecurityService.verify_transaction_auth(
        user=user,
        wallet_id=wallet_id,
        amount=data.amount,
        pin=data.pin,
        biometric_token=data.biometric_token,
        device_id=data.device_id,
    )

    return CustomResponse.success(
        message="Authorization verified successfully", data=auth_result
    )


@wallet_router.post(
    "/wallet/{wallet_id}/security/enable",
    summary="Enable wallet security features",
    description="Enable PIN and/or biometric security for wallet",
    response={200: SecurityDataResponseSchema},
)
async def enable_wallet_security(request, wallet_id: UUID, data: WalletSecuritySchema):
    user = request.auth

    security_result = await WalletSecurityService.enable_wallet_security(
        user=user,
        wallet_id=wallet_id,
        pin=data.pin,
        enable_biometric=data.enable_biometric,
    )

    return CustomResponse.success(
        message="Security features enabled successfully", data=security_result
    )


@wallet_router.post(
    "/wallet/{wallet_id}/security/disable",
    summary="Disable wallet security features",
    description="Disable PIN and/or biometric security for wallet",
    response={200: SecurityDataResponseSchema},
)
async def disable_wallet_security(
    request, wallet_id: UUID, data: DisableSecuritySchema
):
    user = request.auth

    security_result = await WalletSecurityService.disable_wallet_security(
        user=user,
        wallet_id=wallet_id,
        current_pin=data.current_pin,
        disable_pin=data.disable_pin,
        disable_biometric=data.disable_biometric,
    )

    return CustomResponse.success(
        message="Security features disabled successfully", data=security_result
    )


@wallet_router.post(
    "/wallet/{wallet_id}/pin/set",
    summary="Set wallet PIN",
    description="Set or update wallet PIN",
    response=ResponseSchema,
)
async def set_wallet_pin(request, wallet_id: UUID, data: SetWalletPinSchema):
    user = request.auth
    await WalletManager.set_wallet_pin(user, wallet_id, data.pin)
    return CustomResponse.success(message="Wallet PIN set successfully")


@wallet_router.post(
    "/wallet/{wallet_id}/pin/change",
    summary="Change wallet PIN",
    description="Change existing wallet PIN",
    response=ResponseSchema,
)
async def change_wallet_pin(request, wallet_id: UUID, data: ChangeWalletPinSchema):
    user = request.auth

    await WalletSecurityService.change_wallet_pin(
        user=user,
        wallet_id=wallet_id,
        current_pin=data.current_pin,
        new_pin=data.new_pin,
    )

    return CustomResponse.success(message="Wallet PIN changed successfully")


@wallet_router.get(
    "/wallet/{wallet_id}/security",
    summary="Get wallet security status",
    description="Get current security configuration for wallet",
    response={200: SecurityDataResponseSchema},
)
async def get_wallet_security(request, wallet_id: UUID):
    user = request.auth
    security_status = await WalletSecurityService.get_wallet_security_status(
        user, wallet_id
    )
    return CustomResponse.success(
        message="Security status retrieved successfully", data=security_status
    )


# =============== DEPOSIT WEBHOOK ENDPOINTS ===============
@wallet_router.post(
    "/webhooks/deposit",
    summary="Process deposit webhook (Generic)",
    description="""
        **WEBHOOK ENDPOINT** - Called by payment providers when money is sent to a wallet account number.

        This endpoint processes deposits made to wallet account numbers from external sources.

        **Flow:**
        1. User shares their wallet account number (e.g., 9012345678)
        2. Person sends money to that account via bank transfer
        3. Payment provider sends webhook to this endpoint
        4. Money is credited to wallet automatically
        5. Transaction created and user notified

        **Example:** Friend sends ₦5,000 from GTBank to account 9012345678 → Wallet credited instantly
    """,
    response={200: DepositWebhookDataResponseSchema},
    auth=None,
)
async def process_deposit_webhook(request, data: DepositWebhookSchema):
    """Process incoming deposit webhook - how external money enters wallets"""
    result = await DepositService.process_account_deposit(
        account_number=data.account_number,
        amount=data.amount,
        sender_account_number=data.sender_account_number,
        sender_account_name=data.sender_account_name,
        sender_bank_name=data.sender_bank_name,
        external_reference=data.external_reference,
        narration=data.narration,
        transaction_date=data.transaction_date,
        webhook_payload=data.webhook_payload,
    )

    return CustomResponse.success(message="Deposit processed successfully", data=result)


@wallet_router.post(
    "/webhooks/paystack",
    summary="Process Paystack webhook",
    description="""
        **PAYSTACK WEBHOOK ENDPOINT** - Receives webhooks from Paystack for NGN virtual accounts.

        This endpoint is configured in your Paystack dashboard to receive:
        - charge.success: Payment received to virtual account
        - dedicatedaccount.assign.success: Virtual account created successfully
        - dedicatedaccount.assign.failed: Virtual account creation failed

        **Setup:**
        1. Go to https://dashboard.paystack.com/#/settings/webhooks
        2. Add webhook URL: https://yourdomain.com/api/v1/wallets/webhooks/paystack
        3. Paystack will automatically verify this endpoint

        **Security:**
        - Webhook signature verification using HMAC SHA512
        - Only processes events with valid signatures
        - Prevents replay attacks and tampering
    """,
    response={200: ResponseSchema},
    auth=None,
)
async def process_paystack_webhook(request):
    """
    Process Paystack webhook events.

    Paystack sends webhooks with:
    - Raw body (JSON)
    - x-paystack-signature header (HMAC SHA512)
    """

    # Get raw body for signature verification
    body = request.body
    signature = request.headers.get("x-paystack-signature", "")

    # Get Paystack provider for webhook verification
    test_mode = AccountProviderFactory.get_test_mode_setting()
    provider = AccountProviderFactory.get_provider(
        AccountProvider.PAYSTACK, test_mode=test_mode
    )

    # Verify webhook signature
    is_valid = await provider.verify_webhook_signature(body, signature)
    if not is_valid:
        raise RequestError(
            err_code=ErrorCode.VALIDATION_ERROR,
            err_msg="Invalid webhook signature",
            status_code=400,
        )

    # Parse webhook payload
    payload = json.loads(body)

    # Parse event into standardized format
    event_data = provider.parse_webhook_event(payload)

    # Handle charge.success event (payment received)
    if event_data.get("event_type") == "payment.success":
        # Process deposit
        result = await DepositService.process_account_deposit(
            account_number=event_data["account_number"],
            amount=event_data["amount"],
            sender_account_number=event_data.get("sender_account_number", ""),
            sender_account_name=event_data.get("sender_account_name", ""),
            sender_bank_name=event_data.get("sender_bank_name", ""),
            external_reference=event_data["external_reference"],
            narration=f"Paystack deposit - {event_data['external_reference']}",
            transaction_date=None,
            webhook_payload=payload,
        )

        return CustomResponse.success(
            message="Paystack webhook processed successfully",
            data={"event": "charge.success", "processed": True},
        )

    return CustomResponse.success(
        message="Paystack webhook received",
        data={"event": event_data.get("event_type"), "processed": False},
    )
