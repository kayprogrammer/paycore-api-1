from uuid import UUID
from ninja import Query, Router
from ninja.throttling import AuthRateThrottle

from apps.common.exceptions import NotFoundError
from apps.transactions.schemas import (
    BanksResponseSchema,
    BankAccountResponseSchema,
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
from apps.transactions.services.providers.withdrawal_factory import (
    WithdrawalProviderFactory,
)
from apps.transactions.services.transaction_operations import TransactionOperations
from apps.transactions.services.dispute_service import DisputeService
from apps.transactions.services.deposit_manager import DepositManager
from apps.transactions.services.withdrawal_manager import WithdrawalManager
from apps.common.responses import CustomResponse
from apps.common.schemas import PaginationQuerySchema, ResponseSchema
from apps.wallets.models import Wallet
from apps.common.cache import cacheable, invalidate_cache
from apps.transactions.tasks import DepositTasks
from django.conf import settings

transaction_router = Router(tags=["Transactions (14)"])


# =============== TRANSACTION ENDPOINTS ===============
@transaction_router.post(
    "/transfer",
    summary="Initiate a wallet transfer",
    description="""
        Transfer funds from one wallet to another with comprehensive security.

        **Features:**
        - Supports PIN and/or biometric authentication
        - Automatic currency conversion if wallets use different currencies
        - Transparent fee calculation and breakdown
        - Atomic operation - either completes fully or rolls back entirely
        - Complete audit trail with balance snapshots

        **Security:**
        - PIN verification if wallet requires it
        - Biometric authentication if wallet requires it
        - Balance and spending limit validation
        - Wallet status verification

        **Fees:**
        - External transfers: 1% of amount
        - Currency conversion: 0.5% of amount (if applicable)

        All fee details are itemized in the transaction record.
    """,
    response={200: TransactionReceiptResponseSchema},
    throttle=AuthRateThrottle("100/m"),
)
@invalidate_cache(
    patterns=[
        "transactions:list:{{user_id}}:*",
        "wallets:detail:*",
        "wallets:list:{{user_id}}:*",
    ]
)
async def initiate_transfer(request, data: InitiateTransferSchema):
    user = request.auth
    result = await TransactionOperations.initiate_transfer(
        user=user, **data.model_dump()
    )
    return CustomResponse.success(
        message="Transfer completed successfully", data=result
    )


@transaction_router.get(
    "/list",
    summary="List user transactions",
    description="Get paginated list of user transactions with filtering options",
    response={200: TransactionListResponseSchema},
)
@cacheable(key="transactions:list:{{user_id}}", ttl=30)
async def list_transactions(
    request,
    filters: TransactionFilterSchema = Query(...),
    page_params: PaginationQuerySchema = Query(...),
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
@cacheable(key="transactions:detail:{{transaction_id}}:{{user_id}}", ttl=300)
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
    filters: TransactionFilterSchema = Query(...),
    page_params: PaginationQuerySchema = Query(...),
):
    user = request.auth
    wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
    if not wallet:
        raise NotFoundError("Wallet not found")
    result = await TransactionOperations.list_user_transactions(
        user, filters, page_params, wallet_id=wallet.id
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

        Supports multiple payment providers:
        - Internal: Instant completion for testing (when USE_INTERNAL_PROVIDER=True)
        - Paystack: Card, Bank Transfer, USSD, QR (for NGN)
        - Flutterwave: Coming soon

        Returns payment URL for external providers or instant completion for internal.
    """,
    response={200: TransactionResponseSchema},
    throttle=AuthRateThrottle("200/m"),
)
async def initiate_deposit(request, data: InitiateDepositSchema):
    """Initiate a deposit using configured payment provider"""
    user = request.auth

    callback_url = None
    if request.build_absolute_uri:
        callback_url = request.build_absolute_uri("/transactions/deposit/verify")

    transaction, payment_info = await DepositManager.initiate_deposit(
        user=user,
        wallet_id=data.wallet_id,
        amount=data.amount,
        payment_method=data.payment_method,
        callback_url=callback_url,
        description=data.description,
    )
    if settings.USE_INTERNAL_PROVIDER:
        # Schedule auto-confirmation after 5 seconds
        DepositTasks.auto_confirm_deposit.apply_async(
            args=[str(transaction.transaction_id)], countdown=5  # 5 second delay
        )

    return CustomResponse.success(
        message=(
            "Deposit initiated successfully"
            if payment_info["status"] == "pending"
            else "Deposit completed successfully"
        ),
        data=transaction,
    )


@transaction_router.get(
    "/deposit/verify/{reference}",
    summary="Verify deposit status",
    description="""
        Verify the status of a deposit transaction.
        Can be called after payment to confirm completion.
    """,
    response={200: TransactionResponseSchema},
)
async def verify_deposit(request, reference: str):
    """Verify deposit transaction status"""
    user = request.auth

    # Verify and complete deposit
    transaction = await DepositManager.verify_and_complete_deposit(reference=reference)

    # Check if transaction belongs to user
    if transaction.to_user_id != user.id:
        raise NotFoundError("Transaction not found")
    return CustomResponse.success(
        message=f"Deposit {transaction.status}", data=transaction
    )


@transaction_router.post(
    "/withdrawal/initiate",
    summary="Initiate a withdrawal",
    description="""
        Initiate a withdrawal from wallet to bank account.

        Supports multiple payment providers:
        - Internal: Instant completion for testing (when USE_INTERNAL_PROVIDER=True)
        - Paystack: Bank transfers for NGN (Nigerian banks)
        - Flutterwave: Coming soon (multi-currency support)

        **Requirements:**
        - Active wallet with sufficient balance
        - PIN verification (if wallet requires PIN)
        - Valid bank account details (account_number, bank_code, account_name)

        **Process:**
        1. Validates wallet and balance
        2. Verifies PIN if required
        3. Creates withdrawal transaction
        4. Initiates transfer with provider
        5. Debits wallet immediately
        6. Returns withdrawal status and details
    """,
    response={200: TransactionResponseSchema},
    throttle=AuthRateThrottle("10/m"),
)
async def initiate_withdrawal(request, data: InitiateWithdrawalSchema):
    """Initiate a withdrawal to bank account using configured provider"""
    user = request.auth

    transaction, withdrawal_info = await WithdrawalManager.initiate_withdrawal(
        user=user,
        wallet_id=data.wallet_id,
        amount=data.amount,
        account_details=data.account_details,
        pin=str(data.pin) if data.pin else None,
        description=data.description,
    )

    return CustomResponse.success(
        message=(
            "Withdrawal initiated successfully"
            if withdrawal_info["status"] == "pending"
            else "Withdrawal completed successfully"
        ),
        data=transaction,
    )


@transaction_router.post(
    "/withdrawal/verify",
    summary="Verify a withdrawal",
    description="""
        Verify and update withdrawal transaction status.

        Can be used for:
        - Manual verification after webhook
        - Polling for status updates
        - Confirming completion

        Automatically refunds wallet if withdrawal failed.
    """,
    response={200: TransactionResponseSchema},
    throttle=AuthRateThrottle("20/m"),
)
async def verify_withdrawal(
    request, transaction_id: UUID = None, reference: str = None
):
    """Verify withdrawal status and update transaction"""
    user = request.auth

    transaction = await WithdrawalManager.verify_and_complete_withdrawal(
        transaction_id=transaction_id, reference=reference
    )

    # Verify user owns the transaction
    if transaction.from_user_id != user.id:
        raise NotFoundError("Transaction not found")

    return CustomResponse.success(
        message="Withdrawal verification complete", data=transaction
    )


@transaction_router.get(
    "/withdrawal/banks",
    summary="Get list of banks for withdrawals",
    description="""
        Get list of supported banks for withdrawals.

        Optionally filter by currency code.
        Returns bank name, code, and currency.
    """,
    response={200: BanksResponseSchema},
    throttle=AuthRateThrottle("30/m"),
)
async def get_withdrawal_banks(request, currency_code: str = "NGN"):
    """Get list of banks for withdrawals"""
    test_mode = WithdrawalProviderFactory.get_test_mode_setting()
    provider = WithdrawalProviderFactory.get_provider_for_currency(
        currency_code, test_mode=test_mode
    )
    banks = await provider.get_banks(currency_code=currency_code)

    return CustomResponse.success(
        message=f"Retrieved {len(banks)} banks for {currency_code}",
        data={"currency": currency_code, "banks": banks, "count": len(banks)},
    )


@transaction_router.post(
    "/withdrawal/verify-account",
    summary="Verify bank account number",
    description="""
        Verify bank account number and resolve account name.

        Uses provider's account resolution API to confirm:
        - Account number is valid
        - Account name matches
        - Bank details are correct

        Required for withdrawal verification.
    """,
    response={200: BankAccountResponseSchema},
    throttle=AuthRateThrottle("10/m"),
)
async def verify_bank_account(
    request,
    account_number: str = Query(...),
    bank_code: str = Query(...),
    currency_code: str = "NGN",
):
    test_mode = WithdrawalProviderFactory.get_test_mode_setting()
    provider = WithdrawalProviderFactory.get_provider_for_currency(
        currency_code, test_mode=test_mode
    )

    account_info = await provider.verify_account_number(
        account_number=account_number, bank_code=bank_code
    )

    return CustomResponse.success(
        message="Account verified successfully", data=account_info, status_code=200
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
    throttle=AuthRateThrottle("100/m"),
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
    page_params: PaginationQuerySchema = Query(...),
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
