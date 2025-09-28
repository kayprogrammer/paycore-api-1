from uuid import UUID
from ninja import Router
from ninja.throttling import AuthRateThrottle

from apps.wallets.models import WalletStatus, WalletType
from apps.wallets.services.wallet_manager import WalletManager
from apps.wallets.services.wallet_operations import WalletOperations
from apps.wallets.services.security_service import WalletSecurityService
from apps.wallets.schemas import (
    CreateWalletSchema,
    CreateWalletResponseSchema,
    UpdateWalletSchema,
    SetWalletPinSchema,
    ChangeWalletPinSchema,
    WalletStatusSchema,
    WalletListResponseSchema,
    TransferSchema,
    TransferDataResponseSchema,
    InternalTransferSchema,
    HoldFundsSchema,
    ReleaseFundsSchema,
    BalanceDataResponseSchema,
    TransactionAuthSchema,
    AuthDataResponseSchema,
    WalletSecuritySchema,
    SecurityDataResponseSchema,
    DisableSecuritySchema,
    WalletSummaryDataResponseSchema,
)
from apps.common.responses import CustomResponse
from apps.common.schemas import ResponseSchema

wallet_router = Router(tags=["Wallets"])


# =============== WALLET MANAGEMENT ENDPOINTS ===============
@wallet_router.post(
    "/create",
    summary="Create a new wallet",
    description="""
        Create a new wallet for the authenticated user
    """,
    response={201: CreateWalletResponseSchema},
)
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
    "/wallet/{wallet_id}/transfer",
    summary="Transfer to another wallet",
    description="Transfer funds from this wallet to another wallet",
    response={200: TransferDataResponseSchema},
    throttle=AuthRateThrottle("20/m"),
)
async def transfer_funds(request, wallet_id: UUID, data: TransferSchema):
    user = request.auth
    transfer_result = await WalletOperations.transfer_between_wallets(
        user, wallet_id, data
    )
    return CustomResponse.success(
        message="Transfer completed successfully", data=transfer_result
    )


@wallet_router.post(
    "/internal-transfer",
    summary="Internal transfer between own wallets",
    description="Transfer funds between user's own wallets",
    response={200: TransferDataResponseSchema},
)
async def internal_transfer(request, data: InternalTransferSchema):
    user = request.auth

    transfer_result = await WalletOperations.internal_transfer(
        user=user,
        from_wallet_id=data.from_wallet_id,
        to_wallet_id=data.to_wallet_id,
        amount=data.amount,
        description=data.description,
    )

    return CustomResponse.success(
        message="Internal transfer completed successfully", data=transfer_result
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
