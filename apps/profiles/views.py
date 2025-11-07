from ninja import File, Form, Query, Router, UploadedFile
from apps.accounts.models import User
from apps.common.exceptions import BodyValidationError
from apps.common.responses import CustomResponse
from apps.common.utils import set_dict_attr
from apps.common.cache import cacheable, invalidate_cache
from apps.profiles.schemas import (
    CountryFilterSchema,
    CountryListResponseSchema,
    UserResponseSchema,
    UserUpdateSchema,
)
from apps.profiles.models import Country
from asgiref.sync import sync_to_async
from apps.compliance.models import KYCVerification, KYCStatus

profiles_router = Router(tags=["Profiles (3)"])


@profiles_router.get(
    "",
    summary="Get Profile",
    description="""
        This endpoint returns the profile of a user out from all devices.
    """,
    response=UserResponseSchema,
)
@cacheable(key="profile:{{user_id}}", ttl=60)
async def get_user(request):
    user = request.auth
    kyc = (
        await KYCVerification.objects.filter(user=user).order_by("-created_at").afirst()
    )
    user.kyc_level = kyc.level if kyc and kyc.status == KYCStatus.APPROVED else None
    return CustomResponse.success(message="Profile retrieved successfully", data=user)


@profiles_router.put(
    "",
    summary="Update Profile",
    description="""
        This endpoint updates the profile of a user.
    """,
    response=UserResponseSchema,
)
@invalidate_cache(patterns=["profile:{{user_id}}"])
async def update_user(
    request, data: Form[UserUpdateSchema], avatar: File[UploadedFile] = None
):
    user = request.auth
    phone_already_used = (
        await User.objects.filter(phone=data.phone).exclude(id=user.id).aexists()
    )
    if phone_already_used:
        raise BodyValidationError("phone", "Phone number already used")
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
@cacheable(key="countries:list", ttl=300)
async def list_countries(request, filters: CountryFilterSchema = Query(...)):
    filtered_countries = filters.filter(Country.objects.filter(is_active=True))
    countries = await sync_to_async(list)(filtered_countries)
    return CustomResponse.success(
        message="Countries retrieved successfully", data=countries
    )
