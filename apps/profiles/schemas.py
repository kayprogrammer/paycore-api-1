from datetime import date
from uuid import UUID
import uuid
from ninja import Field, FilterSchema, ModelSchema
from pydantic import field_validator
from typing import List, Optional
from apps.accounts.models import User
from apps.common.schemas import BaseSchema, ResponseSchema
from .models import KYC, Country, DocumentType, KYCStatus


# USER SCHEMAS
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


# ------------------------------------------------------


# KYC SCHEMAS
class KYCSubmissionSchema(BaseSchema):
    first_name: str = Field(..., example="John", max_length=100)
    last_name: str = Field(..., example="Doe", max_length=100)
    date_of_birth: date = Field(..., example="1990-01-15")
    nationality: str = Field(..., example="American", max_length=100)
    phone_number: Optional[str] = Field(None, example="+1234567890", max_length=20)

    address_line1: str = Field(..., example="123 Main Street", max_length=255)
    address_line2: Optional[str] = Field(None, example="Apt 4B", max_length=255)
    city: str = Field(..., example="New York", max_length=100)
    state: Optional[str] = Field(None, example="NY", max_length=100)
    country_id: UUID = Field(..., example=uuid.uuid4())
    postal_code: Optional[str] = Field(None, example="10001", max_length=20)

    document_type: DocumentType = Field(..., example=DocumentType.PASSPORT)
    document_number: str = Field(..., example="A12345678", max_length=100)
    document_expiry_date: Optional[date] = Field(None, example="2030-12-31")

    is_politically_exposed: bool = Field(False, example=False)

    @field_validator("first_name", "last_name")
    def no_spaces(cls, v: str):
        if " " in v:
            raise ValueError("No spacing allowed")
        return v


class KYCDetailSchema(ModelSchema):
    class Meta:
        model = KYC
        fields = [
            "id",
            "first_name",
            "last_name",
            "date_of_birth",
            "nationality",
            "status",
            "created_at",
            "reviewed_at",
        ]


class KYCStatusUpdateSchema(BaseSchema):
    status: KYCStatus = Field(..., example=KYCStatus.APPROVED)
    notes: Optional[str] = Field(None, example="All documents verified successfully")
    rejection_reason: Optional[str] = Field(None, example="Document expired")

class KycFilterSchema(FilterSchema):
    status: Optional[KYCStatus] = Field(None, q="status")
    
class KYCListResponseSchema(ResponseSchema):
    data: List[KYCDetailSchema]


class KYCSingleResponseSchema(ResponseSchema):
    data: KYCDetailSchema


# ------------------------------------------------------
