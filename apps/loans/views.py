from decimal import Decimal
from uuid import UUID
from typing import Optional
from ninja import Query, Router
from django.conf import settings

from apps.common.responses import CustomResponse
from apps.common.schemas import PaginationQuerySchema
from apps.loans.models import LoanProductType, LoanRepayment
from apps.loans.schemas import (
    CreateLoanApplicationSchema,
    LoanApplicationDataResponseSchema,
    LoanApplicationListDataResponseSchema,
    LoanCalculationDataResponseSchema,
    LoanProductDataResponseSchema,
    LoanProductListDataResponseSchema,
    LoanRepaymentListResponseSchema,
    MakeLoanRepaymentSchema,
    LoanRepaymentDataResponseSchema,
    CreditScoreDataResponseSchema,
    LoanSummaryDataResponseSchema,
    LoanDetailsDataResponseSchema,
    EnableAutoRepaymentSchema,
    RepaymentScheduleListResponseSchema,
    UpdateAutoRepaymentSchema,
    AutoRepaymentDataResponseSchema,
)
from apps.loans.services.loan_manager import LoanManager
from apps.loans.services.loan_processor import LoanProcessor
from apps.loans.services.credit_score_service import CreditScoreService
from apps.loans.services.auto_repayment_service import AutoRepaymentService
from apps.loans.tasks import LoanApprovalTasks


loan_router = Router(tags=["Loans (20)"])


# ==================== LOAN PRODUCTS ====================


@loan_router.get(
    "/products/list",
    summary="List loan products",
    response={200: LoanProductListDataResponseSchema},
)
async def list_loan_products(
    request,
    currency_code: Optional[str] = None,
    product_type: Optional[LoanProductType] = None,
):
    products = await LoanManager.get_active_loan_products(currency_code, product_type)

    return CustomResponse.success("Loan products retrieved successfully", products)


@loan_router.get(
    "/products/{product_id}",
    summary="Get loan product details",
    response={200: LoanProductDataResponseSchema},
)
async def get_loan_product(request, product_id: UUID):
    product = await LoanManager.get_loan_product(product_id)
    return CustomResponse.success("Loan product retrieved successfully", product)


@loan_router.post(
    "/calculate",
    summary="Calculate loan details",
    response={200: LoanCalculationDataResponseSchema},
)
async def calculate_loan(
    request,
    product_id: UUID,
    amount: float,
    tenure_months: int,
    repayment_frequency: str,
):
    product = await LoanManager.get_loan_product(product_id)

    loan_calc = await LoanManager.calculate_loan(
        product, Decimal(str(amount)), tenure_months, repayment_frequency
    )
    return CustomResponse.success("Loan calculation completed", loan_calc)


# ==================== LOAN APPLICATIONS ====================


@loan_router.post(
    "/applications/create",
    summary="Create loan application",
    response={201: LoanApplicationDataResponseSchema},
)
async def create_loan_application(request, data: CreateLoanApplicationSchema):
    user = request.auth
    loan = await LoanManager.create_loan_application(user, data)
    loan = await LoanManager.get_loan_application(user, loan.application_id)

    # Schedule auto-approval after 10 seconds if using internal provider
    if settings.USE_INTERNAL_PROVIDER:
        LoanApprovalTasks.auto_approve_loan.apply_async(
            args=[str(loan.application_id)], countdown=10  # 10 seconds delay
        )

    return CustomResponse.success(
        "Loan application created successfully", loan, status_code=201
    )


@loan_router.get(
    "/applications/list",
    summary="List loan applications",
    response={200: LoanApplicationListDataResponseSchema},
)
async def list_loan_applications(
    request,
    status: Optional[str] = None,
    page_params: PaginationQuerySchema = Query(...),
):
    user = request.auth
    loans_paginated_data = await LoanManager.list_loan_applications(
        user, status, page_params
    )
    return CustomResponse.success(
        "Loan applications retrieved successfully", loans_paginated_data
    )


@loan_router.get(
    "/applications/{application_id}",
    summary="Get loan application details",
    response={200: LoanApplicationDataResponseSchema},
)
async def get_loan_application(request, application_id: UUID):
    user = request.auth
    loan = await LoanManager.get_loan_application(user, application_id)
    return CustomResponse.success("Loan application retrieved successfully", loan)


@loan_router.delete(
    "/applications/{application_id}",
    summary="Cancel loan application",
    response={200: dict},
)
async def cancel_loan_application(request, application_id: UUID):
    user = request.auth
    await LoanManager.cancel_loan_application(user, application_id)
    return CustomResponse.success("Loan application cancelled successfully")


# ==================== REPAYMENT SCHEDULE ====================


@loan_router.get(
    "/applications/{application_id}/schedule",
    summary="Get repayment schedule",
    response={200: RepaymentScheduleListResponseSchema},
)
async def get_repayment_schedule(request, application_id: UUID):
    user = request.auth
    schedules = await LoanManager.get_repayment_schedule(user, application_id)
    return CustomResponse.success(
        "Repayment schedule retrieved successfully", schedules
    )


# ==================== LOAN REPAYMENT ====================


