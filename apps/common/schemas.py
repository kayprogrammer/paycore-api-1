from ninja import Field, Schema
from pydantic import ConfigDict


class BaseSchema(Schema):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ResponseSchema(BaseSchema):
    status: str = "success"
    message: str


class ErrorResponseSchema(ResponseSchema):
    status: str = "failure"


class PaginatedResponseDataSchema(BaseSchema):
    total: int
    limit: int
    page: int
    total_pages: int


class UserDataSchema(BaseSchema):
    name: str = Field(..., alias="full_name")
    avatar: str | None = Field(None, alias="avatar_url")


class PaginationQuerySchema(BaseSchema):
    page: int = Field(1, ge=1, description="Page number for pagination")
    limit: int = Field(50, ge=1, le=100, description="Number of items per page")
