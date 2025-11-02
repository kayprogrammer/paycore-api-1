from asgiref.sync import sync_to_async
from ninja import Router, Query
from django.db.models import Q
from uuid import UUID

from apps.accounts.auth import AuthAdmin, AuthUser
from apps.common.responses import CustomResponse
from apps.common.schemas import PaginationQuerySchema
from apps.common.paginators import Paginator

from apps.audit_logs.models import AuditLog, EventType, EventCategory, SeverityLevel
from apps.audit_logs.schemas import (
    AuditLogFilterSchema,
    AuditLogListResponseSchema,
    AuditLogDetailResponseSchema,
    AuditLogStatsResponseSchema,
    AuditLogSchema,
    AuditLogStatsSchema,
)
from apps.common.exceptions import NotFoundError, RequestError, ErrorCode

audit_router = Router(tags=["Audit Logs (3)"])


@audit_router.get(
    "",
    summary="Get Audit Logs",
    description="""
        Retrieve audit logs with filtering and pagination. 
        Admin users can see all logs, regular users only see their own.
    """,
    response={200: AuditLogListResponseSchema},
    auth=AuthUser(),
)
async def get_audit_logs(
    request,
    filters: AuditLogFilterSchema = Query(...),
    pagination: PaginationQuerySchema = Query(...),
):
    user = request.auth

    queryset = AuditLog.objects.all()

    if not user.is_staff:
        queryset = queryset.filter(user=user)

    queryset = filters.filter(queryset)
    paginated_data = await Paginator.paginate_queryset(
        queryset, pagination.page, pagination.limit
    )
    return CustomResponse.success(
        message="Audit logs retrieved successfully", data=paginated_data
    )


@audit_router.get(
    "/log/{log_id}",
    summary="Get Audit Log Detail",
    description="Get detailed information about a specific audit log entry",
    response={200: AuditLogDetailResponseSchema},
    auth=AuthUser(),
)
async def get_audit_log_detail(request, log_id: UUID):
    user = request.auth
    log = await AuditLog.objects.aget_or_none(id=log_id)

    if not log:
        raise NotFoundError("Audit log not found")

    # Non-admin users can only see their own logs
    if not user.is_staff and log.user_id != user.id:
        raise RequestError(
            err_code=ErrorCode.NOT_ALLOWED,
            err_msg="You don't have permission to view this log",
            status_code=403,
        )

    return CustomResponse.success(
        message="Audit log retrieved successfully", data=AuditLogSchema.from_orm(log)
    )


@audit_router.get(
    "/stats/overview",
    summary="Get Audit Log Statistics",
    description="Get overview statistics of audit logs. Admin only.",
    response={200: AuditLogStatsResponseSchema},
    auth=AuthAdmin(),
)
async def get_audit_stats(request):
    user = request.auth
    # Get total logs
    total_logs = await AuditLog.objects.acount()

    # Logs by category
    category_stats = {}
    for category in EventCategory:
        count = await AuditLog.objects.filter(event_category=category.value).acount()
        if count > 0:
            category_stats[category.label] = count

    # Logs by severity
    severity_stats = {}
    for severity in SeverityLevel:
        count = await AuditLog.objects.filter(severity=severity.value).acount()
        if count > 0:
            severity_stats[severity.label] = count

    # Suspicious activities count
    suspicious_count = await AuditLog.objects.filter(
        Q(
            event_type__in=[
                EventType.SUSPICIOUS_ACTIVITY,
                EventType.FAILED_LOGIN_ATTEMPTS,
                EventType.IP_BLOCKED,
            ]
        )
        | Q(severity=SeverityLevel.CRITICAL)
    ).acount()

    # Compliance events count
    compliance_count = await AuditLog.objects.filter(is_compliance_event=True).acount()

    # Recent activities (last 10)
    recent_logs = await sync_to_async(list)(AuditLog.objects.all()[:10])
    return CustomResponse.success(
        message="Statistics retrieved successfully",
        data=AuditLogStatsSchema(
            total_logs=total_logs,
            logs_by_category=category_stats,
            logs_by_severity=severity_stats,
            suspicious_activities=suspicious_count,
            compliance_events=compliance_count,
            recent_activities=recent_logs,
        ),
    )
