from uuid import UUID
from ninja import FilterSchema
from pydantic import Field
from decimal import Decimal
from typing import Optional, List
from datetime import datetime

from apps.common.doc_examples import DATE_EXAMPLE, UUID_EXAMPLE
from apps.common.schemas import BaseSchema, PaginatedResponseDataSchema, ResponseSchema
from apps.transactions.models import (
    TransactionType,
    TransactionStatus,
    TransactionDirection,
    DisputeType,
    DisputeStatus,
)


# =============== FILTER SCHEMAS ===============
class TransactionFilterSchema(FilterSchema):
    transaction_type: Optional[TransactionType] = None
    status: Optional[TransactionStatus] = None
    direction: Optional[TransactionDirection] = None
    start_date: Optional[datetime] = Field(
        None, example=DATE_EXAMPLE, q=["created_at__gte"]
    )
    end_date: Optional[datetime] = Field(
        None, example=DATE_EXAMPLE, q=["created_at__lte"]
    )
    min_amount: Optional[Decimal] = Field(
        None, example=10.00, ge=0, q=["net_amount__gte"]
    )
    max_amount: Optional[Decimal] = Field(
        None, example=1000.00, ge=0, q=["net_amount__lte"]
    )
    search: Optional[str] = Field(
        None,
        example="payment",
        q=[
            "description__icontains",
            "reference__icontains",
            "external_reference__icontains",
        ],
    )


# =============== REQUEST SCHEMAS ===============
class InitiateTransferSchema(BaseSchema):
    """Schema for initiating a wallet-to-wallet transfer"""

    from_wallet_id: UUID = Field(
        ..., example=UUID_EXAMPLE, description="Source wallet ID"
    )
    to_wallet_id: UUID = Field(
        ..., example=UUID_EXAMPLE, description="Destination wallet ID"
    )
    amount: Decimal = Field(..., example=100.50, gt=0, description="Amount to transfer")
    description: Optional[str] = Field(None, example="Payment for services")
    reference: Optional[str] = Field(None, example="INV-2024-001")
    pin: Optional[str] = Field(
        None,
        example="1234",
        min_length=4,
        max_length=6,
        description="Wallet PIN if required",
    )
    biometric_token: Optional[str] = Field(
        None, description="Biometric authentication token"
    )
    device_id: Optional[str] = Field(
        None, example="device_12345", description="Device ID for biometric verification"
    )


class InitiateDepositSchema(BaseSchema):
    wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    amount: Decimal = Field(..., example=500.00, gt=0)
    payment_method: str = Field(..., example="bank_transfer")
    description: Optional[str] = Field(None, example="Top up wallet")
    external_reference: Optional[str] = Field(None, example="BNK-REF-123")


class InitiateWithdrawalSchema(BaseSchema):
    wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    amount: Decimal = Field(..., example=200.00, gt=0)
    destination: str = Field(..., example="bank_account")
    account_details: dict = Field(..., example={"account_number": "1234567890"})
    description: Optional[str] = Field(None, example="Withdraw to bank")
    pin: Optional[int] = Field(None, example=1234, gt=999, lt=10000)


class CreateDisputeSchema(BaseSchema):
    dispute_type: DisputeType = Field(..., example=DisputeType.UNAUTHORIZED)
    reason: str = Field(
        ..., min_length=10, max_length=1000, example="Transaction not authorized by me"
    )
    disputed_amount: Optional[Decimal] = Field(None, example=50.00, gt=0)
    evidence: Optional[dict] = Field(None, example={"screenshot": "url_to_proof"})


class ResolveDisputeSchema(BaseSchema):
    resolution_notes: str = Field(
        ..., min_length=10, example="Dispute resolved in favor of customer"
    )
    refund_amount: Optional[Decimal] = Field(None, example=50.00, ge=0)


# =============== RESPONSE SCHEMAS ===============
class TransactionFeeSchema(BaseSchema):
    fee_type: str = Field(..., example="processing")
    amount: Decimal = Field(..., example=2.50)
    percentage: Optional[Decimal] = Field(None, example=2.5)
    description: Optional[str] = Field(None, example="Processing fee")


