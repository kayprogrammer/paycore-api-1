from ninja import Router, Query, File, Form
from ninja.files import UploadedFile
from typing import Optional
from uuid import UUID
import logging

from apps.accounts.auth import AuthUser, AuthAdmin
from apps.common.responses import CustomResponse
from django.conf import settings
from apps.compliance.tasks import KYCTasks

# from apps.common.schemas import PaginationQuerySchema

logger = logging.getLogger(__name__)
from apps.compliance.schemas import (
    CreateKYCSchema,
    KYCLevelSchema,
    # KYCVerificationsResponseSchema,
    # UpdateKYCStatusSchema,
    KYCVerificationDataResponseSchema,
    KYCVerificationListDataResponseSchema,
    # KYCVerificationPaginatedDataResponseSchema,
    # CreateAMLCheckSchema,
    # UpdateAMLReviewSchema,
    # AMLCheckDataResponseSchema,
    # AMLCheckPaginatedDataResponseSchema,
    # CreateSanctionsScreeningSchema,
    # UpdateSanctionsReviewSchema,
    # SanctionsScreeningDataResponseSchema,
    # SanctionsScreeningPaginatedDataResponseSchema,
    # TransactionMonitoringDataResponseSchema,
    # TransactionMonitoringPaginatedDataResponseSchema,
    # ResolveMonitoringAlertSchema,
    # CreateComplianceReportSchema,
    # ComplianceReportDataResponseSchema,
    # ComplianceReportPaginatedDataResponseSchema,
    # ComplianceStatisticsDataResponseSchema,
)
from apps.compliance.services.kyc_manager import KYCManager

# from apps.compliance.services.compliance_checker import ComplianceChecker
# from apps.accounts.models import User
# from apps.compliance.tasks import KYCWebhookTasks
# import json

compliance_router = Router(tags=["Compliance (4)"])


# ==================== KYC ENDPOINTS ====================


@compliance_router.post(
    "/kyc/submit",
    summary="Submit KYC verification",
    response={201: KYCVerificationDataResponseSchema},
    auth=AuthUser(),
)
async def submit_kyc(
    request,
    data: Form[CreateKYCSchema],
    id_document: UploadedFile = File(...),
    selfie: UploadedFile = File(...),
    proof_of_address: UploadedFile = File(None),
):
    user = request.auth
    kyc = await KYCManager.submit_kyc(user, data, id_document, selfie, proof_of_address)

    # Schedule auto-approval if using internal provider
    if settings.USE_INTERNAL_PROVIDER:
        # Schedule instant auto-approval
        KYCTasks.auto_approve_kyc.apply_async(
            args=[str(kyc.kyc_id)], countdown=0  # Instant approval
        )
        logger.info(f"Scheduled instant auto-approval for KYC {kyc.kyc_id}")

    return CustomResponse.success("KYC verification submitted successfully", kyc, 201)


@compliance_router.get(
    "/kyc/my-verifications",
    summary="Get my KYC verifications",
    response={200: KYCVerificationListDataResponseSchema},
    auth=AuthUser(),
)
async def get_my_kyc_verifications(request, status: Optional[str] = None):
    user = request.auth
    verifications = await KYCManager.list_user_kyc(user, status)
    return CustomResponse.success(
        "KYC verifications retrieved successfully", verifications
    )


@compliance_router.get(
    "/kyc/{kyc_id}",
    summary="Get KYC verification details",
    response={200: KYCVerificationDataResponseSchema},
    auth=AuthUser(),
)
async def get_kyc_verification(request, kyc_id: UUID):
    user = request.auth
    kyc = await KYCManager.get_kyc(user, kyc_id)
    return CustomResponse.success("KYC verification retrieved successfully", kyc)


@compliance_router.get(
    "/kyc/level/current-level",
    summary="Get current KYC level",
    response={200: KYCLevelSchema},
    auth=AuthUser(),
)
async def get_current_kyc_level(request):
    user = request.auth
    level = await KYCManager.get_user_current_kyc_level(user)
    return CustomResponse.success(
        "Current KYC level retrieved successfully", {"level": level}
    )


# ==================== KYC ADMIN ENDPOINTS ====================


# @compliance_router.get(
#     "/admin/kyc/list",
#     summary="List all KYC verifications (Admin)",
#     response={200: KYCVerificationsResponseSchema},
#     auth=AuthAdmin(),
# )
# async def list_all_kyc_verifications(
#     request,
#     status: Optional[str] = None,
#     level: Optional[str] = None,
#     page_params: PaginationQuerySchema = Query(...),
# ):
#     paginated_data = await KYCManager.list_all_kyc(status, level, page_params)
#     return CustomResponse.success(
#         "KYC verifications retrieved successfully", paginated_data
#     )


