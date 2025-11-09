import json, logging
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from apps.accounts.auth import Authentication
from apps.notifications.models import Notification
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications
    Connection URL: ws://domain.com/ws/notifications/?token=<access_token>
    """

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]
        user = await Authentication.retrieve_user_from_token(token)
        if not user:
            logger.warning("Unauthorized WebSocket connection attempt")
            await self.close()
            return
        self.scope["user"] = self.user = user
        self.user_group_name = f"user_{user.id}_notifications"

        # Join user's notification group
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()
        logger.info(f"WebSocket connected for user {user.id}")

        # Send initial unread count
        unread_count = await self.get_unread_count()
        await self.send(
            text_data=json.dumps({"type": "unread_count", "count": unread_count})
        )

    async def disconnect(self, close_code):
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(
                self.user_group_name, self.channel_name
            )
            logger.info(
                f"WebSocket disconnected for user {self.user.id if self.user else 'unknown'}"
            )

    async def receive(self, text_data):
        """
        Handle messages from WebSocket client

        Supported commands:
        - {"command": "get_unread_count"}
        - {"command": "mark_read", "notification_ids": ["uuid1", "uuid2"]}
        - {"command": "ping"}
        """
        try:
            data = json.loads(text_data)
            command = data.get("command")

            if command == "get_unread_count":
                unread_count = await self.get_unread_count()
                await self.send(
                    text_data=json.dumps(
                        {"type": "unread_count", "count": unread_count}
                    )
                )

            elif command == "mark_read":
                notification_ids = data.get("notification_ids", [])
                if notification_ids:
                    count = await self.mark_notifications_read(notification_ids)
                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "mark_read_response",
                                "count": count,
                                "notification_ids": notification_ids,
                            }
                        )
                    )

            elif command == "ping":
                await self.send(
                    text_data=json.dumps(
                        {"type": "pong", "timestamp": str(timezone.now())}
                    )
                )

            else:
                await self.send(
                    text_data=json.dumps(
                        {"type": "error", "message": f"Unknown command: {command}"}
                    )
                )

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps({"type": "error", "message": "Invalid JSON"})
            )
        except Exception as e:
            logger.error(f"Error in WebSocket receive: {str(e)}")
            await self.send(
                text_data=json.dumps({"type": "error", "message": "Internal error"})
            )

    async def notification_message(self, event):
        notification_data = event["notification"]

        # Send notification to WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "notification", "notification": notification_data}
            )
        )

        # Also send updated unread count
        unread_count = await self.get_unread_count()
        await self.send(
            text_data=json.dumps({"type": "unread_count", "count": unread_count})
        )

    async def get_unread_count(self):
        return await Notification.objects.filter(user=self.user, is_read=False).acount()

    async def mark_notifications_read(self, notification_ids):
        updated = await Notification.objects.filter(
            notification_id__in=notification_ids, user=self.user, is_read=False
        ).aupdate(is_read=True, read_at=timezone.now())
        return updated
