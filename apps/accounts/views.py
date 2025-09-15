from ninja import File, Router, UploadedFile, Form
from apps.accounts.auth import AuthUser, Authentication
from apps.accounts.emails import EmailUtil
from apps.accounts.models import User
from apps.accounts.schemas import (
    EmailSchema,
    LoginUserSchema,
    RegisterResponseSchema,
    RegisterUserSchema,
    SetNewPasswordSchema,
    TokenSchema,
    TokensResponseSchema,
    UserResponseSchema,
    UserUpdateSchema,
    VerifyOtpSchema,
)
from apps.common.exceptions import ErrorCode, RequestError, ValidationError
from apps.common.responses import CustomResponse
from apps.common.schemas import ResponseSchema
from apps.common.utils import set_dict_attr

auth_router = Router(tags=["Auth"])


@auth_router.post(
    "/register",
    summary="Register a new user",
    description="This endpoint registers new users into our application",
    response={201: RegisterResponseSchema},
)
async def register(request, data: RegisterUserSchema):
    # Check for existing user
    existing_user = await User.objects.aget_or_none(email=data.email)
    if existing_user:
        raise ValidationError("email", "Email already registered!")

    # Create user
    user = await User.objects.acreate_user(**data.model_dump())

    # Send verification email
    await EmailUtil.send_otp(user, "account verification")

    return CustomResponse.success(
        message="Registration successful", data={"email": data.email}, status_code=201
    )


@auth_router.post(
    "/verify-email",
    summary="Verify a user's email",
    description="""
        This endpoint verifies a user's email
    """,
    response=ResponseSchema,
)
async def verify_email(request, data: VerifyOtpSchema):
    email = data.email
    otp_code = data.otp

    user = await User.objects.aget_or_none(email=email)

    if not user:
        raise RequestError(
            err_code=ErrorCode.INCORRECT_EMAIL,
            err_msg="Incorrect Email",
            status_code=404,
        )

    if user.is_email_verified:
        return CustomResponse.success(message="Email already verified")

    if user.otp_code != otp_code:
        raise RequestError(
            err_code=ErrorCode.INCORRECT_OTP, err_msg="Incorrect Otp", status_code=404
        )
    if user.is_otp_expired():
        raise RequestError(
            err_code=ErrorCode.EXPIRED_OTP, err_msg="Expired Otp", status_code=410
        )

    user.is_email_verified = True
    user.otp_code, user.otp_expires_at = None, None
    await user.asave()

    # Send welcome email
    EmailUtil.welcome_email(user)
    return CustomResponse.success(message="Account verification successful")


@auth_router.post(
    "/resend-verification-otp",
    summary="Resend Verification Email",
    description="""
        This endpoint resends new otp to the user's email
    """,
    response=ResponseSchema,
)
async def resend_verification_email(request, data: EmailSchema):
    email = data.email
    user = await User.objects.aget_or_none(email=email)
    if not user:
        raise RequestError(
            err_code=ErrorCode.INCORRECT_EMAIL,
            err_msg="Incorrect Email",
            status_code=404,
        )
    if user.is_email_verified:
        return CustomResponse.success(message="Email already verified")

    # Send verification email
    await EmailUtil.send_otp(user, "account verification")
    return CustomResponse.success(message="Verification email sent")


@auth_router.post(
    "/send-password-reset-otp",
    summary="Send Password Reset Otp",
    description="""
        This endpoint sends new password reset otp to the user's email
    """,
    response=ResponseSchema,
)
async def send_password_reset_otp(request, data: EmailSchema):
    email = data.email
    user = await User.objects.aget_or_none(email=email)
    if not user:
        raise RequestError(
            err_code=ErrorCode.INCORRECT_EMAIL,
            err_msg="Incorrect Email",
            status_code=404,
        )

    # Send password reset email
    await EmailUtil.send_otp(user, "password reset")
    return CustomResponse.success(message="Password otp sent")


@auth_router.post(
    "/set-new-password",
    summary="Set New Password",
    description="This endpoint verifies the password reset otp",
    response=ResponseSchema,
)
async def set_new_password(request, data: SetNewPasswordSchema):
    email = data.email
    code = data.otp
    password = data.password

    user = await User.objects.aget_or_none(email=email)
    if not user:
        raise RequestError(
            err_code=ErrorCode.INCORRECT_EMAIL,
            err_msg="Incorrect Email",
            status_code=404,
        )

    if user.otp_code != code:
        raise RequestError(
            err_code=ErrorCode.INCORRECT_OTP,
            err_msg="Incorrect Otp",
            status_code=404,
        )

    if user.is_otp_expired():
        raise RequestError(
            err_code=ErrorCode.EXPIRED_OTP, err_msg="Expired Otp", status_code=410
        )

    user.set_password(password)
    await user.asave()

    # Send password reset success email
    EmailUtil.password_reset_confirmation(user)
    return CustomResponse.success(message="Password reset successful")