# @compliance_router.patch(
#     "/admin/kyc/{kyc_id}/status",
#     summary="Update KYC verification status (Admin)",
#     response={200: KYCVerificationDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def update_kyc_status(request, kyc_id: UUID, data: UpdateKYCStatusSchema):
#     admin_user = request.auth
#     kyc = await KYCManager.update_kyc_status(admin_user, kyc_id, data)
#     return CustomResponse.success("KYC status updated successfully", kyc)


# # ==================== AML ENDPOINTS ====================


# @compliance_router.post(
#     "/admin/aml/create",
#     summary="Create AML check (Admin)",
#     response={201: AMLCheckDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def create_aml_check(request, data: CreateAMLCheckSchema):
#     aml_check = await ComplianceChecker.create_aml_check(data)
#     return CustomResponse.success("AML check created successfully", aml_check, 201)


# @compliance_router.get(
#     "/admin/aml/list",
#     summary="List AML checks (Admin)",
#     response={200: AMLCheckPaginatedDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def list_aml_checks(
#     request,
#     user_id: Optional[UUID] = None,
#     risk_level: Optional[str] = None,
#     requires_review: Optional[bool] = None,
#     page_params: PaginationQuerySchema = Query(...),
# ):

#     user = None
#     if user_id:
#         user = await User.objects.aget_or_none(id=user_id)

#     paginated_data = await ComplianceChecker.list_aml_checks(
#         user, risk_level, requires_review, page_params
#     )
#     return CustomResponse.success("AML checks retrieved successfully", paginated_data)


# @compliance_router.get(
#     "/admin/aml/{check_id}",
#     summary="Get AML check details (Admin)",
#     response={200: AMLCheckDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def get_aml_check(request, check_id: UUID):
#     aml_check = await ComplianceChecker.get_aml_check(check_id)
#     return CustomResponse.success("AML check retrieved successfully", aml_check)


# @compliance_router.patch(
#     "/admin/aml/{check_id}/review",
#     summary="Update AML check review (Admin)",
#     response={200: AMLCheckDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def update_aml_review(request, check_id: UUID, data: UpdateAMLReviewSchema):
#     admin_user = request.auth
#     aml_check = await ComplianceChecker.update_aml_review(admin_user, check_id, data)
#     return CustomResponse.success("AML check review updated successfully", aml_check)


# # ==================== SANCTIONS SCREENING ENDPOINTS ====================


# @compliance_router.post(
#     "/admin/sanctions/create",
#     summary="Create sanctions screening (Admin)",
#     response={201: SanctionsScreeningDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def create_sanctions_screening(request, data: CreateSanctionsScreeningSchema):
#     screening = await ComplianceChecker.create_sanctions_screening(data)
#     return CustomResponse.success(
#         "Sanctions screening created successfully", screening, 201
#     )


# @compliance_router.get(
#     "/admin/sanctions/list",
#     summary="List sanctions screenings (Admin)",
#     response={200: SanctionsScreeningPaginatedDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def list_sanctions_screenings(
#     request,
#     user_id: Optional[UUID] = None,
#     is_match: Optional[bool] = None,
#     page_params: PaginationQuerySchema = Query(...),
# ):
#     user = None
#     if user_id:
#         user = await User.objects.aget_or_none(id=user_id)

#     paginated_data = await ComplianceChecker.list_sanctions_screenings(
#         user, is_match, page_params
#     )
#     return CustomResponse.success(
#         "Sanctions screenings retrieved successfully", paginated_data
#     )


# @compliance_router.get(
#     "/admin/sanctions/{screening_id}",
#     summary="Get sanctions screening details (Admin)",
#     response={200: SanctionsScreeningDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def get_sanctions_screening(request, screening_id: UUID):
#     screening = await ComplianceChecker.get_sanctions_screening(screening_id)
#     return CustomResponse.success(
#         "Sanctions screening retrieved successfully", screening
#     )


# @compliance_router.patch(
#     "/admin/sanctions/{screening_id}/review",
#     summary="Update sanctions screening review (Admin)",
#     response={200: SanctionsScreeningDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def update_sanctions_review(
#     request, screening_id: UUID, data: UpdateSanctionsReviewSchema
# ):
#     admin_user = request.auth
#     screening = await ComplianceChecker.update_sanctions_review(
#         admin_user, screening_id, data
#     )
#     return CustomResponse.success(
#         "Sanctions screening review updated successfully", screening
#     )


# # ==================== TRANSACTION MONITORING ENDPOINTS ====================


