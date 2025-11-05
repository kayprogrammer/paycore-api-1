from locale import currency
from uuid import UUID
from ninja import ModelSchema
from pydantic import Field, constr, field_validator
from decimal import Decimal
from typing import Annotated, Optional, List
from datetime import datetime

from apps.common.doc_examples import DATE_EXAMPLE, UUID_EXAMPLE
from apps.common.schemas import BaseSchema, ResponseSchema, UserDataSchema
from apps.transactions.models import Transaction
from apps.wallets.models import PaymentFrequency, SplitPaymentType, WalletStatus


# =============== CURRENCY SCHEMAS ===============
class CurrencySchema(BaseSchema):
    code: str = Field(..., example="USD")
    name: str = Field(..., example="US Dollar")
    symbol: str = Field(..., example="$")
    decimal_places: int = Field(..., example=2)
    is_crypto: bool = Field(..., example=False)


class CurrencyListResponseSchema(ResponseSchema):
    data: List[CurrencySchema]


# =============== WALLET MANAGEMENT SCHEMAS ===============
class CreateWalletSchema(BaseSchema):
    currency_code: str = Field(..., example="USD", max_length=10)
    name: str = Field(..., example="My Main Wallet", max_length=100)
    wallet_type: str = Field(default="main", example="main")
    is_default: bool = Field(default=False, example=False)
    description: Optional[str] = Field(None, example="My primary spending wallet")


class UpdateWalletSchema(BaseSchema):
    name: Optional[str] = Field(None, example="Updated Wallet Name", max_length=100)
    description: Optional[str] = Field(None, example="Updated description")
    daily_limit: Optional[Decimal] = Field(None, example=1000.00, ge=0)
    monthly_limit: Optional[Decimal] = Field(None, example=5000.00, ge=0)
    requires_pin: Optional[bool] = Field(False, example=True)
    requires_biometric: Optional[bool] = Field(None, example=False)


class SetWalletPinSchema(BaseSchema):
    pin: int = Field(example=1234, gt=999, lt=10000)


class ChangeWalletPinSchema(BaseSchema):
    current_pin: int = Field(..., example=1234, gt=999, lt=10000)
    new_pin: int = Field(..., example=5678, gt=999, lt=10000)


class WalletStatusSchema(BaseSchema):
    status: WalletStatus = Field(..., example=WalletStatus.ACTIVE)


# =============== WALLET OPERATIONS SCHEMAS ===============
class TransferSchema(BaseSchema):
    to_wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    amount: Decimal = Field(..., example=100.50, gt=0)
    description: Optional[str] = Field(None, example="Payment for dinner")
    pin: Optional[int] = Field(None, example=1234, gt=999, lt=10000)
    reference: Optional[str] = Field(None, example="REF123456")


class InternalTransferSchema(BaseSchema):
    from_wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    to_wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    amount: Decimal = Field(..., example=250.00, gt=0)
    description: Optional[str] = Field(None, example="Transfer to savings")


class HoldFundsSchema(BaseSchema):
    amount: Decimal = Field(..., example=50.00, gt=0)
    reference: Optional[str] = Field(None, example="HOLD_REF_123")
    expires_at: Optional[datetime] = Field(None, example=DATE_EXAMPLE)


class ReleaseFundsSchema(BaseSchema):
    amount: Decimal = Field(..., example=50.00, gt=0)
    reference: Optional[str] = Field(None, example="HOLD_REF_123")


# =============== SECURITY SCHEMAS ===============
class TransactionAuthSchema(BaseSchema):
    amount: Decimal = Field(..., example=100.00, gt=0)
    pin: Optional[int] = Field(None, example=1234, gt=999, lt=10000)
    device_id: Optional[str] = Field(None, example="device_12345")
    biometric_token: Optional[str] = Field(None)


class WalletSecuritySchema(BaseSchema):
    pin: Optional[int] = Field(None, example=1234, gt=999, lt=10000)
    enable_biometric: bool = Field(default=False, example=True)
    device_id: Optional[str] = Field(None, example="device_12345")


class DisableSecuritySchema(BaseSchema):
    current_pin: Optional[int] = Field(None, example=1234, gt=999, lt=10000)
    disable_pin: bool = Field(default=False, example=True)
    disable_biometric: bool = Field(default=False, example=False)


# =============== VIRTUAL CARD SCHEMAS ===============
class CreateVirtualCardSchema(BaseSchema):
    wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    nickname: Optional[str] = Field(None, example="Netflix Card", max_length=50)
    spending_limit: Optional[Decimal] = Field(None, example=500.00, ge=0)
    created_for_merchant: Optional[str] = Field(None, example="Netflix", max_length=100)


class UpdateVirtualCardSchema(BaseSchema):
    nickname: Optional[str] = Field(None, example="Updated Card Name")
    spending_limit: Optional[Decimal] = Field(None, example=1000.00, ge=0)
    is_active: Optional[bool] = Field(None, example=True)
    is_frozen: Optional[bool] = Field(None, example=False)