# @auth_router.post(
#     "/login",
#     summary="Login a user",
#     description="""
#         This endpoint generates new access and refresh tokens for authentication
#     """,
#     response={201: TokensResponseSchema},
# )
# async def login(request, data: LoginUserSchema):
#     email = data.email
#     password = data.password

#     user = await User.objects.aget_or_none(email=email)
#     if not user or not user.check_password(password):
#         raise RequestError(
#             err_code=ErrorCode.INVALID_CREDENTIALS,
#             err_msg="Invalid credentials",
#             status_code=401,
#         )

#     if not user.is_email_verified:
#         raise RequestError(
#             err_code=ErrorCode.UNVERIFIED_USER,
#             err_msg="Verify your email first",
#             status_code=401,
#         )

#     # Create tokens and store in jwt model
#     access = Authentication.create_access_token(user.id)
#     refresh = Authentication.create_refresh_token()
#     await Jwt.objects.acreate(user=user, access=access, refresh=refresh)

#     return CustomResponse.success(
#         message="Login successful",
#         data={"access": access, "refresh": refresh},
#         status_code=201,
#     )


# @auth_router.post(
#     "/refresh",
#     summary="Refresh tokens",
#     description="""
#         This endpoint refresh tokens by generating new access and refresh tokens for a user
#     """,
#     response={201: TokensResponseSchema},
# )
# async def refresh(request, data: TokenSchema):
#     token = data.token
#     jwt = await Jwt.objects.aget_or_none(refresh=token)

#     if not jwt or not Authentication.decode_jwt(token):
#         raise RequestError(
#             err_code=ErrorCode.INVALID_TOKEN,
#             err_msg="Refresh token is invalid or expired",
#             status_code=401,
#         )

#     user = await User.objects.aget(id=jwt.user_id)
#     access = Authentication.create_access_token(user.id)
#     refresh = Authentication.create_refresh_token()

#     jwt.access = access
#     jwt.refresh = refresh
#     await jwt.asave()

#     return CustomResponse.success(
#         message="Tokens refresh successful",
#         data={"access": access, "refresh": refresh},
#         status_code=201,
#     )


# @auth_router.post(
#     "/google-login",
#     summary="Google Auth",
#     description="""
#         This endpoint authenticates a user by generating new access and refresh tokens for a user based on their google id token
#         If user doesn't exist in our platform, we'll create and authenticate, else, we'll just authenticate
#     """,
#     response={201: TokensResponseSchema},
# )
# async def google_login(request, data: TokenSchema):
#     token = data.token
#     user_data, err_code, err_msg = Authentication.validate_google_token(token)
#     if not user_data:
#         raise RequestError(err_code, err_msg, 401)
#     user = await Authentication.store_google_user(
#         user_data["email"], user_data["name"], user_data["picture"]
#     )

#     access = Authentication.create_access_token(user.id)
#     refresh = Authentication.create_refresh_token()
#     await Jwt.objects.acreate(user=user, access=access, refresh=refresh)

#     return CustomResponse.success(
#         message="Tokens created successfully",
#         data={"access": access, "refresh": refresh},
#         status_code=201,
#     )


# @auth_router.get(
#     "/logout",
#     summary="Logout a user",
#     description="""
#         This endpoint logs a user out from our application by invalidating the token from our backend
#     """,
#     response=ResponseSchema,
#     auth=AuthUser(),
# )
# async def logout(request):
#     user = request.auth
#     auth_header = request.META.get("HTTP_AUTHORIZATION") or request.META.get(
#         "HTTP_Authorization"
#     )
#     access_token = auth_header[7:] if auth_header else None
#     await Jwt.objects.filter(user=user, access=access_token).adelete()
#     return CustomResponse.success(message="Logout successful")


# @auth_router.get(
#     "/logout-all",
#     summary="Logout All",
#     description="""
#         This endpoint logs a user out from all devices. It invalidates all of that user's tokens from our app
#     """,
#     response=ResponseSchema,
#     auth=AuthUser(),
# )
# async def logout_all(request):
#     user = request.auth
#     await Jwt.objects.filter(user=user).adelete()
#     return CustomResponse.success(message="Logout successful")


# PROFILES
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
