from django.conf import settings
from django.utils.crypto import get_random_string
from apps.accounts.emails import EmailUtil
from apps.accounts.models import User
from datetime import UTC, datetime, timedelta
from apps.common.exceptions import ErrorCode, RequestError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from ninja.security import HttpBearer
import jwt, secrets

ALGORITHM = "HS256"


class Authentication:
    # generate cryptographically secure random string
    @staticmethod
    def get_random(length: int):
        return secrets.token_urlsafe(length)

    # generate access token and encode user's id with additional security claims
    @staticmethod
    def create_access_token(user_id, jti=None):
        if not jti:
            jti = secrets.token_urlsafe(16)
        expire = datetime.now(UTC) + timedelta(
            minutes=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode = {
            "exp": expire,
            "iat": datetime.now(UTC),
            "user_id": str(user_id),
            "jti": jti,
            "type": "access",
        }
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    # generate cryptographically secure refresh token
    @staticmethod
    def create_refresh_token():
        expire = datetime.now(UTC) + timedelta(
            minutes=int(settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        )
        jti = secrets.token_urlsafe(16)
        return jwt.encode(
            {
                "exp": expire,
                "iat": datetime.now(UTC),
                "jti": jti,
                "type": "refresh",
                "data": Authentication.get_random(10),
            },
            settings.SECRET_KEY,
            algorithm=ALGORITHM,
        )

    # create token pair and invalidate previous tokens for security
    @staticmethod
    async def create_tokens_for_user(user):
        access_token = Authentication.create_access_token(user.id)
        refresh_token = Authentication.create_refresh_token()

        user.access, user.refresh = access_token, refresh_token
        await user.asave()
        return access_token, refresh_token

    # decode and validate JWT token with enhanced security
    @staticmethod
    def decode_jwt(token: str, token_type: str = "access"):
        try:
            decoded = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[ALGORITHM],
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_signature": True,
                },
            )
            # Validate token type
            if decoded.get("type") != token_type:
                return None
            return decoded
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None

    @staticmethod
    async def retrieve_user_from_token(token: str):
        decoded = Authentication.decode_jwt(token, "access")
        if not decoded:
            return None

        # Verify token is still valid in user model (prevents token reuse after logout)
        user = await User.objects.aget_or_none(
            id=decoded["user_id"], access=token, is_active=True
        )
        return user

    # rotate refresh token for enhanced security
    @staticmethod
    async def rotate_refresh_token(refresh_token: str):
        decoded = Authentication.decode_jwt(refresh_token, "refresh")
        if not decoded:
            return None, None, None

        user = await User.objects.aget_or_none(refresh=refresh_token, is_active=True)
        if not user:
            return None, None, None

        # Create new token pair
        new_access, new_refresh = await Authentication.create_tokens_for_user(user)
        return user, new_access, new_refresh

    # invalidate user tokens (for logout)
    @staticmethod
    async def invalidate_user_tokens(user):
        user.access, user.refresh = None, None
        await user.asave()

    # generate trust token for biometrics authentication
    @staticmethod
    async def create_trust_token(user, device_id):
        expire = datetime.now(UTC) + timedelta(
            days=settings.TRUST_TOKEN_EXPIRE_DAYS
        )
        jti = secrets.token_urlsafe(32)
        trust_data = {
            "exp": expire,
            "iat": datetime.now(UTC),
            "user_id": str(user.id),
            "device_id": device_id,
            "jti": jti,
            "type": "trust",
        }
        trust_token = jwt.encode(trust_data, settings.SECRET_KEY, algorithm=ALGORITHM)
        
        user.trust_token = trust_token
        user.trust_token_expires_at = expire
        user.biometrics_enabled = True
        await user.asave()
        
        return trust_token, expire

    # validate trust token for biometrics login
    @staticmethod
    async def validate_trust_token(email, trust_token, device_id):
        try:
            decoded = jwt.decode(
                trust_token,
                settings.SECRET_KEY,
                algorithms=[ALGORITHM],
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_signature": True,
                },
            )
            
            if decoded.get("type") != "trust":
                return None, "Invalid trust token type"
                
            if decoded.get("device_id") != device_id:
                return None, "Device ID mismatch"
                
            user = await User.objects.aget_or_none(
                email=email,
                id=decoded["user_id"],
                trust_token=trust_token,
                biometrics_enabled=True,
                is_active=True
            )
            
            if not user:
                return None, "Invalid trust token or user not found"
                
            if user.is_trust_token_expired():
                return None, "Trust token has expired"
                
            return user, None
            
        except jwt.ExpiredSignatureError:
            return None, "Trust token has expired"
        except jwt.InvalidTokenError:
            return None, "Invalid trust token"
        except Exception:
            return None, "Trust token validation failed"

    # revoke trust token (disable biometrics)
    @staticmethod
    async def revoke_trust_token(user):
        user.trust_token, user.trust_token_expires_at, user.biometrics_enabled = None, None, False
        await user.asave()

    # detect client type for proper token handling
    @staticmethod
    def is_web_client(request):
        client_type = getattr(request, "client_type", None)

        # Check if client explicitly specified web
        if client_type and client_type.lower() == "web":
            return True
        return False

    # set secure HTTP-only cookie for web clients
    @staticmethod
    def set_refresh_token_cookie(response, refresh_token, max_age=None):
        if not max_age:
            max_age = int(settings.REFRESH_TOKEN_EXPIRE_MINUTES) * 60

        response.set_cookie(
            "refresh_token",
            refresh_token,
            max_age=max_age,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Strict",  # CSRF protection
            domain=None,
        )
        return response

    # clear refresh token cookie
    @staticmethod
    def clear_refresh_token_cookie(response):
        response.delete_cookie("refresh_token")
        return response

    def validate_google_token(auth_token):
        """
        validate method Queries the Google oAUTH2 api to fetch the user info
        """
        try:
            idinfo = id_token.verify_oauth2_token(auth_token, google_requests.Request())
            if not "sub" in idinfo.keys():
                return None, ErrorCode.INVALID_TOKEN, "Invalid Google ID Token"
            if idinfo["aud"] != settings.GOOGLE_CLIENT_ID:
                return None, ErrorCode.INVALID_CLIENT_ID, "Invalid Client ID"
            return idinfo, None, None
        except:
            return None, ErrorCode.INVALID_TOKEN, "Invalid Auth Token"

    async def store_google_user(email: str, name: str, avatar: str = None):
        user = await User.objects.aget_or_none(email=email)
        if not user:
            name = name.split()
            first_name = name[0]
            last_name = name[1]
            user = await User.objects.acreate_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=get_random_string(12),
                social_avatar=avatar,
                is_email_verified=True,
            )
            EmailUtil.welcome_email(user)
        return user


class AuthUser(HttpBearer):
    async def authenticate(self, request, token):
        if not token:
            raise RequestError(
                err_code=ErrorCode.INVALID_AUTH,
                err_msg="Auth Bearer not provided!",
                status_code=401,
            )

        user = await Authentication.retrieve_user_from_token(token)
        if not user:
            raise RequestError(
                err_code=ErrorCode.INVALID_TOKEN,
                err_msg="Auth Token is Invalid or Expired!",
                status_code=401,
            )
        return user


class AuthAdmin(AuthUser):
    async def authenticate(self, request, token):
        user = await super().authenticate(request, token)
        if not user.is_staff:
            raise RequestError(
                err_code=ErrorCode.UNAUTHORIZED_USER,
                err_msg="Only admins are authorized to access this resource",
                status_code=403,
            )
        return user