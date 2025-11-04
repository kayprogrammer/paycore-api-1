from decimal import Decimal
from ninja import Router, Query
from typing import Optional
from uuid import UUID

from apps.common.responses import CustomResponse
from apps.common.schemas import PaginationQuerySchema
from apps.investments.schemas import (
    CreateInvestmentSchema,
    InvestmentDataResponseSchema,
    InvestmentDetailsDataResponseSchema,
    InvestmentListResponseSchema,
    InvestmentProductDataResponseSchema,
    InvestmentProductListDataResponseSchema,
    LiquidateInvestmentSchema,
    RenewInvestmentSchema,
    InvestmentSummaryDataResponseSchema,
    InvestmentPortfolioDataResponseSchema,
    InvestmentCalculationDataResponseSchema,
)
from apps.investments.services.investment_manager import InvestmentManager
from apps.investments.services.investment_processor import InvestmentProcessor
from apps.investments.models import (
    InvestmentProduct,
    InvestmentStatus,
    InvestmentType,
    RiskLevel,
)
from asgiref.sync import sync_to_async

investment_router = Router(tags=["Investments (10)"])


# ==================== INVESTMENT PRODUCTS ====================


@investment_router.get(
    "/products/list",
    summary="List investment products",
    response={200: InvestmentProductListDataResponseSchema},
)
async def list_investment_products(
    request,
    product_type: Optional[InvestmentType] = None,
    risk_level: Optional[RiskLevel] = None,
    currency_code: Optional[str] = None,
):
    queryset = InvestmentProduct.objects.filter(is_active=True).select_related(
        "currency"
    )
    if product_type:
        queryset = queryset.filter(product_type=product_type)
    if risk_level:
        queryset = queryset.filter(risk_level=risk_level)
    if currency_code:
        queryset = queryset.filter(currency__code=currency_code)
    products = await sync_to_async(list)(queryset.order_by("product_type", "name"))
    return CustomResponse.success(
        "Investment products retrieved successfully", products
    )


@investment_router.get(
    "/products/{product_id}",
    summary="Get investment product details",
    response={200: InvestmentProductDataResponseSchema},
)
async def get_investment_product(request, product_id: UUID):
    """Get detailed information about an investment product"""
    product = await InvestmentManager.get_investment_product(product_id)
    return CustomResponse.success("Investment product retrieved successfully", product)


# ==================== INVESTMENT CALCULATIONS ====================


@investment_router.get(
    "/calculate",
    summary="Calculate investment returns",
    response={200: InvestmentCalculationDataResponseSchema},
)
async def calculate_investment(
    request,
    product_id: UUID,
    amount: float,
    duration_days: int,
):
    calculation = await InvestmentManager.calculate_investment(
        product_id, Decimal(str(amount)), duration_days
    )

    return CustomResponse.success("Investment calculated successfully", calculation)


# ==================== USER INVESTMENTS ====================


@investment_router.post(
    "/create",
    summary="Create new investment",
    response={201: InvestmentDataResponseSchema},
)
async def create_investment(request, data: CreateInvestmentSchema):
    user = request.auth
    investment = await InvestmentManager.create_investment(user, data)
    return CustomResponse.success("Investment created successfully", investment, 201)


@investment_router.get(
    "/list",
    summary="List my investments",
    response={200: InvestmentListResponseSchema},
)
async def list_investments(
    request,
    status: Optional[InvestmentStatus] = None,
    page_params: PaginationQuerySchema = Query(...),
):
    user = request.auth
    paginated_investments_data = await InvestmentManager.list_investments(
        user, status, page_params
    )
    return CustomResponse.success(
        "Investments retrieved successfully", paginated_investments_data
    )


@investment_router.get(
    "/investment/{investment_id}",
    summary="Get investment details",
    response={200: InvestmentDetailsDataResponseSchema},
)
async def get_investment_details(request, investment_id: UUID):
    user = request.auth
    details = await InvestmentProcessor.get_investment_details(user, investment_id)
    return CustomResponse.success("Investment details retrieved successfully", details)


# ==================== INVESTMENT ACTIONS ====================


@investment_router.post(
    "/investment/{investment_id}/liquidate",
    summary="Liquidate investment (early exit)",
    response={200: InvestmentDataResponseSchema},
)
async def liquidate_investment(
    request, investment_id: UUID, data: LiquidateInvestmentSchema
):
    user = request.auth
    investment = await InvestmentManager.liquidate_investment(user, investment_id)
    return CustomResponse.success("Investment liquidated successfully", investment)


@investment_router.post(
    "/investment/{investment_id}/renew",
    summary="Renew matured investment",
    response={201: InvestmentDataResponseSchema},
)
async def renew_investment(request, investment_id: UUID, data: RenewInvestmentSchema):
    user = request.auth
    investment = await InvestmentManager.renew_investment(user, investment_id, data)
    return CustomResponse.success("Investment renewed successfully", investment, 201)


# ==================== PORTFOLIO & SUMMARY ====================


@investment_router.get(
    "/portfolio/summary",
    summary="Get investment portfolio summary",
    response={200: InvestmentSummaryDataResponseSchema},
)
async def get_portfolio_summary(request):
    user = request.auth
    summary = await InvestmentProcessor.get_portfolio_summary(user)
    return CustomResponse.success("Portfolio summary retrieved successfully", summary)


@investment_router.get(
    "/portfolio/details",
    summary="Get detailed portfolio",
    response={200: InvestmentPortfolioDataResponseSchema},
)
async def get_portfolio_details(request):
    user = request.auth
    portfolio = await InvestmentProcessor.update_portfolio(user)
    return CustomResponse.success("Portfolio details retrieved successfully", portfolio)
