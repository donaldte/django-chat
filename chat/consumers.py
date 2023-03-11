"""
LIST OF CONSUMERS
AUTHOR: DONALD PROGRAMMEUR
"""
import json
from datetime import timezone, timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from .models import Profile, Message


User = get_user_model()


class PrivateChatConsumer(AsyncWebsocketConsumer):
    # When a client connects to the WebSocket, set up the necessary variables
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.room_name = None
        self.other_user = None
        self.other_user_id = None
        self.user = None

    async def connect(self):
        self.user = self.scope["user"]  # Get the current user
        self.other_user_id = self.scope['url_route']['kwargs']['user_id']  # Get the ID of the other user
        self.other_user = await self.get_other_user(self.other_user_id)  # Get the Profile object of the other user
        self.room_name = f'private_chat_{self.user.id}_{self.other_user_id}'  # Create a unique room name for the chat

        # Add the consumer to the channel layer group for the room
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()

    # When the WebSocket connection is closed, remove the consumer from the channel layer group
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )

    # When the consumer receives a message from the WebSocket, create a new message object and send it to the room group
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']  # Extract the message text from the JSON data

        # Create a new message object and save it to the database
        await self.create_message(message)

        # Send the message to the room group
        await self.channel_layer.group_send(
            self.room_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': self.user.username
            }
        )

    # When a message is received by the channel layer group, send it back to the WebSocket
    async def chat_message(self, event):
        message = event['message']  # Extract the message text from the event data
        username = event['username']  # Extract the username from the event data

        # Send the message and username back to the WebSocket as JSON data
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username
        }))

    # Get the Profile object for the other user in the chat
    async def get_other_user(self, user_id):
        try:
            other_user = Profile.objects.get(user__id=user_id)
            return other_user
        except Profile.DoesNotExist:
            return None

    # Create a new message object and save it to the database
    async def create_message(self, message_content):
        message = Message.objects.create(
            sender=self.user.profile,
            receiver=self.other_user,
            content=message_content
        )
        message.save()


class UserListStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add('user_list', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('user_list', self.channel_name)

    async def receive(self, text_data):
        # Receive message from WebSocket
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Add new user to the list when they create an account
        if message == 'user_created':
            new_user = text_data_json['user']
            user_data = await self.get_user_data(new_user)
            user_data['status'] = 'online'
            await self.channel_layer.group_send(
                "user_list",
                {
                    "type": "user_list_update",
                    "users": [user_data],
                }
            )
        else:
            # Update user status and send updated user list
            user = self.scope["user"]
            if user.is_authenticated:
                await database_sync_to_async(self.update_user_status)(user.id, True)
            await self.send_user_list()

    async def user_online(self, event):
        user_id = event['user_id']
        await self.update_user_status(user_id, True)
        user_list = await self.get_sorted_user_list()
        await self.send_user_list(user_list)

    async def user_offline(self, event):
        user_id = event['user_id']
        await self.update_user_status(user_id, False)
        user_list = await self.get_sorted_user_list()
        await self.send_user_list(user_list)

    async def user_created(self, event):
        user_list = await self.get_sorted_user_list()
        await self.send_user_list(user_list)

    @database_sync_to_async
    def update_user_status(self, user_id, status):
        user = Profile.objects.get(pk=user_id)
        user.last_online = timezone.now() if status else None
        user.save()

    @database_sync_to_async
    def get_sorted_user_list(self):
        profiles = Profile.objects.all()
        sorted_profiles = sorted(profiles, key=lambda p: p.last_online, reverse=True)
        user_list = []
        for profile in sorted_profiles:
            user_dict = {
                'id': profile.id,
                'username': profile.user.username,
                'is_online': profile.last_online and (timezone.now() - profile.last_online) < timedelta(minutes=5),
                'last_seen': profile.last_seen.strftime('%b %d %Y %I:%M %p') if profile.last_seen else '',
            }
            user_list.append(user_dict)
        return user_list

    @database_sync_to_async
    def get_user_data(self, user_id):
        user = get_user_model().objects.get(id=user_id)
        return {
            'id': user.id,
            'username': user.username,
            'status': user.last_seen,
            'last_login': str(user.last_login) if user.last_login else None
        }

    async def send_user_list(self, user_list):
        await self.send(text_data=json.dumps({'user_list': user_list}))
