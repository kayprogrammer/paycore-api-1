from ninja import FilterSchema, ModelSchema, Schema
from pydantic import Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from fcm_django.models import DeviceType
from apps.notifications.models import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from apps.common.schemas import BaseSchema, PaginatedResponseDataSchema, ResponseSchema


# Request Schemas
class RegisterDeviceTokenSchema(BaseSchema):
    fcm_token: str = Field(
        ..., min_length=1, description="Firebase Cloud Messaging token"
    )
    device_type: DeviceType = Field(..., description="Device type: ios, android, web")


class NotificationPreferenceUpdateSchema(BaseSchema):
    push_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None


class MarkNotificationsReadSchema(BaseSchema):
    notification_ids: List[UUID] = Field(
        [], min_length=1, description="List of notification UUIDs"
    )
    all: Optional[bool] = False


class NotificationFilterSchema(FilterSchema):
    notification_type: Optional[NotificationType] = None
    is_read: Optional[bool] = None
    priority: Optional[NotificationPriority] = None


# Response Schemas
class NotificationSchema(ModelSchema):
    class Meta:
        model = Notification
        exclude = ["deleted_at"]


class NotificationListResponseDataSchema(PaginatedResponseDataSchema):
    unread_count: int
    notifications: List[NotificationSchema] = Field(
        ..., description="List of notifications", alias="items"
    )


class NotificationListResponseSchema(ResponseSchema):
    data: NotificationListResponseDataSchema


class NotificationPreferenceSchema(Schema):
    push_enabled: bool
    in_app_enabled: bool
    email_enabled: bool


class NotificationStatsSchema(Schema):
    total_count: int
    unread_count: int
    by_type: Dict[str, int]
    by_priority: Dict[str, int]


class NotificationStatsResponseSchema(ResponseSchema):
    data: NotificationStatsSchema
