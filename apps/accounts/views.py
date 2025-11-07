from django.http import HttpResponse
from ninja import Router
from ninja.throttling import AnonRateThrottle
from apps.accounts.auth import AuthUser, Authentication
from apps.accounts.models import User
from apps.accounts.tasks import (
    EmailTasks,
)
from apps.accounts.schemas import (
    BiometricsEnableSchema,
    BiometricsLoginSchema,
    BiometricsResponseSchema,
    EmailSchema,
    LoginUserSchema,
    LoginMfaSchema,
    RegisterResponseSchema,
    RegisterUserSchema,
    SetNewPasswordSchema,
    TokenSchema,
    TokensResponseSchema,
    VerifyOtpSchema,
)
from apps.common.exceptions import BodyValidationError, ErrorCode, RequestError
from apps.common.responses import CustomResponse
from apps.common.schemas import ResponseSchema
from apps.notifications.services.fcm import FCMService

auth_router = Router(tags=["Auth (13)"])


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
        raise BodyValidationError("email", "Email already registered!")

    # Create user
    user = await User.objects.acreate_user(**data.model_dump())

    # Send verification email asynchronously
    task = EmailTasks.send_otp_email.delay(user.id, "account verification")

    return CustomResponse.success(
        message="Registration successful",
        data={"email": data.email, "task_id": task.id},
        status_code=201,
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

    # Send welcome email asynchronously
    EmailTasks.send_welcome_email.delay(user.id)
    return CustomResponse.success(message="Account verification successful")


@auth_router.post(
    "/resend-verification-otp",
    summary="Resend Verification Email",
    description="""
        This endpoint resends new otp to the user's email
    """,
    response=ResponseSchema,
    throttle=AnonRateThrottle("30/1m"),
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

    # Send verification email asynchronously
    task = EmailTasks.send_otp_email.delay(user.id, "account verification")
    return CustomResponse.success(
        message="Verification email sent", data={"task_id": task.id}
    )


@auth_router.post(
    "/send-password-reset-otp",
    summary="Send Password Reset Otp",
    description="""
        This endpoint sends new password reset otp to the user's email
    """,
    response=ResponseSchema,
    throttle=AnonRateThrottle("30/1m"),
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

    # Send password reset email asynchronously
    task = EmailTasks.send_otp_email.delay(user.id, "password reset")
    return CustomResponse.success(
        message="Password otp sent", data={"task_id": task.id}
    )


@auth_router.post(
    "/set-new-password",
    summary="Set New Password",
    description="This endpoint verifies the password reset otp",
    response=ResponseSchema,
    throttle=AnonRateThrottle("30/5m"),
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

    # Send password reset success email asynchronously
    EmailTasks.send_password_reset_confirmation.delay(user.id)
    return CustomResponse.success(message="Password reset successful")


@auth_router.post(
    "/login",
    summary="Initiate secure login",
    description="""
        Step 1: Verify credentials and send OTP for MFA.
        This endpoint validates email/password and sends OTP code.
    """,
    response=ResponseSchema,
    throttle=AnonRateThrottle("50/3m"),
)
async def login_initiate(request, data: LoginUserSchema):
    email = data.email
    password = data.password

    user = await User.objects.aget_or_none(email=email)
    if not user or not user.check_password(password):
        raise RequestError(
            err_code=ErrorCode.INVALID_CREDENTIALS,
            err_msg="Invalid credentials",
            status_code=401,
        )

    if not user.is_email_verified:
        raise RequestError(
            err_code=ErrorCode.UNVERIFIED_USER,
            err_msg="Verify your email first",
            status_code=401,
        )

    # Send MFA OTP asynchronously
    task = EmailTasks.send_otp_email.delay(user.id, "login verification")
    return CustomResponse.success(
        message="Login OTP sent to your email", data={"task_id": task.id}
    )


@auth_router.post(
    "/login/verify",
    summary="Complete secure login with MFA",
    description="""
        Step 2: Verify OTP and receive authentication tokens.
        This endpoint validates the OTP and issues access/refresh tokens.
        Web clients receive refresh token as HTTP-only cookie.
    """,
    response={200: TokensResponseSchema},
    throttle=AnonRateThrottle("100/15m"),
)
async def login_complete(request, data: LoginMfaSchema, response: HttpResponse):
    email = data.email
    otp_code = data.otp

    user = await User.objects.aget_or_none(email=email)
    if not user:
        raise RequestError(
            err_code=ErrorCode.INCORRECT_EMAIL,
            err_msg="Invalid credentials",
            status_code=401,
        )

    if not user.is_email_verified:
        raise RequestError(
            err_code=ErrorCode.UNVERIFIED_USER,
            err_msg="Verify your email first",
            status_code=401,
        )

    if user.otp_code != otp_code:
        raise RequestError(
            err_code=ErrorCode.INCORRECT_OTP,
            err_msg="Invalid OTP code",
            status_code=401,
        )

    if user.is_otp_expired():
        raise RequestError(
            err_code=ErrorCode.EXPIRED_OTP,
            err_msg="OTP has expired",
            status_code=410,
        )

    user.otp_code, user.otp_expires_at = None, None
    await user.asave()

    if data.device_token and data.device_type:
        await FCMService.register_device(user, data.device_token, data.device_type)

    # Create secure tokens
    access_token, refresh_token = await Authentication.create_tokens_for_user(user)

    # Set HTTP-only cookie for web clients
    if Authentication.is_web_client(request):
        Authentication.set_refresh_token_cookie(response, refresh_token)
        refresh_token = "Set as HTTP-only cookie"

    return CustomResponse.success(
        message="Login successful",
        data={"access": access_token, "refresh": refresh_token},
    )


@auth_router.post(
    "/refresh",
    summary="Refresh authentication tokens",
    description="""
        Generate new access and refresh tokens using a valid refresh token.
        Supports both HTTP-only cookies (web) and request body (mobile).
        Implements automatic token rotation for enhanced security.
    """,
    response={200: TokensResponseSchema},
)
async def refresh_tokens(
    request, data: TokenSchema = None, response: HttpResponse = None
):
    # Get refresh token from cookie (web) or request body (mobile)
    refresh_token = None

    # Try cookie first (web clients)
    if hasattr(request, "COOKIES") and "refresh_token" in request.COOKIES:
        refresh_token = request.COOKIES["refresh_token"]
    # Fall back to request body (mobile clients)
    elif data and data.token:
        refresh_token = data.token

    if not refresh_token:
        raise RequestError(
            err_code=ErrorCode.INVALID_TOKEN,
            err_msg="Refresh token not provided",
            status_code=401,
        )

    user, new_access, new_refresh = await Authentication.rotate_refresh_token(
        refresh_token
    )

    if not user:
        raise RequestError(
            err_code=ErrorCode.INVALID_TOKEN,
            err_msg="Refresh token is invalid or expired",
            status_code=401,
        )

    # Set HTTP-only cookie for web clients
    if Authentication.is_web_client(request):
        Authentication.set_refresh_token_cookie(response, new_refresh)
        new_refresh = "Set as HTTP-only cookie"

    return CustomResponse.success(
        message="Tokens refreshed successfully",
        data={"access": new_access, "refresh": new_refresh},
    )


@auth_router.post(
    "/google-login",
    summary="Google OAuth Authentication",
    description="""
        Secure Google OAuth login with automatic user creation.
        Validates Google ID token and creates/authenticates user.
        Web clients receive refresh token as HTTP-only cookie.
    """,
    response={200: TokensResponseSchema},
    throttle=AnonRateThrottle("1000/5m"),
)
async def google_login(request, data: TokenSchema, response: HttpResponse):
    token = data.token

    # Validate Google ID token
    user_data, err_code, err_msg = Authentication.validate_google_token(token)
    if not user_data:
        raise RequestError(err_code, err_msg, 401)

    # Create or retrieve Google user
    user = await Authentication.store_google_user(
        user_data["email"], user_data["name"], user_data.get("picture")
    )

    # Register FCM device and subscribe to global topic if provided
    if data.device_token and data.device_type:
        await FCMService.register_device(user, data.device_token, data.device_type)

    # Create secure tokens using our enhanced system
    access_token, refresh_token = await Authentication.create_tokens_for_user(user)

    # Set HTTP-only cookie for web clients
    if Authentication.is_web_client(request):
        Authentication.set_refresh_token_cookie(response, refresh_token)
        refresh_token = "Set as HTTP-only cookie"

    return CustomResponse.success(
        message="Google login successful",
        data={"access": access_token, "refresh": refresh_token},
    )


@auth_router.post(
    "/logout",
    summary="Logout current session",
    description="""
        Securely logout from the current session by invalidating all user tokens.
        Clears HTTP-only cookies for web clients.
    """,
    response=ResponseSchema,
    auth=AuthUser(),
)
async def logout(request, response: HttpResponse):
    user = request.auth
    await Authentication.invalidate_user_tokens(user)

    # Clear HTTP-only cookie for web clients
    if Authentication.is_web_client(request):
        Authentication.clear_refresh_token_cookie(response)

    return CustomResponse.success(message="Logout successful")


@auth_router.post(
    "/biometrics/enable",
    summary="Enable biometrics authentication",
    description="""
        Enable biometrics login for the authenticated user.
        Creates a trust token that can be used for biometric authentication.
    """,
    response={200: BiometricsResponseSchema},
    auth=AuthUser(),
)
async def enable_biometrics(request, data: BiometricsEnableSchema):
    user = request.auth

    if user.biometrics_enabled:
        raise RequestError(
            err_code=ErrorCode.NOT_ALLOWED,
            err_msg="Biometrics already enabled for this account",
            status_code=400,
        )

    # Create trust token
    trust_token, expires_at = await Authentication.create_trust_token(
        user, data.device_id
    )

    return CustomResponse.success(
        message="Biometrics authentication enabled successfully",
        data={
            "trust_token": trust_token,
            "expires_at": expires_at.isoformat(),
        },
    )


@auth_router.post(
    "/biometrics/login",
    summary="Login with biometrics",
    description="""
        Authenticate using biometrics trust token.
        Returns access and refresh tokens upon successful validation.
    """,
    response={200: TokensResponseSchema},
    throttle=AnonRateThrottle("100/15m"),
)
async def biometrics_login(
    request, data: BiometricsLoginSchema, response: HttpResponse
):
    email = data.email
    trust_token = data.trust_token
    device_id = data.device_id

    # Validate trust token
    user, error_msg = await Authentication.validate_trust_token(
        email, trust_token, device_id
    )

    if not user:
        raise RequestError(
            err_code=ErrorCode.INVALID_TOKEN,
            err_msg=error_msg or "Invalid biometrics credentials",
            status_code=401,
        )

    # Register FCM device and subscribe to global topic if provided
    if data.device_token and data.device_type:
        from apps.notifications.services.fcm import FCMService

        FCMService.register_device(user, data.device_token, data.device_type)

    # Create access and refresh tokens
    access_token, refresh_token = await Authentication.create_tokens_for_user(user)

    # Set HTTP-only cookie for web clients
    if Authentication.is_web_client(request):
        Authentication.set_refresh_token_cookie(response, refresh_token)
        refresh_token = "Set as HTTP-only cookie"

    return CustomResponse.success(
        message="Biometrics login successful",
        data={"access": access_token, "refresh": refresh_token},
    )


@auth_router.post(
    "/biometrics/disable",
    summary="Disable biometrics authentication",
    description="""
        Disable biometrics login and revoke the trust token.
        User will need to re-enable biometrics to use this feature again.
    """,
    response=ResponseSchema,
    auth=AuthUser(),
)
async def disable_biometrics(request):
    user = request.auth

    if not user.biometrics_enabled:
        raise RequestError(
            err_code=ErrorCode.NOT_ALLOWED,
            err_msg="Biometrics not enabled for this account",
            status_code=400,
        )

    # Revoke trust token and disable biometrics
    await Authentication.revoke_trust_token(user)

    return CustomResponse.success(
        message="Biometrics authentication disabled successfully"
    )
