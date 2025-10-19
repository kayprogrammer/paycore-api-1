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
    UserResponseSchema,
    UserUpdateSchema,
)
from apps.profiles.models import Country
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
