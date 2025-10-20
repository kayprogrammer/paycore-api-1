from fcm_django.models import DeviceType
from pydantic import field_validator, Field, EmailStr
from apps.common.schemas import BaseSchema, ResponseSchema


class EmailSchema(BaseSchema):
    email: EmailStr = Field(..., example="johndoe@example.com")


# REQUEST SCHEMAS
class RegisterUserSchema(EmailSchema):
    first_name: str = Field(..., example="John", max_length=50)
    last_name: str = Field(..., example="Doe", max_length=50)
    password: str = Field(..., example="strongpassword", min_length=8)

    @field_validator("first_name", "last_name")
    def no_spaces(cls, v: str):
        if " " in v:
            raise ValueError("No spacing allowed")
        return v


class VerifyOtpSchema(EmailSchema):
    otp: int


class SetNewPasswordSchema(VerifyOtpSchema):
    password: str = Field(..., example="newstrongpassword", min_length=8)


class LoginUserSchema(EmailSchema):
    password: str = Field(..., example="password")


class LoginMfaSchema(EmailSchema):
    otp: int = Field(..., example=123456)
    device_token: str | None = Field(
        None, description="FCM device token for push notifications"
    )
    device_type: DeviceType | None = Field(
        None, description="Device type: ios, android, web"
    )


TOKEN_EXAMPLE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"


class TokenSchema(BaseSchema):
    token: str = Field(
        None, example=TOKEN_EXAMPLE
    )  # use for token refresh and google login (id_token)
    device_token: str | None = Field(
        None, description="FCM device token for push notifications"
    )
    device_type: DeviceType | None = Field(
        None, description="Device type: ios, android, web"
    )


# RESPONSE SCHEMAS
class RegisterResponseSchema(ResponseSchema):
    data: EmailSchema


class TokensResponseDataSchema(BaseSchema):
    access: str = Field(..., example=TOKEN_EXAMPLE)
    refresh: str = Field(..., example=TOKEN_EXAMPLE)


class TokensResponseSchema(ResponseSchema):
    data: TokensResponseDataSchema


# BIOMETRICS SCHEMAS
class BiometricsEnableSchema(BaseSchema):
    device_id: str = Field(..., example="device_12345")
    device_info: str = Field(None, example="iPhone 13 Pro Max")


class BiometricsLoginSchema(BaseSchema):
    email: EmailStr = Field(..., example="johndoe@example.com")
    trust_token: str = Field(..., example="trust_token_abc123")
    device_id: str = Field(..., example="device_12345")
    device_token: str | None = Field(
        None, description="FCM device token for push notifications"
    )
    device_type: str | None = Field(None, description="Device type: ios, android, web")


class BiometricsResponseDataSchema(BaseSchema):
    trust_token: str = Field(..., example="trust_token_abc123")
    expires_at: str = Field(..., example="2024-02-01T12:00:00Z")


class BiometricsResponseSchema(ResponseSchema):
    data: BiometricsResponseDataSchema
