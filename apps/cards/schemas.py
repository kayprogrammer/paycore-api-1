from uuid import UUID
from decimal import Decimal
from typing import Optional, List
from datetime import datetime
from pydantic import Field

from apps.common.schemas import BaseSchema, ResponseSchema
from apps.common.doc_examples import UUID_EXAMPLE, DATE_EXAMPLE


# =============== BILLING ADDRESS SCHEMA ===============
class BillingAddressSchema(BaseSchema):
    street: str = Field(..., example="123 Main St", max_length=200)
    city: str = Field(..., example="New York", max_length=100)
    state: Optional[str] = Field(None, example="NY", max_length=100)
    country: str = Field(
        ..., example="US", max_length=2, description="ISO 3166-1 alpha-2 country code"
    )
    postal_code: str = Field(..., example="10001", max_length=20)


# =============== CARD MANAGEMENT SCHEMAS ===============
class CreateCardSchema(BaseSchema):
    wallet_id: UUID = Field(
        ..., example=UUID_EXAMPLE, description="Wallet to link card to"
    )
    card_type: str = Field(
        default="virtual",
        example="virtual",
        description="Card type (virtual or physical)",
    )
    card_brand: str = Field(
        default="visa",
        example="visa",
        description="Card brand (visa, mastercard, verve)",
    )
    currency_code: str = Field(..., example="USD", description="Card currency")
    nickname: Optional[str] = Field(None, example="Netflix Card", max_length=50)
    spending_limit: Optional[Decimal] = Field(None, example=500.00, ge=0)
    daily_limit: Optional[Decimal] = Field(None, example=1000.00, ge=0)
    monthly_limit: Optional[Decimal] = Field(None, example=5000.00, ge=0)
    created_for_merchant: Optional[str] = Field(None, example="Netflix", max_length=100)
    billing_address: Optional[BillingAddressSchema] = Field(
        None, description="Billing address for card"
    )


class UpdateCardSchema(BaseSchema):
    nickname: Optional[str] = Field(None, example="Updated Card Name")
    spending_limit: Optional[Decimal] = Field(None, example=1000.00, ge=0)
    daily_limit: Optional[Decimal] = Field(None, example=2000.00, ge=0)
    monthly_limit: Optional[Decimal] = Field(None, example=10000.00, ge=0)
    allow_online_transactions: Optional[bool] = Field(None, example=True)
    allow_atm_withdrawals: Optional[bool] = Field(None, example=True)
    allow_international_transactions: Optional[bool] = Field(None, example=False)
    billing_address: Optional[BillingAddressSchema] = Field(
        None, description="Updated billing address"
    )


class FundCardSchema(BaseSchema):
    amount: Decimal = Field(
        ..., example=100.00, gt=0, description="Amount to fund card with"
    )
    pin: Optional[int] = Field(None, example=1234, gt=999, lt=10000)
    description: Optional[str] = Field(None, example="Funding for Netflix subscription")


class CardControlsSchema(BaseSchema):
    allow_online_transactions: bool = Field(..., example=True)
    allow_atm_withdrawals: bool = Field(..., example=True)
    allow_international_transactions: bool = Field(..., example=False)


# =============== RESPONSE SCHEMAS ===============
class CardResponseSchema(BaseSchema):
    card_id: UUID
    wallet_id: UUID
    user_id: UUID
    card_type: str
    card_brand: str

    # Masked card details
    masked_number: str
    card_holder_name: str
    expiry_month: int
    expiry_year: int

    # Provider info
    card_provider: str
    is_test_mode: bool

    # Limits and controls
    spending_limit: Optional[Decimal]
    daily_limit: Optional[Decimal]
    monthly_limit: Optional[Decimal]

    # Status
    status: str
    is_frozen: bool
    is_expired: bool
    can_transact: bool

    # Usage tracking
    total_spent: Decimal
    daily_spent: Decimal
    monthly_spent: Decimal
    last_used_at: Optional[datetime]

    # Controls
    allow_online_transactions: bool
    allow_atm_withdrawals: bool
    allow_international_transactions: bool

    # Metadata
    nickname: Optional[str]
    created_for_merchant: Optional[str]
    billing_address: Optional[BillingAddressSchema]

    # Timestamps
    created_at: datetime
    updated_at: datetime


class CardDetailsResponseSchema(CardResponseSchema):
    """Full card details including sensitive info (CVV shown only on creation)"""

    card_number: str = Field(
        ..., description="Full card number (only shown on creation)"
    )
    cvv: str = Field(..., description="CVV (only shown on creation)")


class CardListItemSchema(BaseSchema):
    card_id: UUID
    masked_number: str
    card_brand: str
    card_type: str
    status: str
    is_frozen: bool
    nickname: Optional[str]
    total_spent: Decimal
    created_at: datetime


class CardTransactionSchema(BaseSchema):
    transaction_id: UUID
    transaction_type: str
    amount: Decimal
    currency: str = Field(
        ...,
        example="USD",
        description="Transaction currency",
        alias="from_wallet.currency.code",
    )
    merchant_name: Optional[str]
    merchant_category: Optional[str]
    description: Optional[str]
    status: str
    created_at: datetime


# =============== DATA RESPONSE SCHEMAS (for CustomResponse) ===============
class CreateCardDataResponseSchema(ResponseSchema):
    data: CardDetailsResponseSchema


class CardDataResponseSchema(ResponseSchema):
    data: CardResponseSchema


class CardListDataResponseSchema(ResponseSchema):
    data: List[CardListItemSchema]
    pagination: Optional[dict] = None


class CardTransactionListDataResponseSchema(ResponseSchema):
    data: List[CardTransactionSchema]
    pagination: Optional[dict] = None


class FundCardDataResponseSchema(ResponseSchema):
    data: dict = Field(
        ...,
        example={
            "card_id": UUID_EXAMPLE,
            "amount_funded": 100.00,
            "wallet_balance_before": 500.00,
            "wallet_balance_after": 400.00,
            "transaction_id": UUID_EXAMPLE,
        },
    )