# =============== QR CODE SCHEMAS ===============
class CreateQRCodeSchema(BaseSchema):
    wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    amount: Optional[Decimal] = Field(None, example=25.00, ge=0)
    description: Optional[str] = Field(None, example="Coffee payment")
    is_single_use: bool = Field(default=False, example=True)
    is_amount_fixed: bool = Field(default=False, example=True)
    expires_at: Optional[datetime] = Field(None, example=DATE_EXAMPLE)


class PayQRCodeSchema(BaseSchema):
    qr_id: UUID = Field(..., example=UUID_EXAMPLE)
    amount: Optional[Decimal] = Field(None, example=25.00, gt=0)
    from_wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    pin: Optional[int] = Field(None, example=1234, gt=999, lt=10000)


# =============== SPLIT PAYMENT SCHEMAS ===============
class CreateSplitPaymentSchema(BaseSchema):
    total_amount: Decimal = Field(..., example=120.00, gt=0)
    currency_code: str = Field(..., example="USD")
    description: str = Field(..., example="Dinner at restaurant")
    split_type: SplitPaymentType = Field(
        default=SplitPaymentType.EQUAL, example=SplitPaymentType.EQUAL
    )
    participants: List[str] = Field(
        ..., example=["user1@example.com", "user2@example.com"]
    )
    custom_amounts: Optional[List[Decimal]] = Field(None, example=[40.00, 80.00])
    due_date: Optional[datetime] = Field(None, example=DATE_EXAMPLE)


class PaySplitPaymentSchema(BaseSchema):
    payment_id: UUID = Field(..., example=UUID_EXAMPLE)
    wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    amount: Optional[Decimal] = Field(None, example=40.00, gt=0)
    pin: Optional[int] = Field(None, example=1234, gt=999, lt=10000)


# =============== RECURRING PAYMENT SCHEMAS ===============
class CreateRecurringPaymentSchema(BaseSchema):
    from_wallet_id: UUID = Field(..., example=UUID_EXAMPLE)
    to_wallet_id: Optional[UUID] = Field(None, example=UUID_EXAMPLE)
    to_external: Optional[str] = Field(None, example="external_account_123")
    amount: Decimal = Field(..., example=50.00, gt=0)
    frequency: PaymentFrequency = Field(..., example=PaymentFrequency.MONTHLY)
    description: str = Field(..., example="Monthly rent payment")
    start_date: datetime = Field(..., example=DATE_EXAMPLE)
    end_date: Optional[datetime] = Field(None, example=DATE_EXAMPLE)
    reference: Optional[str] = Field(None, example="RENT_2024")


class UpdateRecurringPaymentSchema(BaseSchema):
    amount: Optional[Decimal] = Field(None, example=60.00, gt=0)
    frequency: Optional[PaymentFrequency] = Field(
        None, example=PaymentFrequency.MONTHLY
    )
    description: Optional[str] = Field(None, example="Updated description")
    end_date: Optional[datetime] = Field(None, example=DATE_EXAMPLE)
    is_active: Optional[bool] = Field(None, example=True)


# =============== RESPONSE SCHEMAS ===============
class WalletResponseSchema(BaseSchema):
    wallet_id: UUID
    name: str
    wallet_type: str
    currency: CurrencySchema
    balance: Decimal
    available_balance: Decimal
    pending_balance: Decimal
    formatted_balance: str

    # Account Details (for receiving deposits - like PalmPay/Kuda)
    account_number: Optional[str] = Field(
        None, description="Account number for receiving deposits"
    )
    account_name: Optional[str] = Field(None, description="Account holder name")
    bank_name: Optional[str] = Field(None, description="Bank name")

    # Provider Information
    account_provider: str = Field(
        ..., description="Provider managing this account (internal, paystack, etc.)"
    )
    provider_account_id: Optional[str] = Field(
        None, description="External provider's account ID"
    )
    is_test_mode: bool = Field(
        ..., description="Whether this account is in test/sandbox mode"
    )

    daily_limit: Optional[Decimal]
    monthly_limit: Optional[Decimal]
    daily_spent: Decimal
    monthly_spent: Decimal
    status: str
    is_default: bool
    requires_pin: bool
    requires_biometric: bool
    description: Optional[str]
    last_transaction_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class BalanceResponseSchema(BaseSchema):
    wallet_id: UUID
    name: str
    currency: CurrencySchema
    balance: Decimal
    available_balance: Decimal
    pending_balance: Decimal
    formatted_balance: str
    daily_limit: Optional[Decimal]
    monthly_limit: Optional[Decimal]
    daily_spent: Decimal
    monthly_spent: Decimal
    status: str


class BasicWalletSchema(BaseSchema):
    currency: CurrencySchema
    wallet_id: UUID
    name: str
    user: UserDataSchema


class TransactionSchema(ModelSchema):
    from_wallet: BasicWalletSchema
    to_wallet: Optional[BasicWalletSchema]

    class Meta:
        model = Transaction
        exclude = [
            "id",
            "deleted_at",
            "from_balance_before",
            "from_balance_after",
            "to_balance_before",
            "to_balance_after",
            "ip_address",
            "user_agent",
            "device_id",
        ]


