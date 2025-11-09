from ninja import ModelSchema
from pydantic import Field, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from apps.common.schemas import BaseSchema, PaginatedResponseDataSchema, ResponseSchema
from apps.payments.models import (
    Invoice,
    InvoiceStatus,
    MerchantAPIKey,
    Payment,
    PaymentLink,
    PaymentLinkStatus,
)
from apps.wallets.schemas import CurrencySchema


# ============================================================================
# Payment Link Schemas
# ============================================================================


class CreatePaymentLinkSchema(BaseSchema):
    wallet_id: UUID = Field(..., description="Wallet to receive payments")
    title: str = Field(
        ..., min_length=3, max_length=200, example="Freelance Invoice Payment"
    )
    description: Optional[str] = Field(
        None, max_length=1000, example="Payment for web design services"
    )

    amount: Optional[Decimal] = Field(None, ge=0, example=5000.00)
    is_amount_fixed: bool = Field(default=True, example=True)
    min_amount: Optional[Decimal] = Field(None, ge=0, example=100.00)
    max_amount: Optional[Decimal] = Field(None, ge=0, example=100000.00)

    is_single_use: bool = Field(default=False, example=False)
    expires_at: Optional[datetime] = Field(None, example="2025-12-31T23:59:59Z")
    redirect_url: Optional[str] = Field(
        None, max_length=500, example="https://yoursite.com/thank-you"
    )

    logo_url: Optional[str] = Field(None, max_length=500)
    brand_color: Optional[str] = Field(
        default="#3B82F6", pattern="^#[0-9A-Fa-f]{6}$", example="#3B82F6"
    )


class UpdatePaymentLinkSchema(BaseSchema):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[PaymentLinkStatus] = Field(None)
    redirect_url: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    brand_color: Optional[str] = Field(
        None, pattern="^#[0-9A-Fa-f]{6}$", example="#3B82F6"
    )


class PaymentLinkSchema(ModelSchema):
    currency: CurrencySchema = Field(..., alias="wallet.currency")

    class Meta:
        model = PaymentLink
        exclude = ["id", "deleted_at", "user", "wallet"]


class PaymentLinkDataResponseSchema(ResponseSchema):
    data: PaymentLinkSchema


class PaymentLinkListDataResponseSchema(PaginatedResponseDataSchema):
    links: List[PaymentLinkSchema] = Field(
        ..., description="List of payment links", alias="items"
    )


class PaymentLinksResponseSchema(ResponseSchema):
    data: PaymentLinkListDataResponseSchema


# ============================================================================
# Invoice Schemas
# ============================================================================


class InvoiceItemSchema(BaseSchema):
    description: str = Field(
        ..., min_length=1, max_length=500, example="Web Design Services"
    )
    quantity: Decimal = Field(..., gt=0, example=1)
    unit_price: Decimal = Field(..., ge=0, example=5000.00)


class CreateInvoiceSchema(BaseSchema):
    wallet_id: UUID = Field(..., description="Wallet to receive payment")

    customer_name: str = Field(..., min_length=1, max_length=200, example="John Doe")
    customer_email: str = Field(..., example="john@example.com")
    customer_phone: Optional[str] = Field(None, max_length=20, example="+2348012345678")
    customer_address: Optional[str] = Field(None, max_length=500)

    title: str = Field(..., min_length=1, max_length=200, example="Web Design Invoice")
    description: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(
        None, max_length=1000, example="Payment due within 30 days"
    )

    items: List[InvoiceItemSchema] = Field(..., min_length=1)

    tax_amount: Decimal = Field(default=Decimal("0"), ge=0, example=750.00)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0, example=0.00)

    issue_date: date = Field(..., example="2025-10-10")
    due_date: date = Field(..., example="2025-11-10")

    @field_validator("due_date")
    @classmethod
    def validate_dates(cls, value: date):
        # Note: Issue date validation happens at model level
        return value


