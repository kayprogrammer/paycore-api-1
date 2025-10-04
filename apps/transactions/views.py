from uuid import UUID
from ninja import Query, Router
from ninja.throttling import AuthRateThrottle

from apps.common.exceptions import NotFoundError
from apps.transactions.schemas import (
    InitiateTransferSchema,
    InitiateDepositSchema,
    InitiateWithdrawalSchema,
    CreateDisputeSchema,
    TransactionFilterSchema,
    TransactionResponseSchema,
    TransactionDetailResponseSchema,
    TransactionReceiptResponseSchema,
    TransactionListResponseSchema,
    TransactionStatsResponseSchema,
    DisputeResponseSchema,
    DisputeListResponseSchema,
    DisputeStatus,
)
from apps.transactions.transaction_operations import TransactionOperations
from apps.transactions.dispute_service import DisputeService
from apps.common.responses import CustomResponse
from apps.common.schemas import PaginationQuerySchema, ResponseSchema
from apps.wallets.models import Wallet

transaction_router = Router(tags=["Transactions"])


# =============== TRANSACTION ENDPOINTS ===============
@transaction_router.post(
    "/transfer",
    summary="Initiate a transfer",
    description="""
        Transfer funds from one wallet to another.
        Requires authentication and may require PIN verification depending on wallet settings.
    """,
    response={200: TransactionReceiptResponseSchema},
    throttle=AuthRateThrottle("50/m"),
)
async def initiate_transfer(request, data: InitiateTransferSchema):
    """Initiate a wallet-to-wallet transfer"""
    user = request.auth
    from_wallet = await Wallet.objects.aget_or_none(user=user, is_default=True)
    if not from_wallet:
        raise NotFoundError("No wallet found")

    result = await TransactionOperations.initiate_transfer(
        user=user,
        from_wallet_id=from_wallet.wallet_id,
        to_wallet_id=data.to_wallet_id,
        amount=data.amount,
        description=data.description,
        reference=data.reference,
        pin=data.pin,
    )

    return CustomResponse.success(
        message="Transfer initiated successfully", data=result
    )


@transaction_router.get(
    "/list",
    summary="List user transactions",
    description="Get paginated list of user transactions with filtering options",
    response={200: TransactionListResponseSchema},
)
async def list_transactions(
    request,
    filters: Query[TransactionFilterSchema] = Query(...),
    page_params: Query[PaginationQuerySchema] = Query(...),
):
    user = request.auth
    result = await TransactionOperations.list_user_transactions(
        user, filters, page_params
    )
    return CustomResponse.success(
        message="Transactions retrieved successfully", data=result
    )


@transaction_router.get(
    "/transaction/{transaction_id}",
    summary="Get transaction details",
    description="Get detailed information about a specific transaction",
    response={200: TransactionDetailResponseSchema},
)
async def get_transaction(request, transaction_id: UUID):
    user = request.auth
    result = await TransactionOperations.get_transaction_detail(user, transaction_id)
    return CustomResponse.success(
        message="Transaction details retrieved successfully", data=result
    )


@transaction_router.get(
    "/wallet/{wallet_id}/transactions",
    summary="Get wallet transactions",
    description="Get all transactions for a specific wallet",
    response={200: TransactionListResponseSchema},
)
async def get_wallet_transactions(
    request,
    wallet_id: UUID,
    filters: Query[TransactionFilterSchema] = Query(...),
    page_params: Query[PaginationQuerySchema] = Query(...),
):
    user = request.auth
    wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
    if not wallet:
        raise NotFoundError("Wallet not found")
    result = await TransactionOperations.list_user_transactions(
        user, filters, page_params, wallet_id=wallet_id
    )
    return CustomResponse.success(
        message="Wallet transactions retrieved successfully", data=result
    )


@transaction_router.get(
    "/stats",
    summary="Get transaction statistics",
    description="Get aggregated transaction statistics for the user",
    response={200: TransactionStatsResponseSchema},
)
async def get_transaction_stats(request):
    user = request.auth
    result = await TransactionOperations.get_transaction_stats(user)
    return CustomResponse.success(
        message="Transaction statistics retrieved successfully", data=result
    )


