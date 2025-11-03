from ninja import ModelSchema
from pydantic import Field, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from apps.common.schemas import (
    BaseSchema,
    PaginatedResponseDataSchema,
    ResponseSchema,
    UserDataSchema,
)
from apps.investments.models import (
    Investment,
    InvestmentProduct,
    InvestmentReturn,
    InvestmentPortfolio,
    InvestmentStatus,
    InvestmentType,
    RiskLevel,
    InterestPayoutFrequency,
)
from apps.wallets.schemas import CurrencySchema


# ============================================================================
# Investment Product Schemas
# ============================================================================


class InvestmentProductSchema(ModelSchema):
    currency: CurrencySchema

    class Meta:
        model = InvestmentProduct
        exclude = ["id", "updated_at", "deleted_at"]


class InvestmentProductListSchema(BaseSchema):
    product_id: UUID
    name: str
    product_type: str
    min_amount: Decimal
    max_amount: Optional[Decimal]
    interest_rate: Decimal
    risk_level: str
    min_duration_days: int
    is_active: bool
    is_available: bool
    currency: CurrencySchema


class InvestmentProductDataResponseSchema(ResponseSchema):
    data: InvestmentProductSchema


class InvestmentProductListDataResponseSchema(ResponseSchema):
    data: List[InvestmentProductListSchema]


# ============================================================================
# Investment Schemas
# ============================================================================


class CreateInvestmentSchema(BaseSchema):
    product_id: UUID = Field(..., description="Investment product to invest in")
    wallet_id: UUID = Field(..., description="Wallet to debit for investment")
    amount: Decimal = Field(..., gt=0, description="Investment amount")
    duration_days: int = Field(..., gt=0, description="Investment duration in days")
    auto_renew: bool = Field(False, description="Auto-renew on maturity")


class InvestmentSchema(ModelSchema):
    currency: CurrencySchema = Field(
        ..., description="Investment currency", alias="wallet.currency"
    )

    class Meta:
        model = Investment
        exclude = ["id", "updated_at", "deleted_at"]


class InvestmentListSchema(BaseSchema):
    investment_id: UUID
    product_name: str = Field(..., alias="product.name")
    product_type: str = Field(..., alias="product.product_type")
    principal_amount: Decimal
    expected_returns: Decimal
    status: InvestmentStatus
    maturity_date: datetime
    days_to_maturity: int
    currency: CurrencySchema = Field(
        ..., description="Investment currency", alias="product.currency"
    )


class InvestmentDetailsSchema(BaseSchema):
    investment: InvestmentSchema
    returns_history: List["InvestmentReturnSchema"]
    total_returns_paid: Decimal
    next_payout_date: Optional[datetime]
    next_payout_amount: Decimal


class InvestmentDataResponseSchema(ResponseSchema):
    data: InvestmentSchema


class InvestmentListDataResponseSchema(PaginatedResponseDataSchema):
    data: List[InvestmentListSchema] = Field(..., alias="items")


class InvestmentListResponseSchema(ResponseSchema):
    data: InvestmentListDataResponseSchema


class InvestmentDetailsDataResponseSchema(ResponseSchema):
    data: InvestmentDetailsSchema


# ============================================================================
# Investment Action Schemas
# ============================================================================


class LiquidateInvestmentSchema(BaseSchema):
    reason: Optional[str] = Field(
        None, max_length=500, description="Reason for liquidation"
    )
    accept_penalty: bool = Field(..., description="Accept early liquidation penalty")


class RenewInvestmentSchema(BaseSchema):
    duration_days: Optional[int] = Field(
        None, gt=0, description="New duration (defaults to original)"
    )
    auto_renew: bool = Field(False, description="Auto-renew after this term")


# ============================================================================
# Investment Return Schemas
# ============================================================================


class InvestmentReturnSchema(ModelSchema):
    class Meta:
        model = InvestmentReturn
        exclude = [
            "id",
            "investment",
            "transaction",
            "created_at",
            "updated_at",
            "deleted_at",
        ]


class InvestmentReturnListSchema(ModelSchema):
    class Meta:
        model = InvestmentReturn
        fields = ["return_id", "amount", "payout_date", "actual_payout_date", "is_paid"]


class InvestmentReturnDataResponseSchema(ResponseSchema):
    data: InvestmentReturnSchema


# ============================================================================
# Portfolio Schemas
# ============================================================================


class InvestmentPortfolioSchema(ModelSchema):
    class Meta:
        model = InvestmentPortfolio
        exclude = ["id", "user", "created_at", "deleted_at"]


class InvestmentSummarySchema(BaseSchema):
    total_investments: int
    active_investments: int
    matured_investments: int

    total_invested: Decimal
    total_active_value: Decimal
    total_returns_earned: Decimal

    average_return_rate: Decimal

    investments_by_type: dict = Field(..., description="Breakdown by investment type")
    investments_by_risk: dict = Field(..., description="Breakdown by risk level")

    upcoming_maturities: List[InvestmentListSchema]


class InvestmentPortfolioDataResponseSchema(ResponseSchema):
    data: InvestmentPortfolioSchema


class InvestmentSummaryDataResponseSchema(ResponseSchema):
    data: InvestmentSummarySchema


# ============================================================================
# Calculation Schemas
# ============================================================================


class InvestmentCalculationSchema(BaseSchema):
    product_id: UUID
    amount: Decimal
    duration_days: int

    interest_rate: Decimal
    expected_returns: Decimal
    total_maturity_value: Decimal
    effective_annual_rate: Decimal

    payout_schedule: List[dict] = Field(..., description="Expected payout schedule")

    currency: CurrencySchema


class InvestmentCalculationDataResponseSchema(ResponseSchema):
    data: InvestmentCalculationSchema
