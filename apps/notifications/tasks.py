from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count
from django.conf import settings
from datetime import timedelta
from typing import Dict, Any, List
import logging

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationTasks:
    """Background tasks for notification processing"""

    @staticmethod
    @shared_task(
        name="notifications.send_notification",
        queue="notifications",
        retry_kwargs={"max_retries": 3, "countdown": 60},
    )
    def send_notification(
        user_id: int,
        title: str,
        message: str,
        notification_type: str = "other",
        priority: str = "medium",
        **kwargs,
    ):
        """
        Send notification to a user (in-app, push, and real-time)
        This task is called asynchronously from other parts of the application
        """
        try:
            user = User.objects.get(id=user_id)

            notification = NotificationService.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                related_object_type=kwargs.get("related_object_type"),
                related_object_id=kwargs.get("related_object_id"),
                action_url=kwargs.get("action_url"),
                action_data=kwargs.get("action_data"),
                metadata=kwargs.get("metadata"),
                expires_at=kwargs.get("expires_at"),
                send_push=kwargs.get("send_push", True),
                send_realtime=kwargs.get("send_realtime", True),
            )

            if notification:
                logger.info(f"Notification sent to user {user_id}: {title}")
                return {"status": "success", "notification_id": str(notification.id)}
            else:
                logger.warning(
                    f"Notification not sent to user {user_id} (disabled in preferences)"
                )
                return {"status": "skipped", "reason": "user_preferences"}

        except User.DoesNotExist:
            logger.error(f"User {user_id} not found")
            return {"status": "failed", "error": "user_not_found"}
        except Exception as e:
            logger.error(f"Error sending notification to user {user_id}: {str(e)}")
            raise

    @staticmethod
    @shared_task(
        name="notifications.send_bulk_notification",
        queue="notifications",
        retry_kwargs={"max_retries": 2, "countdown": 120},
    )
    def send_bulk_notification(
        user_ids: List[int],
        title: str,
        message: str,
        notification_type: str = "system",
        priority: str = "medium",
        **kwargs,
    ):
        """
        Send notification to multiple users efficiently using bulk operations
        Uses bulk_create for notifications and batch sending for push/websocket
        """
        try:
            users = User.objects.filter(id__in=user_ids, is_active=True)

            if not users.exists():
                logger.warning(f"No active users found from {len(user_ids)} user IDs")
                return {
                    "status": "completed",
                    "created_count": 0,
                    "push_success": 0,
                    "push_failure": 0,
                    "websocket_sent": 0,
                }

            # Use bulk notification service
            result = NotificationService.bulk_create_notifications(
                users=users,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                related_object_type=kwargs.get("related_object_type"),
                related_object_id=kwargs.get("related_object_id"),
                action_url=kwargs.get("action_url"),
                action_data=kwargs.get("action_data"),
                metadata=kwargs.get("metadata"),
                expires_at=kwargs.get("expires_at"),
                send_push=kwargs.get("send_push", True),
                send_realtime=kwargs.get("send_realtime", True),
            )

            logger.info(
                f"Bulk notification complete: {result['created_count']} created, "
                f"Push: {result['push_results'].get('success', 0)} success / {result['push_results'].get('failure', 0)} failed, "
                f"WebSocket: {result['websocket_sent']} sent"
            )

            return {
                "status": "completed",
                "created_count": result["created_count"],
                "push_success": result["push_results"].get("success", 0),
                "push_failure": result["push_results"].get("failure", 0),
                "websocket_sent": result["websocket_sent"],
            }

        except Exception as e:
            logger.error(f"Error in bulk notification: {str(e)}")
            raise


class NotificationCleanupTasks:
    """Tasks for cleaning up old notifications"""

    @staticmethod
    @shared_task(name="notifications.cleanup_old_notifications", queue="maintenance")
    def cleanup_old_notifications():
        """
        Delete old read notifications based on retention policy
        Runs daily at 2 AM
        """
        try:
            retention_days = getattr(settings, "NOTIFICATION_RETENTION_DAYS", 90)
            cutoff_date = timezone.now() - timedelta(days=retention_days)

            # Delete old read notifications
            deleted_count, _ = Notification.objects.filter(
                is_read=True, read_at__lt=cutoff_date
            ).delete()

            logger.info(f"Cleaned up {deleted_count} old notifications")

            return {"status": "success", "deleted_count": deleted_count}

        except Exception as e:
            logger.error(f"Error cleaning up notifications: {str(e)}")
            raise

    @staticmethod
    @shared_task(
        name="notifications.cleanup_expired_notifications", queue="maintenance"
    )
    def cleanup_expired_notifications():
        try:
            deleted_count, _ = Notification.objects.filter(
                expires_at__lte=timezone.now()
            ).delete()

            logger.info(f"Deleted {deleted_count} expired notifications")

            return {"status": "success", "deleted_count": deleted_count}

        except Exception as e:
            logger.error(f"Error deleting expired notifications: {str(e)}")
            raise


class NotificationStatsTask:
    """Tasks for notification statistics and analytics"""

    @staticmethod
    @shared_task(name="notifications.generate_daily_stats", queue="analytics")
    def generate_daily_stats():
        """
        Generate daily notification statistics
        Runs daily at midnight
        """
        try:
            yesterday = timezone.now() - timedelta(days=1)
            start_of_day = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = yesterday.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )

            # Count notifications sent yesterday
            notifications = Notification.objects.filter(
                created_at__range=[start_of_day, end_of_day]
            )

            total_sent = notifications.count()
            push_sent = notifications.filter(sent_via_push=True).count()
            websocket_sent = notifications.filter(sent_via_websocket=True).count()
            read_count = notifications.filter(is_read=True).count()

            # Count by type
            by_type = dict(
                notifications.values("notification_type")
                .annotate(count=Count("id"))
                .values_list("notification_type", "count")
            )

            # Count by priority
            by_priority = dict(
                notifications.values("priority")
                .annotate(count=Count("id"))
                .values_list("priority", "count")
            )

            stats = {
                "date": yesterday.date().isoformat(),
                "total_sent": total_sent,
                "push_sent": push_sent,
                "websocket_sent": websocket_sent,
                "read_count": read_count,
                "read_rate": (read_count / total_sent * 100) if total_sent > 0 else 0,
                "by_type": by_type,
                "by_priority": by_priority,
            }

            logger.info(
                f"Daily notification stats generated: {total_sent} notifications sent"
            )

            # You can save these stats to a model or send to an analytics service
            return stats

        except Exception as e:
            logger.error(f"Error generating daily stats: {str(e)}")
            raise
