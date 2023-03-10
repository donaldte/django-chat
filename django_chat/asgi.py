from django.urls import path
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from routing import websocket_urlpatterns
import os


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_chat.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns)
    # Just HTTP for now. (We can add other protocols later.)
})
