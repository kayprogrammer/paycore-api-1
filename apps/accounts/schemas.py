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


TOKEN_EXAMPLE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"


class TokenSchema(BaseSchema):
    token: str = Field(
        ..., example=TOKEN_EXAMPLE
    )  # use for token refresh and google login (id_token)


# RESPONSE SCHEMAS
class RegisterResponseSchema(ResponseSchema):
    data: EmailSchema


class TokensResponseDataSchema(BaseSchema):
    access: str = Field(..., example=TOKEN_EXAMPLE)
    refresh: str = Field(..., example=TOKEN_EXAMPLE)


class TokensResponseSchema(ResponseSchema):
    data: TokensResponseDataSchema
