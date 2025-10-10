from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID

from ninja import Field

from apps.common.schemas import BaseSchema


# ============================================================================
# Bill Provider Schemas
# ============================================================================

class BillProviderSchema(BaseSchema):
    provider_id: UUID
    name: str
    slug: str
    category: str
    provider_code: str
    is_active: bool
    is_available: bool
    logo_url: Optional[str] = None
    description: Optional[str] = None
    supports_amount_range: bool
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    fee_type: str
    fee_amount: Decimal
    fee_cap: Optional[Decimal] = None


class BillPackageSchema(BaseSchema):
    package_id: UUID
    name: str
    code: str
    amount: Decimal
    description: Optional[str] = None
    validity_period: Optional[str] = None
    benefits: List[str] = Field(default_factory=list)
    is_popular: bool
    is_active: bool


class BillProviderDetailSchema(BillProviderSchema):
    """Detailed bill provider with packages"""
    packages: List[BillPackageSchema] = Field(default_factory=list)


# ============================================================================
# Bill Payment Request Schemas
# ============================================================================

class ValidateCustomerSchema(BaseSchema):
    provider_id: UUID = Field(..., description="Bill provider ID")
    customer_id: str = Field(..., min_length=1, max_length=200, description="Customer ID/Number")

class CreateBillPaymentSchema(BaseSchema):
    wallet_id: UUID = Field(..., description="Wallet to debit")
    provider_id: UUID = Field(..., description="Bill provider ID")
    customer_id: str = Field(..., min_length=1, max_length=200, description="Customer ID/Number")
    amount: Optional[Decimal] = Field(None, ge=0, description="Payment amount (required if no package)")
    package_id: Optional[UUID] = Field(None, description="Package ID (for predefined packages)")

    # Optional fields
    customer_email: Optional[str] = Field(None, max_length=200)
    customer_phone: Optional[str] = Field(None, max_length=20)
    save_beneficiary: bool = Field(default=False, description="Save as beneficiary")
    beneficiary_nickname: Optional[str] = Field(None, max_length=100, description="Nickname for beneficiary")
    pin: Optional[str] = Field(None, description="Transaction PIN")
    extra_data: Optional[Dict[str, Any]] = Field(...)


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


class BillPaymentSchema(BaseSchema):
    payment_id: UUID
    provider: BillProviderSchema
    package: Optional[BillPackageSchema] = None
    category: str
    amount: Decimal
    fee_amount: Decimal
    total_amount: Decimal
    customer_id: str
    customer_name: Optional[str] = None
    status: str
    token: Optional[str] = None
    token_units: Optional[str] = None
    provider_reference: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


class BillPaymentListSchema(BaseSchema):
    payments: List[BillPaymentSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


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
