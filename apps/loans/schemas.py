from ninja import ModelSchema
from pydantic import Field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from apps.common.schemas import (
    BaseSchema,
    PaginatedResponseDataSchema,
    ResponseSchema,
    UserDataSchema,
)
from apps.loans.models import (
    CollateralType,
    CreditScore,
    LoanApplication,
    LoanProduct,
    LoanProductType,
    LoanRepayment,
    LoanRepaymentSchedule,
    RepaymentFrequency,
    RepaymentStatus,
)
from apps.wallets.schemas import CurrencySchema


# ============================================================================
# Loan Product Schemas
# ============================================================================


class LoanProductSchema(ModelSchema):
    currency: CurrencySchema

    class Meta:
        model = LoanProduct
        exclude = [
            "id",
            "updated_at",
            "deleted_at",
        ]


class LoanProductListSchema(ModelSchema):
    currency: CurrencySchema

    class Meta:
        model = LoanProduct
        fields = [
            "product_id",
            "name",
            "product_type",
            "min_amount",
            "max_amount",
            "min_interest_rate",
            "max_interest_rate",
            "min_tenure_months",
            "max_tenure_months",
            "is_active",
        ]


class LoanProductDataResponseSchema(ResponseSchema):
    data: LoanProductSchema


class LoanProductListDataResponseSchema(ResponseSchema):
    data: List[LoanProductListSchema]


# ============================================================================
# Loan Application Schemas
# ============================================================================


class CreateLoanApplicationSchema(BaseSchema):
    loan_product_id: UUID = Field(..., description="Loan product to apply for")
    wallet_id: UUID = Field(..., description="Wallet to receive loan disbursement")

    requested_amount: Decimal = Field(..., gt=0, description="Requested loan amount")
    tenure_months: int = Field(..., gt=0, le=360, description="Loan duration in months")
    repayment_frequency: RepaymentFrequency = Field(
        ...,
        description="Repayment frequency: daily, weekly, biweekly, monthly, quarterly",
    )

    purpose: str = Field(..., min_length=5, max_length=200, description="Loan purpose")
    purpose_details: Optional[str] = Field(
        None, max_length=1000, description="Detailed explanation"
    )

    employment_status: Optional[str] = Field(
        None, max_length=50, description="Employment status"
    )
    employer_name: Optional[str] = Field(
        None, max_length=200, description="Employer name"
    )
    monthly_income: Optional[Decimal] = Field(None, ge=0, description="Monthly income")

    collateral_type: Optional[CollateralType] = Field(
        None,
        description="Collateral type: property, vehicle, savings, investment, other",
    )
    collateral_value: Optional[Decimal] = Field(
        None, ge=0, description="Estimated collateral value"
    )
    collateral_description: Optional[str] = Field(
        None, max_length=500, description="Collateral details"
    )

    guarantor_name: Optional[str] = Field(
        None, max_length=200, description="Guarantor full name"
    )
    guarantor_phone: Optional[str] = Field(
        None, max_length=20, description="Guarantor phone number"
    )
    guarantor_email: Optional[str] = Field(None, description="Guarantor email")
    guarantor_relationship: Optional[str] = Field(
        None, max_length=100, description="Relationship to guarantor"
    )


class LoanApplicationSchema(ModelSchema):
    user: UserDataSchema
    currency: CurrencySchema = Field(
        ..., description="Currency of the loan", alias="loan_product.currency"
    )

    class Meta:
        model = LoanApplication
        exclude = ["id", "deleted_at", "wallet"]


class LoanApplicationListSchema(ModelSchema):
    currency: CurrencySchema = Field(
        ..., description="Currency of the loan", alias="loan_product.currency"
    )

    class Meta:
        model = LoanApplication
        fields = [
            "application_id",
            "loan_product_name",
            "loan_product_type",
            "requested_amount",
            "approved_amount",
            "tenure_months",
            "status",
            "credit_score",
            "created_at",
        ]


class LoanCalculationSchema(BaseSchema):
    requested_amount: Decimal
    approved_amount: Decimal
    interest_rate: Decimal
    tenure_months: int
    repayment_frequency: str

    processing_fee: Decimal
    total_interest: Decimal
    total_repayable: Decimal
    monthly_repayment: Decimal
    installment_amount: Decimal
    number_of_installments: int

    currency: CurrencySchema = Field(..., description="Currency of the loan")


class LoanApplicationDataResponseSchema(ResponseSchema):
    data: LoanApplicationSchema