class TransactionSchema(BaseSchema):
    transaction_id: UUID = Field(..., example=UUID_EXAMPLE)
    transaction_type: TransactionType
    status: TransactionStatus
    direction: TransactionDirection = None
    amount: Decimal = Field(..., example=100.50)
    fee_amount: Decimal = Field(..., example=2.50)
    net_amount: Decimal = Field(..., example=98.00)
    currency_code: str = Field(None, example="USD", alias="from_wallet.currency.code")
    description: Optional[str] = Field(None, example="Payment for services")
    reference: Optional[str] = Field(None, example="TXN-001")
    from_user_name: Optional[str] = Field(
        None, example="John Doe", alias="from_user.full_name"
    )
    to_user_name: Optional[str] = Field(
        None, example="Jane Smith", alias="to_user.full_name"
    )
    from_wallet_name: Optional[str] = Field(
        None, example="Main Wallet", alias="from_wallet.name"
    )
    to_wallet_name: Optional[str] = Field(
        None, example="Savings Wallet", alias="to_wallet.name"
    )
    initiated_at: datetime = Field(..., example=DATE_EXAMPLE)
    completed_at: Optional[datetime] = Field(None, example=DATE_EXAMPLE)
    failure_reason: Optional[str] = Field(None, example="Insufficient funds")
    metadata: dict = Field(default_factory=dict)

    @staticmethod
    def resolve_reference(obj):
        if not obj.reference:
            provider_resp = obj.metadata.get("provider_response", {})
            return obj.metadata.get("reference", None) or provider_resp.get(
                "reference", None
            )
        return obj.reference


class TransactionDetailSchema(TransactionSchema):
    from_balance_before: Optional[Decimal] = Field(None, example=500.00)
    from_balance_after: Optional[Decimal] = Field(None, example=400.00)
    to_balance_before: Optional[Decimal] = Field(None, example=200.00)
    to_balance_after: Optional[Decimal] = Field(None, example=300.00)
    fees: List[TransactionFeeSchema] = Field(default_factory=list)
    has_dispute: bool = Field(default=False)
    can_dispute: bool = Field(default=True)
    can_reverse: bool = Field(default=False)


class DisputeSchema(BaseSchema):
    dispute_id: UUID = Field(..., example=UUID_EXAMPLE)
    transaction_id: UUID = Field(..., example=UUID_EXAMPLE)
    status: DisputeStatus
    dispute_type: DisputeType
    reason: str
    disputed_amount: Decimal = Field(..., example=50.00)
    initiated_by: str = Field(..., example="John Doe", alias="initiated_by.full_name")
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = Field(..., example=DATE_EXAMPLE)


class TransactionStatsSchema(BaseSchema):
    total_transactions: int = Field(..., example=150)
    total_sent: Decimal = Field(..., example=5000.00)
    total_received: Decimal = Field(..., example=7500.00)
    total_fees: Decimal = Field(..., example=125.00)
    successful_count: int = Field(..., example=145)
    failed_count: int = Field(..., example=3)
    pending_count: int = Field(..., example=2)
    average_transaction_amount: Decimal = Field(..., example=83.33)


class TransactionReceiptSchema(BaseSchema):
    transaction_id: UUID = Field(..., example=UUID_EXAMPLE)
    transaction_type: TransactionType
    status: TransactionStatus
    amount: Decimal = Field(..., example=100.50)
    fee_amount: Decimal = Field(..., example=2.50)
    total_amount: Decimal = Field(..., example=103.00)
    currency_code: str = Field(..., example="USD")
    from_wallet: str = Field(..., example="Main Wallet")
    to_wallet: Optional[str] = Field(None, example="Recipient Wallet")
    description: Optional[str] = None
    reference: Optional[str] = None
    timestamp: datetime = Field(..., example=DATE_EXAMPLE)


class PaginatedTransactionsSchema(PaginatedResponseDataSchema):
    transactions: List[TransactionSchema] = Field(..., alias="items")


class BankSchema(BaseSchema):
    name: str = Field(..., example="Bank of America")
    code: str = Field(..., example="BOA")
    currency: str = Field(..., example="USD")


class BankAccountSchema(BaseSchema):
    account_number: str = Field(..., example="1234567890")
    account_name: str = Field(..., example="JANE JOHNSON")
    bank_code: str = Field(..., example="033")
    bank_name: str = Field(..., example="United Bank for Africa")


# =============== API RESPONSE WRAPPERS ===============
class TransactionResponseSchema(ResponseSchema):
    data: TransactionSchema


class TransactionDetailResponseSchema(ResponseSchema):
    data: TransactionDetailSchema


class TransactionReceiptResponseSchema(ResponseSchema):
    data: TransactionReceiptSchema


class TransactionListResponseSchema(ResponseSchema):
    data: PaginatedTransactionsSchema


class TransactionStatsResponseSchema(ResponseSchema):
    data: TransactionStatsSchema


class DisputeResponseSchema(ResponseSchema):
    data: DisputeSchema


class DisputePaginatedDataSchema(PaginatedResponseDataSchema):
    disputes: List[DisputeSchema] = Field(..., alias="items")


class DisputeListResponseSchema(ResponseSchema):
    data: DisputePaginatedDataSchema


class BankListResponseDataSchema(BaseSchema):
    currency: str = Field(..., example="USD")
    banks: List[BankSchema]
    count: int


class BanksResponseSchema(ResponseSchema):
    data: BankListResponseDataSchema


class BankAccountResponseSchema(ResponseSchema):
    data: BankAccountSchema
