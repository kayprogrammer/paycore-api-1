from ninja import Router
from typing import List
from uuid import UUID

from apps.bills.schemas import (
    BillProviderSchema,
    BillProviderDetailSchema,
    BillPackageSchema,
    ValidateCustomerSchema,
    CustomerValidationSchema,
    CreateBillPaymentSchema,
    BillPaymentSchema,
)
from apps.bills.services.bill_manager import BillManager
from apps.bills.models import BillProvider, BillPackage
from asgiref.sync import sync_to_async

bill_router = Router(tags=["Bill Payments"])


# ============================================================================
# Bill Providers & Packages
# ============================================================================


@bill_router.get("/providers", response=List[BillProviderSchema])
async def list_providers(request, category: str = None):
    """
    List available bill payment providers.

    Query Parameters:
    - category: Filter by category (airtime, data, electricity, cable_tv, etc.)

    Returns list of active bill providers.
    """
    providers = await BillManager.list_providers(category=category)

    return [
        BillProviderSchema(
            provider_id=p.provider_id,
            name=p.name,
            slug=p.slug,
            category=p.category,
            provider_code=p.provider_code,
            is_active=p.is_active,
            is_available=p.is_available,
            logo_url=p.logo_url,
            description=p.description,
            supports_amount_range=p.supports_amount_range,
            min_amount=p.min_amount,
            max_amount=p.max_amount,
            fee_type=p.fee_type,
            fee_amount=p.fee_amount,
            fee_cap=p.fee_cap,
        )
        for p in providers
    ]


@bill_router.get("/providers/{provider_id}", response=BillProviderDetailSchema)
async def get_provider_detail(request, provider_id: UUID):
    """
    Get bill provider details including packages.

    Returns provider information with available packages.
    """
    provider = await BillManager.get_provider(provider_id)
    packages = await BillManager.list_packages(provider_id)

    package_schemas = [
        BillPackageSchema(
            package_id=pkg.package_id,
            name=pkg.name,
            code=pkg.code,
            amount=pkg.amount,
            description=pkg.description,
            validity_period=pkg.validity_period,
            benefits=pkg.benefits,
            is_popular=pkg.is_popular,
            is_active=pkg.is_active,
        )
        for pkg in packages
    ]

    return BillProviderDetailSchema(
        provider_id=provider.provider_id,
        name=provider.name,
        slug=provider.slug,
        category=provider.category,
        provider_code=provider.provider_code,
        is_active=provider.is_active,
        is_available=provider.is_available,
        logo_url=provider.logo_url,
        description=provider.description,
        supports_amount_range=provider.supports_amount_range,
        min_amount=provider.min_amount,
        max_amount=provider.max_amount,
        fee_type=provider.fee_type,
        fee_amount=provider.fee_amount,
        fee_cap=provider.fee_cap,
        packages=package_schemas,
    )


@bill_router.get("/providers/{provider_id}/packages", response=List[BillPackageSchema])
async def list_provider_packages(request, provider_id: UUID):
    """
    List packages for a bill provider.

    Returns available packages (data bundles, cable TV plans, etc.).
    """
    packages = await BillManager.list_packages(provider_id)

    return [
        BillPackageSchema(
            package_id=pkg.package_id,
            name=pkg.name,
            code=pkg.code,
            amount=pkg.amount,
            description=pkg.description,
            validity_period=pkg.validity_period,
            benefits=pkg.benefits,
            is_popular=pkg.is_popular,
            is_active=pkg.is_active,
        )
        for pkg in packages
    ]


# ============================================================================
# Customer Validation
# ============================================================================


@bill_router.post("/validate-customer", response=CustomerValidationSchema)
async def validate_customer(request, data: ValidateCustomerSchema):
    """
    Validate customer details before payment.

    Request Body:
    - provider_id: Bill provider UUID
    - customer_id: Customer ID/number (meter number, smartcard, phone)

    Returns customer information if valid.
    Useful for confirming customer name before making payment.
    """
    validation_result = await BillManager.validate_customer(
        provider_id=data.provider_id,
        customer_id=data.customer_id,
    )

    return CustomerValidationSchema(**validation_result)


# ============================================================================
# Bill Payments
# ============================================================================


