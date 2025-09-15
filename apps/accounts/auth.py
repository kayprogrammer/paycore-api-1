from django.conf import settings
from django.utils.crypto import get_random_string
from apps.accounts.emails import EmailUtil
from apps.accounts.models import User
from datetime import UTC, datetime, timedelta
from apps.common.exceptions import ErrorCode, RequestError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from ninja.security import HttpBearer
import jwt, random, string

ALGORITHM = "HS256"


class Authentication:
    # generate random string
    def get_random(length: int):
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    # generate access token based and encode user's id
    def create_access_token(user_id):
        expire = datetime.now(UTC) + timedelta(
            minutes=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode = {"exp": expire, "user_id": str(user_id)}
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    # generate random refresh token
    def create_refresh_token():
        expire = datetime.now(UTC) + timedelta(
            minutes=int(settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        )
        return jwt.encode(
            {"exp": expire, "data": Authentication.get_random(10)},
            settings.SECRET_KEY,
            algorithm=ALGORITHM,
        )

    # decode access token from header
    def decode_jwt(token: str):
        try:
            decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except:
            decoded = False
        return decoded

    async def retrieve_user_from_token(token: str):
        decoded = Authentication.decode_jwt(token)
        if not decoded:
            return None
        user = await User.objects.aget_or_none(id=decoded["user_id"], access=token)
        return user

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
