from ninja import Router, Query
from apps.common.responses import CustomResponse
from apps.accounts.auth import AuthUser

from apps.common.schemas import ResponseSchema, PaginationQuerySchema
from apps.notifications.schemas import (
    MarkNotificationsReadSchema,
    NotificationFilterSchema,
    NotificationListResponseSchema,
    NotificationStatsResponseSchema
)
from apps.notifications.services import NotificationService

notification_router = Router(tags=["Notifications"])


# ============= Notification Endpoints =============

@notification_router.get(
    "",
    summary="Get User Notifications",
    response={200: NotificationListResponseSchema},
    auth=AuthUser()
)
async def get_notifications(request, filters: NotificationFilterSchema, page_params: PaginationQuerySchema = Query(...)):
    result = await NotificationService.get_user_notifications(user=request.auth, filters=filters, page_params=page_params)
    return CustomResponse.success("Notifications retrieved successfully", result)

@notification_router.get(
    "/stats",
    summary="Get Notification Statistics",
    response={200: NotificationStatsResponseSchema},
    auth=AuthUser()
)
def get_notification_stats(request):
    stats = NotificationService.get_notification_stats(request.auth)
    return CustomResponse.success("Statistics retrieved successfully", stats)

@notification_router.post(
    "/mark-read",
    summary="Mark Notifications as Read",
    response={200: ResponseSchema},
    auth=AuthUser()
)
async def mark_notifications_read(request, data: MarkNotificationsReadSchema):
    await NotificationService.mark_as_read(request.auth, data)
    return CustomResponse.success("Notifications marked as read")

@notification_router.delete(
    "",
    summary="Delete Notification",
    response={200: dict},
    auth=AuthUser()
)
async def delete_notifications(request, data: MarkNotificationsReadSchema):
    await NotificationService.delete_notifications(user=request.auth, data=data)
    return CustomResponse.success("Notifications deleted successfully")
