from urllib.parse import parse_qs
from apps.accounts.auth import Authentication

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

        scope["user"] = None
        if token:
            user = await Authentication.retrieve_user_from_token(token)
            scope["user"] = user
            if not user:
                logger.warning(f"WebSocket auth failed: {str(e)}")
        return await self.app(scope, receive, send)
