from ninja import File, Form, Router, UploadedFile
from apps.accounts.auth import AuthUser
from apps.common.responses import CustomResponse
from apps.common.utils import set_dict_attr
from apps.profiles.schemas import UserResponseSchema, UserUpdateSchema


profiles_router = Router(tags=["Profiles"])


@profiles_router.get(
    "",
    summary="Get Profile",
    description="""
        This endpoint returns the profile of a user out from all devices.
    """,
    response=UserResponseSchema,
    auth=AuthUser(),
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
    auth=AuthUser(),
)
async def update_user(
    request, data: Form[UserUpdateSchema], avatar: File[UploadedFile] = None
):
    user = request.auth
    user = set_dict_attr(user, data.model_dump())
    user.avatar = avatar
    await user.asave()
    return CustomResponse.success(message="Profile updated successfully", data=user)
