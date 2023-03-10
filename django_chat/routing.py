from django.urls import re_path

from chat import consumers

websocket_urlpatterns = [
    re_path(r'ws/private_chat/(?P<user_id>\d+)/$', consumers.PrivateChatConsumer.as_asgi()),
    re_path(r'ws/user_status/$', consumers.UserStatusConsumer.as_asgi()),
]