from ninja import Query, Router
from uuid import UUID

from apps.bills.models import BillCategory, BillPaymentStatus
from apps.bills.schemas import (
    BillPackageListResponseSchema,
    BillPaymentListResponseSchema,
    BillPaymentResponseSchema,
    BillProviderListResponseSchema,
    BillProviderDetailResponseSchema,
    CustomerValidationResponseSchema,
    ValidateCustomerSchema,
    CreateBillPaymentSchema,
)
from apps.bills.services.bill_manager import BillManager

from apps.common.responses import CustomResponse
from apps.common.schemas import PaginationQuerySchema
from apps.common.cache import cacheable, invalidate_cache

bill_router = Router(tags=["Bill Payments (7)"])


# ============================================================================
# Bill Providers & Packages
# ============================================================================


@bill_router.get(
    "/providers",
    description="""
        List available bill payment providers.
        Query Parameters:
        - category: Filter by category (airtime, data, electricity, cable_tv, etc.)
        Returns list of active bill providers.
    """,
    response=BillProviderListResponseSchema,
)
@cacheable(key="bills:providers:list", ttl=300)
async def list_providers(request, category: str = None):
    providers = await BillManager.list_providers(category=category)
    print(providers)
    return CustomResponse.success(
        "Bill Providers returned successfully", data=providers
    )


@bill_router.get(
    "/providers/{provider_id}",
    description="""
        Get bill provider details including packages.
        Returns provider information with available packages.
    """,
    response=BillProviderDetailResponseSchema,
)
@cacheable(key="bills:providers:{{provider_id}}", ttl=300)
async def get_provider_detail(request, provider_id: UUID):
    provider = await BillManager.get_provider(provider_id)
    return CustomResponse.success("Bill Provider returned successfully", data=provider)


@bill_router.get(
    "/providers/{provider_id}/packages",
    description="""
        List packages for a bill provider.

        Returns available packages (data bundles, cable TV plans, etc.).
    """,
    response=BillPackageListResponseSchema,
)
@cacheable(key="bills:providers:{{provider_id}}:packages", ttl=300)
async def list_provider_packages(request, provider_id: UUID):
    provider = await BillManager.get_provider(provider_id)
    packages = provider.packages.all()
    return CustomResponse.success("Bill Packages returned successfully", data=packages)


# ============================================================================
# Customer Validation
# ============================================================================


@bill_router.post(
    "/validate-customer",
    description="""
        Validate customer details before payment.

        Request Body:
        - provider_id: Bill provider UUID
        - customer_id: Customer ID/number (meter number, smartcard, phone)

        Returns customer information if valid.
        Useful for confirming customer name before making payment.
    """,
    response=CustomerValidationResponseSchema,
)
async def validate_customer(request, data: ValidateCustomerSchema):
    validation_result = await BillManager.validate_customer(
        provider_id=data.provider_id,
        customer_id=data.customer_id,
    )
    return CustomResponse.success(
        "Customer validation successful", data=validation_result
    )


# ============================================================================
# Bill Payments
# ============================================================================


@bill_router.post(
    "/pay",
    description="""
        Process bill payment.

        Request Body:
        - wallet_id: Wallet to debit
        - provider_id: Bill provider ID
        - customer_id: Customer ID/number
        - amount: Payment amount (optional if using package)
        - package_id: Package ID for predefined packages (optional)
    """,
    response={201: BillPaymentResponseSchema},
)
@invalidate_cache(
    patterns=[
        "bills:payments:{{user_id}}:*",
        "wallets:detail:*",
        "wallets:list:{{user_id}}:*",
    ]
)
async def create_bill_payment(request, data: CreateBillPaymentSchema):
    user = request.auth
    payment = await BillManager.create_bill_payment(user=user, **data.model_dump())
    return CustomResponse.success(
        "Bill payment created successfully", data=payment, status_code=201
    )


@bill_router.get(
    "/payments",
    description="""
        List user's bill payments.
        Returns paginated list of bill payments.
    """,
    response=BillPaymentListResponseSchema,
)
@cacheable(key="bills:payments:{{user_id}}", ttl=30)
async def list_bill_payments(
    request,
    category: BillCategory = None,
    status: BillPaymentStatus = None,
    page_params: PaginationQuerySchema = Query(...),
):
    user = request.auth
    payments_data = await BillManager.get_user_payments(
        user=user, category=category, status=status, page_params=page_params
    )
    return CustomResponse.success(
        "Bill Payments returned successfully", data=payments_data
    )


@bill_router.get(
    "/payments/{payment_id}",
    description="""
        Get bill payment details.

        Returns detailed information about a specific bill payment including:
        - Payment status
        - Token/PIN (for electricity, etc.)
        - Provider response
        - Transaction details
    """,
    response=BillPaymentResponseSchema,
)
@cacheable(key="bills:payments:{{payment_id}}:{{user_id}}", ttl=60)
async def get_bill_payment(request, payment_id: UUID):
    user = request.auth
    payment = await BillManager.get_payment_by_id(user, payment_id)
    return CustomResponse.success("Bill Payment returned successfully", data=payment)
