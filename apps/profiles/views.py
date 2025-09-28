from uuid import UUID
from ninja import File, Form, Query, Router, UploadedFile
from apps.accounts.auth import AuthAdmin
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
    KycFilterSchema,
    UserResponseSchema,
    UserUpdateSchema,
    KYCSubmissionSchema,
    KYCSingleResponseSchema,
    KYCStatusUpdateSchema,
    KYCListResponseSchema,
)
from apps.profiles.models import KYC, Country, KYCStatus
from asgiref.sync import sync_to_async
from django.utils import timezone

from apps.profiles.tasks import KYCTasks

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
    user_kyc = await KYC.objects.select_related("user", "country").aget_or_none(
        user=user
    )
    if user_kyc and user_kyc.status != KYCStatus.RESUBMIT_REQUIRED:
        raise RequestError(
            err_code=ErrorCode.KYC_ALREADY_SUBMITTED,
            err_msg="KYC already submitted. Contact support for updates.",
        )

    country = await Country.objects.aget_or_none(id=data.country_id, is_active=True)
    if not country:
        raise ValidationError("country_id", "Invalid country selected")

    try:
        kyc_data = data.model_dump()
        kyc_data.pop("country_id")
        if user_kyc:
            user_kyc = set_dict_attr(user_kyc, kyc_data)
            user_kyc.country = country
            if document_file:
                user_kyc.document_file = document_file
            if document_back_file:
                user_kyc.document_back_file = document_back_file
            if selfie_file:
                user_kyc.selfie_file = selfie_file
            user_kyc.status = KYCStatus.PENDING
            await user_kyc.asave()
            kyc = user_kyc
        else:
            kyc = await KYC.objects.acreate(
                user=user,
                country=country,
                document_file=document_file,
                document_back_file=document_back_file,
                selfie_file=selfie_file,
                **kyc_data,
            )

        # Submit to background task for verification
        KYCTasks.process_kyc_verification.delay(str(kyc.id))
        return CustomResponse.success(
            message="KYC submitted successfully and queued for verification.", data=kyc
        )

    except Exception as e:
        return CustomResponse.error(
            message=f"Failed to submit KYC: Please Contact support",
            err_code=ErrorCode.SERVER_ERROR,
            status_code=500,
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
    "/kyc/{kyc_id}/manual-review",
    summary="Mark for Manual Review (Admin)",
    description="""
        Admin endpoint to review a KYC submission.
    """,
    response=KYCSingleResponseSchema,
    auth=AuthAdmin(),
)
async def review_kyc(request, kyc_id: UUID, data: KYCStatusUpdateSchema):
    kyc = await KYC.objects.select_related("user", "country").aget_or_none(id=kyc_id)
    if not kyc:
        raise NotFoundError("KYC submission not found")

    kyc = set_dict_attr(kyc, data.model_dump(exclude_unset=True))
    kyc.reviewed_by = request.auth
    kyc.reviewed_at = timezone.now()
    await kyc.asave()
    return CustomResponse.success(message="KYC reviewd successfully", data=kyc)


@profiles_router.get(
    "/kyc/list",
    summary="List KYC Submissions (Admin)",
    description="""
        Admin endpoint to list all KYC submissions.
    """,
    response=KYCListResponseSchema,
    auth=AuthAdmin(),
)
async def list_kyc_submissions(request, filters: KycFilterSchema = Query(...)):
    kycs = KYC.objects.select_related("country", "user")
    filtered_kycs = filters.filter(kycs)
    kyc_list = await sync_to_async(list)(filtered_kycs.order_by("-created_at"))
    return CustomResponse.success(
        message="KYC submissions retrieved successfully", data=kyc_list
    )
