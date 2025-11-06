from uuid import UUID
from decimal import Decimal
from typing import Optional, List
from datetime import datetime
from ninja import ModelSchema
from pydantic import Field

from apps.cards.models import Card, CardBrand, CardStatus, CardType
from apps.common.schemas import BaseSchema, PaginatedResponseDataSchema, ResponseSchema
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
    card_type: CardType = Field(
        default=CardType.VIRTUAL,
        example=CardType.VIRTUAL,
        description="Card type (virtual or physical)",
    )
    card_brand: CardBrand = Field(
        default=CardBrand.VISA,
        example=CardBrand.VISA,
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
    allow_online_transactions: Optional[bool] = Field(None, example=True)
    allow_atm_withdrawals: Optional[bool] = Field(None, example=True)
    allow_international_transactions: Optional[bool] = Field(None, example=False)


# =============== RESPONSE SCHEMAS ===============
class CardResponseSchema(ModelSchema):
    class Meta:
        model = Card
        exclude = ["user", "wallet", "id", "deleted_at", "cvv"]


class CardDetailsResponseSchema(CardResponseSchema):
    """Full card details including sensitive info (CVV shown only on creation)"""

    card_number: str = Field(
        ..., description="Full card number (only shown on creation)"
    )
    cvv: str = Field(..., description="CVV (only shown on creation)")


class CardListItemSchema(ModelSchema):
    class Meta:
        model = Card
        fields = [
            "card_id",
            "card_brand",
            "card_type",
            "card_number",
            "card_holder_name",
            "expiry_month",
            "expiry_year",
            "cvv",
            "status",
            "is_frozen",
            "nickname",
            "total_spent",
            "allow_online_transactions",
            "allow_atm_withdrawals",
            "allow_international_transactions",
            "created_at",
        ]

    # Additional computed fields from properties and relations
    masked_number: str = Field(default="****", description="Masked card number")
    balance: float = Field(default=0.0, description="Card balance")
    currency: str = Field(default="USD", description="Card currency code")

    @staticmethod
    def resolve_masked_number(obj):
        """Get masked number from card property"""
        return obj.masked_number

    @staticmethod
    def resolve_balance(obj):
        """Get balance from associated wallet"""
        return float(obj.wallet.available_balance) if obj.wallet else 0.0

    @staticmethod
    def resolve_currency(obj):
        """Get currency from associated wallet"""
        return obj.wallet.currency.code if obj.wallet and obj.wallet.currency else "USD"


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


class CardTransactionListDataResponseSchema(PaginatedResponseDataSchema):
    transactions: List[CardTransactionSchema] = Field(..., alias="items")


class CardTransactionListResponseSchema(ResponseSchema):
    data: CardTransactionListDataResponseSchema


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
