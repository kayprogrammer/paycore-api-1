from datetime import date
from ninja import ModelSchema
from pydantic import field_validator, Field, EmailStr
from apps.accounts.models import User
from apps.common.schemas import BaseSchema, ResponseSchema
import phonenumbers


class EmailSchema(BaseSchema):
    email: EmailStr = Field(..., example="johndoe@example.com")


# REQUEST SCHEMAS
class RegisterUserSchema(EmailSchema):
    first_name: str = Field(..., example="John", max_length=50)
    last_name: str = Field(..., example="Doe", max_length=50)
    phone: str = Field(..., example="+2348112345678")
    password: str = Field(..., example="strongpassword", min_length=8)

    @field_validator("first_name", "last_name")
    def no_spaces(cls, v: str):
        if " " in v:
            raise ValueError("No spacing allowed")
        return v

    @field_validator("phone")
    def validate_phone_number(cls, v):
        try:
            parsed = phonenumbers.parse(v, None)
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number format")
        except Exception:
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class VerifyOtpSchema(EmailSchema):
    otp: int


class SetNewPasswordSchema(VerifyOtpSchema):
    password: str = Field(..., example="newstrongpassword", min_length=8)


class LoginUserSchema(EmailSchema):
    password: str = Field(..., example="password")


TOKEN_EXAMPLE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"


class TokenSchema(BaseSchema):
    token: str = Field(
        ..., example=TOKEN_EXAMPLE
    )  # use for token refresh and google login (id_token)


class UserUpdateSchema(BaseSchema):
    first_name: str = Field(..., example="John", max_length=50)
    last_name: str = Field(..., example="Doe", max_length=50)
    dob: date = Field(..., example="2000-12-12")
    bio: str = Field(
        ..., example="Senior Backend Engineer | Django Ninja", max_length=200
    )

    @field_validator("first_name", "last_name")
    def no_spaces(cls, v: str):
        if " " in v:
            raise ValueError("No spacing allowed")
        return v


# RESPONSE SCHEMAS
class RegisterResponseSchema(ResponseSchema):
    data: EmailSchema


class TokensResponseDataSchema(BaseSchema):
    access: str = Field(..., example=TOKEN_EXAMPLE)
    refresh: str = Field(..., example=TOKEN_EXAMPLE)


class TokensResponseSchema(ResponseSchema):
    data: TokensResponseDataSchema


class UserSchema(ModelSchema):
    avatar_url: str | None

    class Meta:
        model = User
        fields = ["first_name", "last_name", "bio", "dob"]


class UserResponseSchema(ResponseSchema):
    data: UserSchema
