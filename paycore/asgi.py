"""
ASGI config for paycore project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from decouple import config

os.environ.setdefault("DJANGO_SETTINGS_MODULE", config("DJANGO_SETTINGS_MODULE"))

# Initialize Django ASGI application early to ensure AppRegistry is populated
# before importing other modules that may depend on models
django_asgi_app = get_asgi_application()

# Import channels and routing after Django is initialized
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from apps.notifications.consumers import NotificationAuthMiddleware
from apps.notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        NotificationAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