# =============== DEPOSIT & WITHDRAWAL ENDPOINTS ===============
@transaction_router.post(
    "/deposit/initiate",
    summary="Initiate a deposit",
    description="""
        Initiate a deposit to a wallet.
        This creates a pending transaction that will be completed when payment is confirmed.
    """,
    response={200: TransactionResponseSchema},
    throttle=AuthRateThrottle("10/m"),
)
async def initiate_deposit(request, data: InitiateDepositSchema):
    """Initiate a deposit (placeholder - integrate with payment gateway)"""
    user = request.auth

    # This is a placeholder - integrate with actual payment gateway
    # For now, we'll return a pending transaction

    return CustomResponse.success(
        message="Deposit initiated successfully. Please complete payment.",
        data={
            "transaction_id": "pending",
            "amount": data.amount,
            "payment_method": data.payment_method,
            "status": "pending",
            "next_step": "Complete payment via payment gateway",
        },
    )


@transaction_router.post(
    "/withdrawal/initiate",
    summary="Initiate a withdrawal",
    description="""
        Initiate a withdrawal from wallet to external account.
        Requires PIN verification and sufficient balance.
    """,
    response={200: TransactionResponseSchema},
    throttle=AuthRateThrottle("10/m"),
)
async def initiate_withdrawal(request, data: InitiateWithdrawalSchema):
    """Initiate a withdrawal (placeholder - integrate with payout service)"""
    user = request.auth

    # This is a placeholder - integrate with actual payout service
    # Verify wallet, balance, PIN, etc.

    return CustomResponse.success(
        message="Withdrawal initiated successfully. Processing payout.",
        data={
            "transaction_id": "pending",
            "amount": data.amount,
            "destination": data.destination,
            "status": "processing",
            "estimated_completion": "1-3 business days",
        },
    )


# =============== DISPUTE ENDPOINTS ===============
@transaction_router.post(
    "/transaction/{transaction_id}/dispute",
    summary="Create a transaction dispute",
    description="""
        Create a dispute for a completed transaction.
        Disputes must be filed within 30 days of transaction completion.
    """,
    response={200: DisputeResponseSchema},
    throttle=AuthRateThrottle("5/m"),
)
async def create_dispute(request, transaction_id: UUID, data: CreateDisputeSchema):
    user = request.auth

    result = await DisputeService.create_dispute(
        user=user,
        transaction_id=transaction_id,
        dispute_type=data.dispute_type,
        reason=data.reason,
        disputed_amount=data.disputed_amount,
        evidence=data.evidence,
    )

    return CustomResponse.success(message="Dispute created successfully", data=result)


@transaction_router.get(
    "/disputes/list",
    summary="List user disputes",
    description="Get all disputes initiated by or involving the user",
    response={200: DisputeListResponseSchema},
)
async def list_disputes(
    request,
    status: DisputeStatus = None,
    page_params: Query[PaginationQuerySchema] = Query(...),
):
    user = request.auth

    result = await DisputeService.list_user_disputes(user, status, page_params)
    return CustomResponse.success(
        message="Disputes retrieved successfully", data=result
    )


@transaction_router.get(
    "/disputes/{dispute_id}",
    summary="Get dispute details",
    description="Get detailed information about a specific dispute",
    response={200: DisputeResponseSchema},
)
async def get_dispute(request, dispute_id: UUID):
    user = request.auth
    result = await DisputeService.get_dispute_detail(user, dispute_id)
    return CustomResponse.success(
        message="Dispute details retrieved successfully", data=result
    )


@transaction_router.post(
    "/disputes/{dispute_id}/evidence",
    summary="Add evidence to dispute",
    description="Add supporting evidence to an existing dispute",
    response=ResponseSchema,
    throttle=AuthRateThrottle("10/m"),
)
async def add_dispute_evidence(request, dispute_id: UUID, evidence: dict):
    user = request.auth
    await DisputeService.add_evidence_to_dispute(
        user=user, dispute_id=dispute_id, evidence=evidence
    )
    return CustomResponse.success(message="Evidence added successfully")