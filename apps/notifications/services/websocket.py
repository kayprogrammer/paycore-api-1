from typing import Dict, Any, List, Union
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from apps.notifications.services.fcm import FCMService
from fcm_django.models import FCMDevice
import logging

from apps.notifications.models import Notification

User = get_user_model()
logger = logging.getLogger(__name__)


class WebSocketService:
    """
    Service for sending real-time notifications via WebSockets
    Uses Django Channels to broadcast to connected clients
    """

    @staticmethod
    def send_notification(user_id: int, notification: Notification):
        """
        Send notification to a specific user via WebSocket

        This function can be called from synchronous code (views, tasks, etc.)
        It will broadcast to all WebSocket connections for this user
        """
        try:
            channel_layer = get_channel_layer()

            if not channel_layer:
                logger.warning(
                    "Channel layer not configured. WebSocket notification not sent."
                )
                return False

            # Prepare notification data
            notification_data = {
                "notification_id": str(notification.id),
                "title": notification.title,
                "message": notification.message,
                "notification_type": notification.notification_type,
                "priority": notification.priority,
                "is_read": notification.is_read,
                "related_object_type": notification.related_object_type,
                "related_object_id": notification.related_object_id,
                "action_url": notification.action_url,
                "action_data": notification.action_data,
                "metadata": notification.metadata,
                "created_at": notification.created_at.isoformat(),
            }

            # Send to user's group
            user_group_name = f"user_{user_id}_notifications"

            logger.info(
                f"📤 Sending WebSocket notification {notification.id} to user {user_id}: {notification.title}"
            )

            async_to_sync(channel_layer.group_send)(
                user_group_name,
                {
                    "type": "notification_message",
                    "notification": notification_data,
                },
            )

            logger.info(f"✅ WebSocket notification sent to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending WebSocket notification: {str(e)}")
            return False

    @staticmethod
    def send_unread_count(user_id: int, count: int):
        try:
            channel_layer = get_channel_layer()

            if not channel_layer:
                return False

            user_group_name = f"user_{user_id}_notifications"

            async_to_sync(channel_layer.group_send)(
                user_group_name,
                {
                    "type": "unread_count_update",
                    "count": count,
                },
            )

            return True

        except Exception as e:
            logger.error(f"Error sending unread count: {str(e)}")
            return False

    @staticmethod
    def broadcast_to_all(title: str, message: str, notification_type: str = "system"):
        """
        Broadcast a notification to all connected users
        (Use sparingly for system-wide announcements)
        """
        try:
            channel_layer = get_channel_layer()

            if not channel_layer:
                return False

            notification_data = {
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "priority": "high",
                "is_broadcast": True,
            }

            # Send to broadcast group (all connected clients)
            async_to_sync(channel_layer.group_send)(
                "broadcast_notifications",
                {
                    "type": "notification_message",
                    "notification": notification_data,
                },
            )

            logger.info("Broadcast notification sent to all users")
            return True

        except Exception as e:
            logger.error(f"Error broadcasting notification: {str(e)}")
            return False

    @staticmethod
    def bulk_send_notifications(notifications: List[Notification]) -> int:
        """
        Send multiple notifications via WebSocket to their respective users
        More efficient than calling send_notification in a loop
        """
        try:
            channel_layer = get_channel_layer()

            if not channel_layer:
                logger.warning(
                    "Channel layer not configured. WebSocket notifications not sent."
                )
                return 0

            sent_count = 0

            # Group notifications by user for efficient sending
            user_notifications = {}
            for notification in notifications:
                user_id = notification.user_id
                if user_id not in user_notifications:
                    user_notifications[user_id] = []
                user_notifications[user_id].append(notification)

            # Send notifications to each user's group
            for user_id, user_notifs in user_notifications.items():
                user_group_name = f"user_{user_id}_notifications"

                for notification in user_notifs:
                    try:
                        notification_data = {
                            "notification_id": str(notification.id),
                            "title": notification.title,
                            "message": notification.message,
                            "notification_type": notification.notification_type,
                            "priority": notification.priority,
                            "is_read": notification.is_read,
                            "related_object_type": notification.related_object_type,
                            "related_object_id": notification.related_object_id,
                            "action_url": notification.action_url,
                            "action_data": notification.action_data,
                            "metadata": notification.metadata,
                            "created_at": notification.created_at.isoformat(),
                        }

                        async_to_sync(channel_layer.group_send)(
                            user_group_name,
                            {
                                "type": "notification_message",
                                "notification": notification_data,
                            },
                        )
                        sent_count += 1

                    except Exception as e:
                        logger.error(
                            f"Error sending WebSocket notification {notification.id}: {str(e)}"
                        )
                        continue

            logger.info(
                f"Bulk sent {sent_count} WebSocket notifications to {len(user_notifications)} users"
            )
            return sent_count

        except Exception as e:
            logger.error(f"Error in bulk_send_notifications: {str(e)}")
            return 0

    @staticmethod
    def bulk_send_push(
        users: Union[List[User], Any],
        title: str,
        message: str,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Send push notifications to multiple users efficiently
        Uses FCM topics or batch sending for better performance

        Returns:
            Dict with success/failure counts
        """
        try:

            # Get all active device tokens for these users
            if hasattr(users, "values_list"):
                user_ids = list(users.values_list("id", flat=True))
            else:
                user_ids = [u.id for u in users]

            # Get all active FCM devices for these users
            devices = FCMDevice.objects.filter(user_id__in=user_ids, active=True)

            if not devices.exists():
                logger.info(f"No active devices for {len(user_ids)} users")
                return {"success": 0, "failure": 0, "errors": ["No active devices"]}

            # Get all device tokens
            tokens = list(devices.values_list("registration_id", flat=True))

            # Use FCM batch send
            result = FCMService.send_to_tokens(
                tokens=tokens,
                title=title,
                body=message,
                data=data,
            )

            logger.info(
                f"Bulk push sent to {len(user_ids)} users: {result['success']} succeeded, {result['failure']} failed"
            )
            return result

        except Exception as e:
            logger.error(f"Error in bulk_send_push: {str(e)}")
            return {"success": 0, "failure": 0, "errors": [str(e)]}
