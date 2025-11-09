from typing import Optional, Dict, Any, List, Union
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, QuerySet
import logging

from apps.notifications.models import (
    Notification,
    NotificationTemplate,
    NotificationType,
    NotificationPriority,
)
from apps.common.paginators import Paginator
from apps.notifications.schemas import MarkNotificationsReadSchema
from apps.notifications.services.fcm import FCMService
from apps.notifications.services.websocket import WebSocketService

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing in-app notifications"""

    @staticmethod
    def create_notification(
        user: User,
        title: str,
        message: str,
        notification_type: str = NotificationType.OTHER,
        priority: str = NotificationPriority.MEDIUM,
        related_object_type: str = None,
        related_object_id: str = None,
        action_url: str = None,
        action_data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
        expires_at: timezone.datetime = None,
        send_push: bool = True,
        send_realtime: bool = True,
    ) -> Optional[Notification]:
        """
        Create a notification for a user
        Optionally sends push notification and real-time WebSocket notification
        """
        try:
            if not user.in_app_enabled:
                logger.info(
                    f"Skipping in-app notification for user {user.id} - disabled in preferences"
                )
                return None

            notification = Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                related_object_type=related_object_type or "",
                related_object_id=related_object_id or "",
                action_url=action_url or "",
                action_data=action_data or {},
                metadata=metadata or {},
                expires_at=expires_at,
            )
            logger.info(
                f"✅ Created notification {notification.id} for user {user.id}: {title} (type={notification_type})"
            )

            update_fields = ["updated_at"]
            # Send push notification if enabled
            if send_push and user.push_enabled:
                FCMService.send_to_user(
                    user,
                    title,
                    message,
                    {
                        "notification_id": str(notification.id),
                        "notification_type": notification_type,
                        "action_url": action_url or "",
                        **(action_data or {}),
                    },
                )
                notification.sent_via_push = True
                notification.push_sent_at = timezone.now()
                update_fields.extend(["sent_via_push", "push_sent_at"])

            # Send real-time WebSocket notification
            if send_realtime:
                WebSocketService.send_notification(user.id, notification)
                notification.sent_via_websocket = True
                notification.websocket_sent_at = timezone.now()
                update_fields.extend(["sent_via_websocket", "websocket_sent_at"])

            notification.save(update_fields=update_fields)
            logger.info(f"Notification created for user {user.id}: {title}")
            return notification

        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            return None

    @staticmethod
    def create_from_template(
        user: User,
        template_name: str,
        context: Dict[str, Any],
        send_push: bool = True,
        send_realtime: bool = True,
    ) -> Optional[Notification]:
        try:
            template = NotificationTemplate.objects.get_or_none(
                name=template_name, is_active=True
            )

            if not template:
                logger.error(f"Template not found: {template_name}")
                return None

            rendered = template.render(context)

            return NotificationService.create_notification(
                user=user,
                title=rendered["title"],
                message=rendered["message"],
                notification_type=template.notification_type,
                priority=template.priority,
                action_url=rendered.get("action_url", ""),
                send_push=send_push,
                send_realtime=send_realtime,
            )
        except Exception as e:
            logger.error(f"Error creating notification from template: {str(e)}")
            return None

    @staticmethod
    async def get_user_notifications(
        user: User, filters, page_params
    ) -> Dict[str, Any]:
        query = Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        notifications = Notification.objects.filter(user=user).filter(query)
        notifications = filters.filter(notifications)
        unread_count = await Notification.objects.filter(
            user=user, is_read=False
        ).acount()

        paginated_data = await Paginator.paginate_queryset(
            notifications.order_by("-created_at"), page_params.page, page_params.limit
        )
        paginated_data["unread_count"] = unread_count
        return paginated_data

    @staticmethod
    async def mark_as_read(user: User, payload: MarkNotificationsReadSchema) -> int:
        notification_ids = payload.notification_ids
        filters = {} if len(notification_ids) < 1 else {"id__in": notification_ids}
        return await Notification.objects.filter(
            user=user, is_read=False, **filters
        ).aupdate(is_read=True, read_at=timezone.now())

    @staticmethod
    async def delete_notifications(
        user: User, payload: MarkNotificationsReadSchema
    ) -> bool:
        notification_ids = payload.notification_ids
        filters = {} if len(notification_ids) < 1 else {"id__in": notification_ids}
        await Notification.objects.filter(user=user, **filters).adelete()

    @staticmethod
    async def get_notification_stats(user: User) -> Dict[str, Any]:
        notifications = Notification.objects.filter(user=user)

        # Count by type
        by_type = dict(
            await sync_to_async(list)(
                notifications.values("notification_type")
                .annotate(count=Count("id"))
                .values_list("notification_type", "count")
            )
        )

        # Count by priority
        by_priority = dict(
            await sync_to_async(list)(
                notifications.values("priority")
                .annotate(count=Count("id"))
                .values_list("priority", "count")
            )
        )

        return {
            "total_count": await notifications.acount(),
            "unread_count": await notifications.filter(is_read=False).acount(),
            "by_type": by_type,
            "by_priority": by_priority,
        }

    @staticmethod
    def bulk_create_notifications(
        users: Union[List[User], QuerySet],
        title: str,
        message: str,
        notification_type: str = NotificationType.OTHER,
        priority: str = NotificationPriority.MEDIUM,
        related_object_type: str = None,
        related_object_id: str = None,
        action_url: str = None,
        action_data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
        expires_at: timezone.datetime = None,
        send_push: bool = True,
        send_realtime: bool = True,
    ) -> Dict[str, Any]:
        """
        Bulk create notifications for multiple users
        For bulk notifications, all users receive notifications regardless of preferences
        Use this for important announcements, system messages, etc.

        Returns:
            Dict containing:
                - created_count: number of notifications created
                - push_results: FCM push notification results
                - websocket_sent: number of WebSocket notifications sent
        """
        try:
            # Convert QuerySet to list if needed
            if isinstance(users, QuerySet):
                users_list = list(users)
            else:
                users_list = users

            if not users_list:
                logger.warning("No users provided for bulk notification")
                return {
                    "created_count": 0,
                    "push_results": {"success": 0, "failure": 0},
                    "websocket_sent": 0,
                }

            # Prepare notification data once
            notification_data = {
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "priority": priority,
                "related_object_type": related_object_type or "",
                "related_object_id": related_object_id or "",
                "action_url": action_url or "",
                "action_data": action_data or {},
                "metadata": metadata or {},
                "expires_at": expires_at,
            }

            # Bulk create all notifications in one go - single list comprehension
            now = timezone.now()
            created_notifications = Notification.objects.bulk_create(
                [Notification(user=user, **notification_data) for user in users_list]
            )
            created_count = len(created_notifications)

            logger.info(
                f"Bulk created {created_count} notifications for {len(users_list)} users"
            )

            # Prepare updates dict - we'll update everything in one query at the end
            updates = {}

            # Send push notifications
            push_results = {"success": 0, "failure": 0}
            if send_push:
                push_results = WebSocketService.bulk_send_push(
                    users=users_list,
                    title=title,
                    message=message,
                    data={
                        "notification_type": notification_type,
                        "action_url": action_url or "",
                        **(action_data or {}),
                    },
                )

                if push_results.get("success", 0) > 0:
                    updates["sent_via_push"] = True
                    updates["push_sent_at"] = now

            websocket_sent = 0
            if send_realtime:
                websocket_sent = WebSocketService.bulk_send_notifications(
                    notifications=created_notifications
                )

                if websocket_sent > 0:
                    updates["sent_via_websocket"] = True
                    updates["websocket_sent_at"] = now

            if updates:
                notification_ids = [n.id for n in created_notifications]
                Notification.objects.filter(id__in=notification_ids).update(**updates)

            return {
                "created_count": created_count,
                "push_results": push_results,
                "websocket_sent": websocket_sent,
            }

        except Exception as e:
            logger.error(f"Error in bulk_create_notifications: {str(e)}")
            return {
                "created_count": 0,
                "push_results": {"success": 0, "failure": 0},
                "websocket_sent": 0,
                "error": str(e),
            }
