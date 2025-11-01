from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID

from ninja import Field, ModelSchema

from apps.bills.models import BillPackage, BillPayment, BillProvider
from apps.common.schemas import BaseSchema, PaginatedResponseDataSchema, ResponseSchema


# ============================================================================
# Bill Provider Schemas
# ============================================================================


class BillProviderSchema(ModelSchema):
    class Meta:
        model = BillProvider
        exclude = [
            "id",
            "deleted_at",
            "requires_customer_validation",
            "validation_fields",
            "extra_fields",
        ]


class BillPackageSchema(ModelSchema):
    class Meta:
        model = BillPackage
        exclude = ["id", "deleted_at", "display_order"]


class BillProviderDetailSchema(BillProviderSchema):
    packages: List[BillPackageSchema]


class BillProviderListResponseSchema(ResponseSchema):
    data: List[BillProviderSchema]


class BillProviderDetailResponseSchema(ResponseSchema):
    data: BillProviderDetailSchema


class BillPackageListResponseSchema(ResponseSchema):
    data: List[BillPackageSchema]


# ============================================================================
# Bill Payment Request Schemas
# ============================================================================


class ValidateCustomerSchema(BaseSchema):
    provider_id: UUID = Field(..., description="Bill provider ID")
    customer_id: str = Field(
        ..., min_length=1, max_length=200, description="Customer ID/Number"
    )


class CreateBillPaymentSchema(BaseSchema):
    wallet_id: UUID = Field(..., description="Wallet to debit")
    provider_id: UUID = Field(..., description="Bill provider ID")
    customer_id: str = Field(
        ..., min_length=1, max_length=200, description="Customer ID/Number"
    )
    amount: Optional[Decimal] = Field(
        None, ge=0, description="Payment amount (required if no package)"
    )
    package_id: Optional[UUID] = Field(
        None, description="Package ID (for predefined packages)"
    )

    # Optional fields
    customer_email: Optional[str] = Field(None, max_length=200)
    customer_phone: Optional[str] = Field(None, max_length=20)
    save_beneficiary: bool = Field(default=False, description="Save as beneficiary")
    beneficiary_nickname: Optional[str] = Field(
        None, max_length=100, description="Nickname for beneficiary"
    )
    pin: Optional[str] = Field(None, description="Transaction PIN")
    extra_data: Optional[Dict[str, Any]] = Field(None)


class ReprocessBillPaymentSchema(BaseSchema):
    payment_id: UUID = Field(..., description="Bill payment ID")


# ============================================================================
# Bill Payment Response Schemas
# ============================================================================


class CustomerValidationSchema(BaseSchema):
    is_valid: bool
    customer_name: Optional[str] = None
    customer_id: str
    customer_type: Optional[str] = None
    address: Optional[str] = None
    balance: Optional[str] = None
    extra_info: Dict[str, Any] = Field(default_factory=dict)


class CustomerValidationResponseSchema(ResponseSchema):
    data: CustomerValidationSchema


class BillPaymentSchema(ModelSchema):
    provider: BillProviderSchema
    package: Optional[BillPackageSchema] = None

    class Meta:
        model = BillPayment
        exclude = [
            "id",
            "deleted_at",
            "save_beneficiary",
            "extra_data",
            "wallet",
            "user",
        ]


class BillPaymentListPaginatedDataSchema(PaginatedResponseDataSchema):
    payments: List[BillPaymentSchema] = Field(alias="items")


class BillPaymentListResponseSchema(ResponseSchema):
    data: BillPaymentListPaginatedDataSchema


class BillPaymentResponseSchema(ResponseSchema):
    data: BillPaymentSchema


# ============================================================================
# Bill Beneficiary Schemas
# ============================================================================


class CreateBeneficiarySchema(BaseSchema):
    provider_id: UUID = Field(..., description="Bill provider ID")
    customer_id: str = Field(..., min_length=1, max_length=200)
    nickname: str = Field(..., min_length=1, max_length=100)
    customer_name: Optional[str] = Field(None, max_length=200)
    extra_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateBeneficiarySchema(BaseSchema):
    nickname: Optional[str] = Field(None, min_length=1, max_length=100)


class BillBeneficiarySchema(BaseSchema):
    beneficiary_id: UUID
    provider: BillProviderSchema
    nickname: str
    customer_id: str
    customer_name: Optional[str] = None
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime


# ============================================================================
# Bill Schedule Schemas
# ============================================================================


class CreateBillScheduleSchema(BaseSchema):
    wallet_id: UUID = Field(..., description="Wallet to debit")
    provider_id: UUID = Field(..., description="Bill provider ID")
    customer_id: str = Field(..., min_length=1, max_length=200)
    amount: Decimal = Field(..., ge=0)
    frequency: str = Field(..., pattern="^(daily|weekly|monthly|quarterly)$")
    next_payment_date: date = Field(..., description="First payment date")
    description: Optional[str] = Field(None, max_length=500)
    pin: Optional[str] = Field(None, description="Transaction PIN")


class UpdateBillScheduleSchema(BaseSchema):
    amount: Optional[Decimal] = Field(None, ge=0)
    frequency: Optional[str] = Field(None, pattern="^(daily|weekly|monthly|quarterly)$")
    next_payment_date: Optional[date] = None
    is_paused: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=500)


class BillScheduleSchema(BaseSchema):
    schedule_id: UUID
    provider: BillProviderSchema
    customer_id: str
    amount: Decimal
    frequency: str
    next_payment_date: date
    is_active: bool
    is_paused: bool
    total_payments: int
    successful_payments: int
    failed_payments: int
    last_payment_date: Optional[date] = None
    description: Optional[str] = None
    created_at: datetime


# ============================================================================
# Analytics Schemas
# ============================================================================


class BillPaymentStatsSchema(BaseSchema):
    total_payments: int
    successful_payments: int
    failed_payments: int
    total_amount_spent: Decimal
    total_fees_paid: Decimal
    most_used_category: Optional[str] = None
    most_used_provider: Optional[str] = None
    category_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


# ============================================================================
# Filter Schemas
# ============================================================================


class BillPaymentFilterSchema(BaseSchema):
    category: Optional[str] = None
    provider_id: Optional[UUID] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
