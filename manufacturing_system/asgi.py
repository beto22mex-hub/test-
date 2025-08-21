"""
ASGI config for manufacturing_system project.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import manufacturing.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacturing_system.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            manufacturing.routing.websocket_urlpatterns
        )
    ),
})