# @compliance_router.get(
#     "/admin/monitoring/list",
#     summary="List transaction monitoring alerts (Admin)",
#     response={200: TransactionMonitoringPaginatedDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def list_monitoring_alerts(
#     request,
#     user_id: Optional[UUID] = None,
#     risk_level: Optional[str] = None,
#     is_resolved: Optional[bool] = None,
#     page_params: PaginationQuerySchema = Query(...),
# ):
#     user = None
#     if user_id:
#         user = await User.objects.aget_or_none(id=user_id)

#     paginated_data = await ComplianceChecker.list_monitoring_alerts(
#         user, risk_level, is_resolved, page_params
#     )
#     return CustomResponse.success(
#         "Transaction monitoring alerts retrieved successfully", paginated_data
#     )


# @compliance_router.get(
#     "/admin/monitoring/{monitoring_id}",
#     summary="Get transaction monitoring alert details (Admin)",
#     response={200: TransactionMonitoringDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def get_monitoring_alert(request, monitoring_id: UUID):
#     alert = await ComplianceChecker.get_monitoring_alert(monitoring_id)
#     return CustomResponse.success(
#         "Transaction monitoring alert retrieved successfully", alert
#     )


# @compliance_router.patch(
#     "/admin/monitoring/{monitoring_id}/resolve",
#     summary="Resolve transaction monitoring alert (Admin)",
#     response={200: TransactionMonitoringDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def resolve_monitoring_alert(
#     request, monitoring_id: UUID, data: ResolveMonitoringAlertSchema
# ):
#     admin_user = request.auth
#     alert = await ComplianceChecker.resolve_monitoring_alert(
#         admin_user, monitoring_id, data
#     )
#     return CustomResponse.success(
#         "Transaction monitoring alert resolved successfully", alert
#     )


# # ==================== COMPLIANCE REPORT ENDPOINTS ====================


# @compliance_router.post(
#     "/admin/reports/generate",
#     summary="Generate compliance report (Admin)",
#     response={201: ComplianceReportDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def generate_compliance_report(request, data: CreateComplianceReportSchema):
#     admin_user = request.auth
#     report = await ComplianceChecker.generate_compliance_report(admin_user, data)
#     return CustomResponse.success(
#         "Compliance report generated successfully", report, 201
#     )


# @compliance_router.get(
#     "/admin/reports/list",
#     summary="List compliance reports (Admin)",
#     response={200: ComplianceReportPaginatedDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def list_compliance_reports(
#     request,
#     report_type: Optional[str] = None,
#     page_params: PaginationQuerySchema = Query(...),
# ):
#     paginated_data = await ComplianceChecker.list_compliance_reports(
#         report_type, page_params
#     )
#     return CustomResponse.success(
#         "Compliance reports retrieved successfully", paginated_data
#     )


# @compliance_router.get(
#     "/admin/reports/{report_id}",
#     summary="Get compliance report details (Admin)",
#     response={200: ComplianceReportDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def get_compliance_report(request, report_id: UUID):
#     report = await ComplianceChecker.get_compliance_report(report_id)
#     return CustomResponse.success("Compliance report retrieved successfully", report)


# # ==================== COMPLIANCE STATISTICS ====================


# @compliance_router.get(
#     "/admin/statistics",
#     summary="Get compliance statistics (Admin)",
#     response={200: ComplianceStatisticsDataResponseSchema},
#     auth=AuthAdmin(),
# )
# async def get_compliance_statistics(request):
#     statistics = await ComplianceChecker.get_compliance_statistics()
#     return CustomResponse.success(
#         "Compliance statistics retrieved successfully", statistics
#     )


# # ==================== WEBHOOK ENDPOINTS ====================


# @compliance_router.post(
#     "/webhooks/kyc",
#     summary="KYC Provider Webhook",
#     description="Webhook endpoint for KYC providers (Onfido, Jumio, etc.) to send verification updates",
#     response={200: dict},
#     auth=None,  # Public endpoint, validation done via webhook signature
# )
# async def kyc_provider_webhook(request):
#     """
#     Receive webhook notifications from KYC providers
#     Validates webhook signature and processes the update
#     """

#     try:
#         if request.body:
#             webhook_data = json.loads(request.body.decode("utf-8"))
#         else:
#             webhook_data = dict(request.POST)

#         # TODO: Validate webhook signature based on provider
#         # For Onfido: validate X-SHA2-Signature header
#         # For Jumio: validate Authorization header

#         # Process webhook asynchronously
#         KYCWebhookTasks.process_kyc_webhook.delay(webhook_data)

#         return CustomResponse.success(
#             "Webhook received and queued for processing", {"status": "queued"}
#         )

#     except json.JSONDecodeError:
#         return CustomResponse.error("Invalid JSON payload", "invalid_payload", 400)
#     except Exception as e:
#         logger.error(f"Webhook processing error: {str(e)}")
#         return CustomResponse.error("Webhook processing failed", "webhook_error", 500)
