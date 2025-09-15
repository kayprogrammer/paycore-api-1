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
    per_page: int
    current_page: int
    last_page: int


class UserDataSchema(BaseSchema):
    name: str = Field(..., alias="full_name")
    avatar: str | None = Field(None, alias="avatar_url")