class TransferResponseSchema(BaseSchema):
    transfer_id: UUID
    from_wallet: dict
    to_wallet: dict
    amount: Decimal
    currency: str
    description: Optional[str]
    reference: Optional[str]
    timestamp: str


class SecurityResponseSchema(BaseSchema):
    wallet_id: UUID
    requires_pin: bool
    requires_biometric: bool
    has_pin_set: bool
    user_biometric_enabled: bool
    security_level: str


class AuthResponseSchema(BaseSchema):
    authorized: bool
    auth_methods: List[str]
    auth_token: str
    expires_at: str


class VirtualCardResponseSchema(BaseSchema):
    card_id: UUID
    wallet_id: UUID
    masked_number: str
    card_holder_name: str
    expiry_month: int
    expiry_year: int
    nickname: Optional[str]
    spending_limit: Optional[Decimal]
    total_spent: Decimal
    is_active: bool
    is_frozen: bool
    created_for_merchant: Optional[str]
    created_at: datetime


class QRCodeResponseSchema(BaseSchema):
    qr_id: UUID
    wallet_id: UUID
    qr_image_url: Optional[str]
    amount: Optional[Decimal]
    description: Optional[str]
    is_single_use: bool
    is_amount_fixed: bool
    expires_at: Optional[datetime]
    times_used: int
    total_received: Decimal
    is_active: bool
    created_at: datetime


class SplitPaymentResponseSchema(BaseSchema):
    payment_id: UUID
    total_amount: Decimal
    currency: str
    description: str
    split_type: str
    status: str
    participants: List[dict]
    created_by: str
    due_date: Optional[datetime]
    created_at: datetime


class RecurringPaymentResponseSchema(BaseSchema):
    payment_id: UUID
    from_wallet_id: UUID
    to_wallet_id: Optional[UUID]
    to_external: Optional[str]
    amount: Decimal
    frequency: str
    description: str
    next_payment_date: datetime
    start_date: datetime
    end_date: Optional[datetime]
    is_active: bool
    total_payments_made: int
    created_at: datetime


class WalletSummaryResponseSchema(BaseSchema):
    wallets: List[dict]
    total_balances: dict
    wallet_count: int


# =============== API RESPONSE WRAPPERS ===============
class CreateWalletResponseSchema(ResponseSchema):
    data: WalletResponseSchema


class WalletListResponseSchema(ResponseSchema):
    data: List[WalletResponseSchema]


class BalanceDataResponseSchema(ResponseSchema):
    data: BalanceResponseSchema


class TransferDataResponseSchema(ResponseSchema):
    data: TransactionSchema


class SecurityDataResponseSchema(ResponseSchema):
    data: SecurityResponseSchema


class AuthDataResponseSchema(ResponseSchema):
    data: AuthResponseSchema


class VirtualCardDataResponseSchema(ResponseSchema):
    data: VirtualCardResponseSchema


class VirtualCardListResponseSchema(ResponseSchema):
    data: List[VirtualCardResponseSchema]


class QRCodeDataResponseSchema(ResponseSchema):
    data: QRCodeResponseSchema


class QRCodeListResponseSchema(ResponseSchema):
    data: List[QRCodeResponseSchema]


class SplitPaymentDataResponseSchema(ResponseSchema):
    data: SplitPaymentResponseSchema


class SplitPaymentListResponseSchema(ResponseSchema):
    data: List[SplitPaymentResponseSchema]


class RecurringPaymentDataResponseSchema(ResponseSchema):
    data: RecurringPaymentResponseSchema


class RecurringPaymentListResponseSchema(ResponseSchema):
    data: List[RecurringPaymentResponseSchema]


class WalletSummaryDataResponseSchema(ResponseSchema):
    data: WalletSummaryResponseSchema


# =============== DEPOSIT WEBHOOK SCHEMAS ===============
class DepositWebhookSchema(BaseSchema):
    """Schema for processing deposit webhooks from payment providers"""

    account_number: str = Field(..., example="9012345678")
    amount: Decimal = Field(..., example=1000.00, gt=0)
    sender_account_number: str = Field(..., example="1234567890")
    sender_account_name: str = Field(..., example="Jane Smith")
    sender_bank_name: str = Field(..., example="GTBank")
    external_reference: str = Field(..., example="FLW-123456789")
    narration: Optional[str] = Field(None, example="Payment for services")
    transaction_date: Optional[datetime] = None
    webhook_payload: Optional[dict] = None


class DepositWebhookResponseSchema(BaseSchema):
    success: bool
    transaction_id: str
    external_reference: str
    amount_received: Decimal
    fee_charged: Decimal
    amount_credited: Decimal
    wallet_balance: Decimal
    account_number: str
    status: str


class DepositWebhookDataResponseSchema(ResponseSchema):
    data: DepositWebhookResponseSchema