@bill_router.post("/pay", response={200: BillPaymentSchema})
async def create_bill_payment(request, data: CreateBillPaymentSchema):
    """
    Process bill payment.

    Request Body:
    - wallet_id: Wallet to debit
    - provider_id: Bill provider ID
    - customer_id: Customer ID/number
    - amount: Payment amount (optional if using package)
    - package_id: Package ID for predefined packages (optional)
    - customer_email: Customer email (optional)
    - customer_phone: Customer phone (optional)
    - save_beneficiary: Save as beneficiary for future payments
    - beneficiary_nickname: Nickname for saved beneficiary
    - pin: Transaction PIN (if required)

    Process:
    1. Validates customer (if supported by provider)
    2. Debits wallet
    3. Processes payment with provider
    4. Returns transaction details including token (for electricity, etc.)

    **Fees:**
    - Provider fee (varies by service type)
    - Platform fee (if applicable)
    """
    # Get user from request (auth is handled at router level)
    user = request.auth

    payment = await BillManager.create_bill_payment(
        user=user,
        wallet_id=data.wallet_id,
        provider_id=data.provider_id,
        customer_id=data.customer_id,
        amount=data.amount,
        package_id=data.package_id,
        customer_email=data.customer_email,
        customer_phone=data.customer_phone,
        save_beneficiary=data.save_beneficiary,
        beneficiary_nickname=data.beneficiary_nickname,
        extra_data=data.extra_data,
    )

    # Reload with relationships
    payment = await BillManager.get_payment_by_id(user, payment.payment_id)

    return await _payment_to_schema(payment)


@bill_router.get("/payments", response=List[BillPaymentSchema])
async def list_bill_payments(
    request,
    category: str = None,
    status: str = None,
    limit: int = 20,
    offset: int = 0,
):
    """
    List user's bill payments.

    Query Parameters:
    - category: Filter by category (airtime, data, electricity, etc.)
    - status: Filter by status (pending, completed, failed)
    - limit: Number of results (default: 20, max: 100)
    - offset: Pagination offset

    Returns paginated list of bill payments.
    """
    user = request.auth

    if limit > 100:
        limit = 100

    payments = await BillManager.get_user_payments(
        user=user,
        category=category,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [await _payment_to_schema(p) for p in payments]


@bill_router.get("/payments/{payment_id}", response=BillPaymentSchema)
async def get_bill_payment(request, payment_id: UUID):
    """
    Get bill payment details.

    Returns detailed information about a specific bill payment including:
    - Payment status
    - Token/PIN (for electricity, etc.)
    - Provider response
    - Transaction details
    """
    user = request.auth
    payment = await BillManager.get_payment_by_id(user, payment_id)
    return await _payment_to_schema(payment)


# ============================================================================
# Helper Functions
# ============================================================================


async def _payment_to_schema(payment) -> BillPaymentSchema:
    """Convert BillPayment model to schema"""
    # Get provider
    provider = await sync_to_async(lambda: payment.provider)()

    # Get package if exists
    package = None
    if payment.package_id:
        pkg = await sync_to_async(lambda: payment.package)()
        package = BillPackageSchema(
            package_id=pkg.package_id,
            name=pkg.name,
            code=pkg.code,
            amount=pkg.amount,
            description=pkg.description,
            validity_period=pkg.validity_period,
            benefits=pkg.benefits,
            is_popular=pkg.is_popular,
            is_active=pkg.is_active,
        )

    return BillPaymentSchema(
        payment_id=payment.payment_id,
        provider=BillProviderSchema(
            provider_id=provider.provider_id,
            name=provider.name,
            slug=provider.slug,
            category=provider.category,
            provider_code=provider.provider_code,
            is_active=provider.is_active,
            is_available=provider.is_available,
            logo_url=provider.logo_url,
            description=provider.description,
            supports_amount_range=provider.supports_amount_range,
            min_amount=provider.min_amount,
            max_amount=provider.max_amount,
            fee_type=provider.fee_type,
            fee_amount=provider.fee_amount,
            fee_cap=provider.fee_cap,
        ),
        package=package,
        category=payment.category,
        amount=payment.amount,
        fee_amount=payment.fee_amount,
        total_amount=payment.total_amount,
        customer_id=payment.customer_id,
        customer_name=payment.customer_name,
        status=payment.status,
        token=payment.token,
        token_units=payment.token_units,
        provider_reference=payment.provider_reference,
        description=payment.description,
        created_at=payment.created_at,
        completed_at=payment.completed_at,
        failed_at=payment.failed_at,
        failure_reason=payment.failure_reason,
    )
