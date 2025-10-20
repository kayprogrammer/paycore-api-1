from datetime import date
from uuid import UUID
import uuid
from ninja import Field, FilterSchema, ModelSchema
from pydantic import field_validator
from typing import List, Optional
from apps.accounts.models import User
from apps.common.schemas import BaseSchema, ResponseSchema
from .models import Country


# USER SCHEMAS
class UserUpdateSchema(BaseSchema):
    first_name: str = Field(..., example="John", max_length=50)
    last_name: str = Field(..., example="Doe", max_length=50)
    dob: date = Field(..., example="2000-12-12")
    bio: str = Field(
        ..., example="Senior Backend Engineer | Django Ninja", max_length=200
    )
    push_enabled: bool = Field(..., example=True)
    in_app_enabled: bool = Field(..., example=True)
    email_enabled: bool = Field(..., example=True)

    @field_validator("first_name", "last_name")
    def no_spaces(cls, v: str):
        if " " in v:
            raise ValueError("No spacing allowed")
        return v


class UserSchema(ModelSchema):
    avatar_url: str | None

    class Meta:
        model = User
        fields = ["first_name", "last_name", "bio", "dob"]


class UserResponseSchema(ResponseSchema):
    data: UserSchema


# ------------------------------------------------------


# COUNTRIES SCHEMAS
class CountrySchema(ModelSchema):
    class Meta:
        model = Country
        fields = ["id", "name", "code", "currency"]


class CountryListResponseSchema(ResponseSchema):
    data: List[CountrySchema]


class CountryFilterSchema(FilterSchema):
    search: Optional[str] = Field(
        None,
        q=[
            "name__icontains",
            "code__icontains",
            "currency__icontains",
        ],
    )