@loan_router.post(
    "/applications/{application_id}/repay",
    summary="Make loan repayment",
    response={201: LoanRepaymentDataResponseSchema},
)
async def make_loan_repayment(
    request, application_id: UUID, data: MakeLoanRepaymentSchema
):
    user = request.auth
    repayment = await LoanProcessor.make_repayment(user, application_id, data)
    repayment = await LoanRepayment.objects.select_related(
        "wallet", "transaction", "schedule"
    ).aget_or_none(repayment_id=repayment.repayment_id)
    return CustomResponse.success("Repayment processed successfully", repayment, 201)


@loan_router.get(
    "/applications/{application_id}/repayments",
    summary="Get loan repayments",
    response={200: LoanRepaymentListResponseSchema},
)
async def get_loan_repayments(
    request, application_id: UUID, page_params: PaginationQuerySchema = Query(...)
):
    user = request.auth
    repayments_paginated_data = await LoanProcessor.get_loan_repayments(
        user, application_id, page_params
    )
    return CustomResponse.success(
        "Repayments retrieved successfully", data=repayments_paginated_data
    )


# ==================== CREDIT SCORE ====================


@loan_router.get(
    "/credit-score",
    summary="Get credit score",
    response={200: CreditScoreDataResponseSchema},
)
async def get_credit_score(request):
    user = request.auth
    credit_score = await CreditScoreService.get_latest_credit_score(user)
    return CustomResponse.success("Credit score retrieved successfully", credit_score)


@loan_router.post(
    "/credit-score/refresh",
    summary="Refresh credit score",
    response={200: CreditScoreDataResponseSchema},
)
async def refresh_credit_score(request):
    user = request.auth
    credit_score = await CreditScoreService.calculate_credit_score(user)
    return CustomResponse.success("Credit score refreshed successfully", credit_score)


# ==================== LOAN SUMMARY & DETAILS ====================


@loan_router.get(
    "/summary",
    summary="Get loan summary",
    response={200: LoanSummaryDataResponseSchema},
)
async def get_loan_summary(request):
    user = request.auth
    summary = await LoanProcessor.get_loan_summary(user)
    return CustomResponse.success("Loan summary retrieved successfully", summary)


@loan_router.get(
    "/applications/{application_id}/details",
    summary="Get comprehensive loan details",
    response={200: LoanDetailsDataResponseSchema},
)
async def get_loan_details(request, application_id: UUID):
    user = request.auth
    details = await LoanProcessor.get_loan_details(user, application_id)
    return CustomResponse.success("Loan details retrieved successfully", details)


# ==================== AUTO-REPAYMENT ====================


@loan_router.post(
    "/applications/{application_id}/auto-repayment/enable",
    summary="Enable automatic repayment",
    response={201: AutoRepaymentDataResponseSchema},
)
async def enable_auto_repayment(
    request, application_id: UUID, data: EnableAutoRepaymentSchema
):
    user = request.auth
    auto_repayment = await AutoRepaymentService.enable_auto_repayment(
        user, application_id, data
    )
    return CustomResponse.success(
        "Automatic repayment enabled successfully", auto_repayment, 201
    )


@loan_router.get(
    "/applications/{application_id}/auto-repayment",
    summary="Get automatic repayment settings",
    response={200: AutoRepaymentDataResponseSchema},
)
async def get_auto_repayment(request, application_id: UUID):
    user = request.auth
    auto_repayment = await AutoRepaymentService.get_auto_repayment(user, application_id)
    return CustomResponse.success(
        "Automatic repayment settings retrieved successfully", auto_repayment
    )


@loan_router.put(
    "/applications/{application_id}/auto-repayment",
    summary="Update automatic repayment settings",
    response={200: AutoRepaymentDataResponseSchema},
)
async def update_auto_repayment(
    request, application_id: UUID, data: UpdateAutoRepaymentSchema
):
    user = request.auth
    auto_repayment = await AutoRepaymentService.update_auto_repayment(
        user, application_id, data
    )
    return CustomResponse.success(
        "Automatic repayment settings updated successfully", auto_repayment
    )


@loan_router.post(
    "/applications/{application_id}/auto-repayment/disable",
    summary="Disable automatic repayment",
    response={200: dict},
)
async def disable_auto_repayment(request, application_id: UUID):
    user = request.auth
    await AutoRepaymentService.disable_auto_repayment(user, application_id)
    return CustomResponse.success("Automatic repayment disabled successfully")


@loan_router.post(
    "/applications/{application_id}/auto-repayment/suspend",
    summary="Suspend automatic repayment temporarily",
    response={200: AutoRepaymentDataResponseSchema},
)
async def suspend_auto_repayment(
    request, application_id: UUID, reason: Optional[str] = None
):
    user = request.auth
    auto_repayment = await AutoRepaymentService.suspend_auto_repayment(
        user, application_id, reason
    )
    return CustomResponse.success(
        "Automatic repayment suspended successfully", auto_repayment
    )


@loan_router.post(
    "/applications/{application_id}/auto-repayment/reactivate",
    summary="Reactivate suspended automatic repayment",
    response={200: AutoRepaymentDataResponseSchema},
)
async def reactivate_auto_repayment(request, application_id: UUID):
    user = request.auth
    auto_repayment = await AutoRepaymentService.reactivate_auto_repayment(
        user, application_id
    )
    return CustomResponse.success(
        "Automatic repayment reactivated successfully", auto_repayment
    )
