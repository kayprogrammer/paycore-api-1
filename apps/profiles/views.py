from ninja import File, Form, Query, Router, UploadedFile
from apps.common.exceptions import (
    ErrorCode,
    NotFoundError,
    RequestError,
    ValidationError,
)
from apps.common.responses import CustomResponse
from apps.common.utils import set_dict_attr
from apps.profiles.schemas import (
    CountryFilterSchema,
    CountryListResponseSchema,
    UserResponseSchema,
    UserUpdateSchema,
    KYCSubmissionSchema,
    KYCSingleResponseSchema,
    KYCStatusUpdateSchema,
    KYCListResponseSchema,
)
from apps.profiles.models import KYC, Country, KYCStatus
from apps.profiles.services import KYCValidationService
from asgiref.sync import sync_to_async

profiles_router = Router(tags=["Profiles"])


@profiles_router.get(
    "",
    summary="Get Profile",
    description="""
        This endpoint returns the profile of a user out from all devices.
    """,
    response=UserResponseSchema,
)
async def get_user(request):
    user = request.auth
    return CustomResponse.success(message="Profile retrieved successfully", data=user)


@profiles_router.put(
    "",
    summary="Update Profile",
    description="""
        This endpoint updates the profile of a user.
    """,
    response=UserResponseSchema,
)
async def update_user(
    request, data: Form[UserUpdateSchema], avatar: File[UploadedFile] = None
):
    user = request.auth
    user = set_dict_attr(user, data.model_dump())
    user.avatar = avatar
    await user.asave()
    return CustomResponse.success(message="Profile updated successfully", data=user)


@profiles_router.get(
    "/countries",
    summary="List Countries",
    description="""
        This endpoint returns a list of supported countries for KYC and other operations.
    """,
    response=CountryListResponseSchema,
)
async def list_countries(request, filters: CountryFilterSchema = Query(...)):
    filtered_countries = filters.filter(Country.objects.filter(is_active=True))
    countries = await sync_to_async(list)(filtered_countries)
    return CustomResponse.success(
        message="Countries retrieved successfully", data=countries
    )


@profiles_router.post(
    "/kyc/submit",
    summary="Submit KYC",
    description="""
        This endpoint submits KYC (Know Your Customer) information for verification.
        Users can upload identity documents and selfies for identity verification.
    """,
    response=KYCSingleResponseSchema,
)
async def submit_kyc(
    request,
    data: Form[KYCSubmissionSchema],
    document_file: File[UploadedFile],
    document_back_file: File[UploadedFile] = None,
    selfie_file: File[UploadedFile] = None,
):
    user = request.auth
    user_kyc = await KYC.objects.select_related("country").aget_or_none(user=user)
    if user_kyc:
        raise RequestError(
            err_code=ErrorCode.KYC_ALREADY_SUBMITTED,
            err_msg="KYC already submitted. Contact support for updates.",
        )

    country = await Country.objects.aget_or_none(id=data.country_id, is_active=True)
    if not country:
        raise ValidationError("country_id", "Invalid country selected")

    try:
        # Create KYC record
        kyc_data = data.model_dump()
        kyc_data.pop(
            "country_id"
        )  # Remove country_id since we'll set the country object

        kyc = await KYC.objects.acreate(
            user=user,
            country=country,
            document_file=document_file,
            document_back_file=document_back_file,
            selfie_file=selfie_file,
            **kyc_data,
        )

        # Submit to third-party verification service
        validation_service = KYCValidationService()
        document_files = {
            "document_file": document_file,
        }
        if document_back_file:
            document_files["document_back_file"] = document_back_file
        if selfie_file:
            document_files["selfie_file"] = selfie_file

        # Submit for automated verification
        submission_success = validation_service.submit_kyc_for_verification(
            kyc, document_files
        )

        if not submission_success:
            # If automated submission fails, keep as pending for manual review
            return CustomResponse.success(
                message="KYC submitted successfully. Processing may take longer than usual.",
                data=kyc,
            )

        return CustomResponse.success(
            message="KYC submitted successfully and sent for verification.", data=kyc
        )

    except Exception as e:
        return CustomResponse.error(
            message=f"Failed to submit KYC: Please Contact support", status_code=500
        )


@profiles_router.get(
    "/kyc/status",
    summary="Get KYC Status",
    description="""
        This endpoint returns the current KYC verification status for the authenticated user.
    """,
    response=KYCSingleResponseSchema,
)
async def get_kyc_status(request):
    user = request.auth

    kyc = await KYC.objects.select_related("country").aget_or_none(user=user)
    if not kyc:
        raise NotFoundError("No KYC submission found")
    return CustomResponse.success(message="KYC status retrieved successfully", data=kyc)


# ADMIN/MANUAL REVIEW ENDPOINTS


@profiles_router.put(
    "/kyc/{kyc_id}/approve",
    summary="Approve KYC (Admin)",
    description="""
        Admin endpoint to manually approve a KYC submission.
    """,
    response=KYCSingleResponseSchema,
)
async def approve_kyc(request, kyc_id: int, data: KYCStatusUpdateSchema):
    # Note: Add proper admin authentication here
    kyc = await KYC.objects.aget_or_none(id=kyc_id)
    if not kyc:
        raise NotFoundError("KYC submission not found")

    validation_service = KYCValidationService()
    await sync_to_async(validation_service.approve_kyc)(kyc, data.notes or "")

    return CustomResponse.success(message="KYC approved successfully", data=kyc)


@profiles_router.put(
    "/kyc/{kyc_id}/reject",
    summary="Reject KYC (Admin)",
    description="""
        Admin endpoint to manually reject a KYC submission.
    """,
    response=KYCSingleResponseSchema,
)
async def reject_kyc(request, kyc_id: int, data: KYCStatusUpdateSchema):
    # Note: Add proper admin authentication here
    if not data.rejection_reason:
        raise ValidationError("rejection_reason", "Rejection reason is required")

    kyc = await KYC.objects.aget_or_none(id=kyc_id)
    if not kyc:
        raise NotFoundError("KYC submission not found")

    validation_service = KYCValidationService()
    await sync_to_async(validation_service.reject_kyc)(kyc, data.rejection_reason)

    return CustomResponse.success(message="KYC rejected successfully", data=kyc)


@profiles_router.put(
    "/kyc/{kyc_id}/manual-review",
    summary="Mark for Manual Review (Admin)",
    description="""
        Admin endpoint to mark a KYC submission for manual review.
    """,
    response=KYCSingleResponseSchema,
)
async def mark_manual_review(request, kyc_id: int, data: KYCStatusUpdateSchema):
    # Note: Add proper admin authentication here
    kyc = await KYC.objects.aget_or_none(id=kyc_id)
    if not kyc:
        raise NotFoundError("KYC submission not found")

    validation_service = KYCValidationService()
    await sync_to_async(validation_service.manual_review_required)(
        kyc, data.notes or "Manual review requested"
    )

    return CustomResponse.success(message="KYC marked for manual review", data=kyc)


@profiles_router.get(
    "/kyc/pending-review",
    summary="List Pending KYC Reviews (Admin)",
    description="""
        Admin endpoint to list all KYC submissions pending manual review.
    """,
    response=KYCListResponseSchema,
)
async def list_pending_kyc(request):
    # Note: Add proper admin authentication here
    pending_kycs = await sync_to_async(list)(
        KYC.objects.select_related("country", "user")
        .filter(status__in=[KYCStatus.PENDING, KYCStatus.UNDER_REVIEW])
        .order_by("-created_at")
    )

    return CustomResponse.success(
        message="Pending KYC reviews retrieved successfully", data=pending_kycs
    )