class UpdateInvoiceSchema(BaseSchema):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(None, max_length=1000)
    status: Optional[InvoiceStatus] = Field(None)


class InvoiceItemResponseSchema(BaseSchema):
    item_id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


class InvoiceSchema(ModelSchema):
    items: List[InvoiceItemResponseSchema]
    currency: CurrencySchema = Field(..., alias="wallet.currency")
    merchant_name: str = Field(..., alias="user.full_name")

    class Meta:
        model = Invoice
        exclude = ["id", "updated_at", "deleted_at", "wallet", "user"]


class InvoiceDataResponseSchema(ResponseSchema):
    data: InvoiceSchema


class InvoiceListDataResponseSchema(PaginatedResponseDataSchema):
    data: List[InvoiceSchema] = Field(
        ..., description="List of invoices", alias="items"
    )


class InvoiceListResponseSchema(ResponseSchema):
    data: InvoiceListDataResponseSchema


# ============================================================================
# Payment Schemas
# ============================================================================


class MakePaymentSchema(BaseSchema):
    wallet_id: UUID = Field(..., description="Payer's wallet ID")
    amount: Optional[Decimal] = Field(
        None, gt=0, example=5000.00, description="Amount (required if not fixed)"
    )

    payer_name: Optional[str] = Field(None, max_length=200, example="Jane Doe")
    payer_email: Optional[str] = Field(None, example="jane@example.com")
    payer_phone: Optional[str] = Field(None, max_length=20)

    pin: Optional[str] = Field(None, description="Wallet PIN if required")


class PaymentSchema(ModelSchema):
    currency: CurrencySchema = Field(..., alias="payer_wallet.currency")
    merchant_name: str = Field(..., alias="merchant_user.full_name")
    invoice_number: Optional[str] = Field(
        None, max_length=200, example="INV-20251010-001", alias="invoice.invoice_number"
    )

    class Meta:
        model = Payment
        exclude = [
            "id",
            "merchant_user",
            "merchant_wallet",
            "transaction",
            "invoice",
            "updated_at",
            "deleted_at",
        ]


class PaymentDataResponseSchema(ResponseSchema):
    data: PaymentSchema


class PaymentListDataResponseSchema(PaginatedResponseDataSchema):
    data: List[PaymentSchema] = Field(
        ..., description="List of payments", alias="items"
    )


class PaymentListResponseSchema(ResponseSchema):
    data: PaymentListDataResponseSchema


# ============================================================================
# API Key Schemas
# ============================================================================


class CreateMerchantAPIKeySchema(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100, example="Production API Key")
    is_test_mode: bool = Field(default=False, example=False)

    can_create_links: bool = Field(default=True)
    can_create_invoices: bool = Field(default=True)
    can_view_payments: bool = Field(default=True)


class MerchantAPIKeySchema(ModelSchema):
    class Meta:
        model = MerchantAPIKey
        exclude = ["id", "updated_at", "deleted_at"]


class MerchantAPIKeyListSchema(ModelSchema):
    class Meta:
        model = MerchantAPIKey
        fields = [
            "key_id",
            "name",
            "prefix",
            "is_active",
            "is_test_mode",
            "requests_count",
            "last_used_at",
            "created_at",
        ]


class MerchantAPIKeyDataResponseSchema(ResponseSchema):
    data: MerchantAPIKeySchema


class MerchantAPIKeyListDataResponseSchema(ResponseSchema):
    data: List[MerchantAPIKeyListSchema]


# ============================================================================
# Analytics Schemas
# ============================================================================


class PaymentAnalyticsSchema(BaseSchema):
    total_links: int
    active_links: int
    total_invoices: int
    pending_invoices: int
    overdue_invoices: int

    total_payments: int
    total_collected: Decimal
    total_fees: Decimal
    net_collected: Decimal

    currency: CurrencySchema


class PaymentAnalyticsDataResponseSchema(ResponseSchema):
    data: PaymentAnalyticsSchema
