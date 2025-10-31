from typing import Dict, Any, List
from django.contrib.auth import get_user_model
from django.conf import settings
from firebase_admin.messaging import (
    APNSConfig,
    APNSPayload,
    AndroidConfig,
    AndroidNotification,
    Aps,
    Message,
    MulticastMessage,
    Notification,
    send_each_for_multicast,
)
import logging

try:
    from firebase_admin import messaging
    from fcm_django.models import FCMDevice

    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(
        "Firebase Admin SDK not available. Push notifications will not work."
    )

User = get_user_model()
logger = logging.getLogger(__name__)


class FCMService:
    """
    Firebase Cloud Messaging service for push notifications
    Firebase is initialized in settings.py
    """

    @staticmethod
    def send_to_user(
        user: User,
        title: str,
        body: str,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase not available. Skipping push notification.")
            return {"success": 0, "failure": 0, "errors": ["Firebase not configured"]}

        if not user.push_enabled:
            logger.info(f"Push notifications disabled for user {user.id}")
            return {
                "success": 0,
                "failure": 0,
                "errors": ["Push notifications disabled for user"],
            }

        try:
            device = FCMDevice.objects.filter(user=user, active=True).first()

            if not device:
                logger.info(f"No active device for user {user.id}")
                return {"success": 0, "failure": 0, "errors": ["No active device"]}

            device.send_message(
                Message(notification=Notification(title=title, body=body), data=data)
            )
            logger.info(f"Push notification sent to user {user.id}")
            return {"success": 1, "failure": 0}

        except Exception as e:
            logger.error(f"Error sending push notification to user {user.id}: {str(e)}")
            return {"success": 0, "failure": 1, "errors": [str(e)]}

    @staticmethod
    def send_to_tokens(
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, Any] = None,
        image: str = None,
    ) -> Dict[str, Any]:
        """
        Send push notification to specific device tokens using Firebase multicast
        Optimized for bulk sending - handles up to 500 tokens per request
        Returns success/failure counts and details
        """
        if not FIREBASE_AVAILABLE:
            return {"success": 0, "failure": 0, "errors": ["Firebase not available"]}

        try:
            # Platform-specific configs
            message = MulticastMessage(
                notification=Notification(title=title, body=body, image=image),
                data=data_payload,
                tokens=tokens,
                android=AndroidConfig(
                    priority="high",
                    notification=AndroidNotification(
                        sound=sound,
                        channel_id="default",
                        priority="high",
                    ),
                ),
                apns=APNSConfig(
                    payload=APNSPayload(
                        aps=Aps(
                            sound=sound,
                            badge=badge,
                            content_available=True,
                        )
                    )
                ),
            )

            # Send multicast message
            response = send_each_for_multicast(message)

            # Collect failed tokens for bulk deactivation
            invalid_tokens = [
                tokens[idx]
                for idx, resp in enumerate(response.responses)
                if not resp.success
                and resp.exception
                and resp.exception.code
                in ["invalid-registration-token", "registration-token-not-registered"]
            ]

            # Bulk deactivate invalid tokens in one query
            if invalid_tokens:
                deactivated = FCMDevice.objects.filter(
                    registration_id__in=invalid_tokens
                ).update(active=False)
                logger.info(f"Deactivated {deactivated} invalid device tokens")

            logger.info(
                f"Push sent: {response.success_count} success, {response.failure_count} failed"
            )

            return {
                "success": response.success_count,
                "failure": response.failure_count,
                "invalid_tokens": invalid_tokens,
            }

        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            return {"success": 0, "failure": len(tokens), "errors": [str(e)]}

    @staticmethod
    def send_to_topic(
        topic: str,
        title: str,
        body: str,
        data: Dict[str, Any] = None,
    ) -> bool:
        """
        Send push notification to a topic
        Useful for broadcasting to multiple users
        """
        if not FIREBASE_AVAILABLE:
            return False
        FCMDevice.send_topic_message(
            Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data,
            ),
            topic,
        )
        logger.info(f"Successfully sent message to topic {topic}: {response}")
        return True

    @staticmethod
    async def subscribe_to_topic(user: User, topic: str) -> Dict[str, int]:
        if not FIREBASE_AVAILABLE:
            return {"success": 0, "failure": len(tokens)}
        device = await FCMDevice.objects.filter(user=user, active=True).afirst()
        if not device:
            return {"success": 0, "failure": 0, "errors": ["No active device"]}
        device.handle_topic_subscription(True, topic=topic)
        return {"success": 1, "failure": 0}

    @staticmethod
    async def unsubscribe_from_topic(user: User, topic: str) -> Dict[str, int]:
        if not FIREBASE_AVAILABLE:
            return {"success": 0, "failure": 0, "errors": ["Firebase not available"]}
        device = await FCMDevice.objects.filter(user=user, active=True).afirst()
        if not device:
            return {"success": 0, "failure": 0, "errors": ["No active device"]}
        device.handle_topic_subscription(False, topic=topic)
        return {"success": 1, "failure": 0}

    @staticmethod
    async def register_device(
        user: User,
        device_token: str,
        device_type: str,
    ) -> Dict[str, Any]:
        """
        Register or update FCM device for user and subscribe to global topic
        Called during login (normal, Google OAuth, and biometrics)
        """
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase not available. Cannot register device.")
            return {"success": False, "error": "Firebase not configured"}

        try:
            # Create or update FCM device
            device, created = await FCMDevice.objects.aupdate_or_create(
                user=user,
                defaults={
                    "registration_id": device_token,
                    "type": device_type,
                    "active": True,
                },
            )

            action = "registered" if created else "updated"
            logger.info(f"Device {action} for user {user.id}: {device_type}")

            # Subscribe user to global FCM topic
            subscription_result = await FCMService.subscribe_to_topic(
                user, settings.GLOBAL_FCM_TOPIC_NAME
            )

            if subscription_result["success"] > 0:
                logger.info(
                    f"User {user.id} subscribed to topic: {settings.GLOBAL_FCM_TOPIC_NAME}"
                )
            else:
                logger.warning(
                    f"Failed to subscribe user {user.id} to topic: {settings.GLOBAL_FCM_TOPIC_NAME}"
                )

            return {
                "success": True,
                "device_id": str(device.id),
                "action": action,
                "topic_subscribed": settings.GLOBAL_FCM_TOPIC_NAME,
            }

        except Exception as e:
            logger.error(f"Error registering device for user {user.id}: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def bulk_send_to_users(
        users: List[User],
        title: str,
        body: str,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Send push notifications to multiple users efficiently
        Returns:
            Dict with success/failure counts
        """
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase not available. Skipping bulk push notification.")
            return {"success": 0, "failure": 0, "errors": ["Firebase not configured"]}

        try:
            # Get all user IDs
            user_ids = (
                [u.id for u in users]
                if isinstance(users, list)
                else list(users.values_list("id", flat=True))
            )

            devices = FCMDevice.objects.filter(user_id__in=user_ids, active=True)

            if not devices.exists():
                logger.info(f"No active devices for {len(user_ids)} users")
                return {"success": 0, "failure": 0, "errors": ["No active devices"]}

            devices.send_message(
                Message(notification=Notification(title=title, body=body), data=data)
            )
            device_count = devices.count()
            logger.info(
                f"Bulk push sent to {device_count} devices for {len(user_ids)} users"
            )
            return {"success": device_count, "failure": 0}

        except Exception as e:
            logger.error(f"Error in bulk push notification: {str(e)}")
            return {"success": 0, "failure": len(users), "errors": [str(e)]}