class LoanApplicationPaginatedResponseSchema(PaginatedResponseDataSchema):
    applications: List[LoanApplicationListSchema] = Field(..., alias="items")


class LoanApplicationListDataResponseSchema(ResponseSchema):
    data: LoanApplicationPaginatedResponseSchema


class LoanCalculationDataResponseSchema(ResponseSchema):
    data: LoanCalculationSchema


# ============================================================================
# Loan Action Schemas
# ============================================================================


class ApproveLoanSchema(BaseSchema):
    approved_amount: Optional[Decimal] = Field(
        None, gt=0, description="Approved amount (defaults to requested amount)"
    )
    interest_rate: Optional[Decimal] = Field(
        None, gt=0, le=100, description="Interest rate (overrides default)"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Approval notes")


class RejectLoanSchema(BaseSchema):
    rejection_reason: str = Field(
        ..., min_length=10, max_length=500, description="Reason for rejection"
    )


class DisburseLoanSchema(BaseSchema):
    pin: Optional[str] = Field(
        None, description="Admin PIN for verification (if required)"
    )


# ============================================================================
# Repayment Schedule Schemas
# ============================================================================


class RepaymentScheduleSchema(ModelSchema):
    class Meta:
        model = LoanRepaymentSchedule
        exclude = ["id", "loan", "created_at", "updated_at", "deleted_at"]


class RepaymentScheduleListDataResponseSchema(PaginatedResponseDataSchema):
    data: List[RepaymentScheduleSchema] = Field(..., alias="items")


class RepaymentScheduleListResponseSchema(ResponseSchema):
    data: RepaymentScheduleListDataResponseSchema


# ============================================================================
# Loan Repayment Schemas
# ============================================================================


class MakeLoanRepaymentSchema(BaseSchema):
    wallet_id: UUID = Field(..., description="Wallet to debit for repayment")
    amount: Decimal = Field(..., gt=0, description="Repayment amount")
    schedule_id: Optional[UUID] = Field(
        None, description="Specific schedule to pay (optional)"
    )
    pin: Optional[str] = Field(None, description="Wallet PIN if required")
    notes: Optional[str] = Field(None, max_length=200, description="Payment notes")


class LoanRepaymentSchema(ModelSchema):

    class Meta:
        model = LoanRepayment
        exclude = [
            "id",
            "loan",
            "schedule",
            "transaction",
            "wallet",
            "created_at",
            "deleted_at",
        ]


class LoanRepaymentListSchema(ModelSchema):

    class Meta:
        model = LoanRepayment
        fields = [
            "repayment_id",
            "amount",
            "principal_paid",
            "interest_paid",
            "reference",
            "status",
            "created_at",
        ]


class LoanRepaymentDataResponseSchema(ResponseSchema):
    data: LoanRepaymentSchema


class LoanRepaymentListDataResponseSchema(PaginatedResponseDataSchema):
    data: List[LoanRepaymentListSchema] = Field(..., alias="items")


class LoanRepaymentListResponseSchema(ResponseSchema):
    data: LoanRepaymentListDataResponseSchema


# ============================================================================
# Credit Score Schemas
# ============================================================================


class CreditScoreSchema(ModelSchema):

    class Meta:
        model = CreditScore
        exclude = ["id", "user", "created_at", "deleted_at"]


class CreditScoreDataResponseSchema(ResponseSchema):
    data: CreditScoreSchema


# ============================================================================
# Loan Summary & Analytics Schemas
# ============================================================================


class LoanSummarySchema(BaseSchema):
    total_loans: int
    active_loans: int
    completed_loans: int
    rejected_loans: int

    total_borrowed: Decimal
    total_repaid: Decimal
    outstanding_balance: Decimal

    upcoming_payment_amount: Decimal
    upcoming_payment_date: Optional[date]

    overdue_amount: Decimal
    overdue_count: int

    credit_score: Optional[int]
    credit_score_band: Optional[str]

    currency: CurrencySchema = Field(
        ..., description="Currency of the loan", alias="loan_product.currency"
    )


class LoanSummaryDataResponseSchema(ResponseSchema):
    data: LoanSummarySchema


class LoanDetailsSchema(BaseSchema):
    application: LoanApplicationSchema
    repayment_schedule: List[RepaymentScheduleSchema]
    repayments: List[LoanRepaymentListSchema]

    total_paid: Decimal
    remaining_balance: Decimal
    next_due_date: Optional[date]
    next_due_amount: Decimal


class LoanDetailsDataResponseSchema(ResponseSchema):
    data: LoanDetailsSchema
