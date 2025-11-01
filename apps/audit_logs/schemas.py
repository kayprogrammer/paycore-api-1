from ninja import FilterSchema, ModelSchema
from pydantic import Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from django.db.models import Q

from apps.audit_logs.models import AuditLog, EventCategory, EventType, SeverityLevel
from apps.common.schemas import BaseSchema, PaginatedResponseDataSchema, ResponseSchema


class AuditLogFilterSchema(FilterSchema):
    event_type: Optional[str] = Field(default=None, description="Filter by event type")
    event_category: Optional[str] = Field(
        default=None, description="Filter by event category"
    )
    severity: Optional[str] = Field(
        default=None, description="Filter by severity level"
    )
    user_id: Optional[UUID] = Field(default=None, description="Filter by user ID")
    resource_type: Optional[str] = Field(
        default=None, description="Filter by resource type"
    )
    resource_id: Optional[str] = Field(
        default=None, description="Filter by resource ID"
    )
    ip_address: Optional[str] = Field(default=None, description="Filter by IP address")
    start_date: Optional[datetime] = Field(
        default=None, description="Filter by start date"
    )
    end_date: Optional[datetime] = Field(default=None, description="Filter by end date")
    is_compliance_event: Optional[bool] = Field(
        default=None, description="Filter compliance events"
    )
    is_suspicious: Optional[bool] = Field(
        default=None, description="Filter suspicious activities"
    )

    def filter_is_suspicious(self, value: bool) -> Q:
        return (
            (
                Q(
                    event_type__in=[
                        EventType.SUSPICIOUS_ACTIVITY,
                        EventType.FAILED_LOGIN_ATTEMPTS,
                        EventType.IP_BLOCKED,
                    ]
                )
                | Q(severity=SeverityLevel.CRITICAL)
            )
            if value
            else Q()
        )


class AuditLogSchema(ModelSchema):
    class Meta:
        model = AuditLog
        exclude = ["updated_at", "deleted_at"]


class AuditLogPaginatedResponseDataSchema(PaginatedResponseDataSchema):
    logs: List[AuditLogSchema] = Field(
        ..., description="List of audit logs", alias="items"
    )


class AuditLogStatsSchema(BaseSchema):
    total_logs: int
    logs_by_category: Dict[str, int]
    logs_by_severity: Dict[str, int]
    suspicious_activities: int
    compliance_events: int
    recent_activities: List[AuditLogSchema]


class AuditLogListResponseSchema(ResponseSchema):
    data: AuditLogPaginatedResponseDataSchema


class AuditLogDetailResponseSchema(ResponseSchema):
    data: AuditLogSchema


class AuditLogStatsResponseSchema(ResponseSchema):
    data: AuditLogStatsSchema
