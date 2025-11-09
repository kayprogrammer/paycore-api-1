from urllib.parse import parse_qs
from apps.accounts.auth import Authentication
import logging

logger = logging.getLogger(__name__)


class NotificationAuthMiddleware:
    """
    Middleware to authenticate WebSocket connections using JWT token
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        print("=" * 80)
        print("🔍 WebSocket Connection Attempt")
        print(f"📍 Query String: {query_string}")
        print(f"🔑 Token Present: {bool(token)}")
        if token:
            print(f"🔑 Token (first 30 chars): {token[:30]}...")
        print("=" * 80)

        scope["user"] = None
        if token:
            try:
                print("🔐 Attempting to retrieve user from token...")
                user = await Authentication.retrieve_user_from_token(token)
                print(f"👤 User retrieved: {user}")
                scope["user"] = user
                if user:
                    print(f"✅ WebSocket authenticated for user: {user.id}")
                    logger.info(f"WebSocket authenticated for user: {user.id}")
                else:
                    print("❌ WebSocket auth failed: Invalid token (user is None)")
                    logger.warning(f"WebSocket auth failed: Invalid token")
            except Exception as e:
                print(f"❌ WebSocket auth error: {str(e)}")
                print(f"❌ Error type: {type(e).__name__}")
                import traceback

                traceback.print_exc()
                logger.error(f"WebSocket auth error: {str(e)}")
                scope["user"] = None
        else:
            print("❌ WebSocket connection attempt without token")
            logger.warning("WebSocket connection attempt without token")

        print(f"🎯 Final scope['user']: {scope.get('user')}")
        print("=" * 80)
        return await self.app(scope, receive, send)
