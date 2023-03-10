import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from .models import Profile, Message
from django.db.models.signals import post_save
from django.dispatch import receiver

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


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


# Define a WebSocket consumer for user status updates
class UserStatusConsumer(AsyncWebsocketConsumer):

    # Method called when a WebSocket connection is established
    async def connect(self):
        # Add the current channel to a group named "user_status"
        await self.channel_layer.group_add("user_status", self.channel_name)
        # Accept the WebSocket connection
        await self.accept()

    async def user_create(self, event):
        user = event['user']
        user_list = []
        users = Profile.objects.all().order_by('-last_online')
        for user in users:
            user_list.append({'id': user.id, 'username': user.user.username, 'online': user.is_online})
        await self.send(text_data=json.dumps({'type': 'user_status_update', 'users': user_list}))

    # Method called when a WebSocket connection is closed
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("user_status", self.channel_name)
        # update user status in the database
        user = self.scope['user']
        if user.is_authenticated:
            profile = await database_sync_to_async(Profile.objects.get)(user=user)
            profile.is_online = False
            profile.save()
            await self.channel_layer.group_send("user_status", {'type': 'user_status_update'})

    # Method called when a user's online status is updated
    async def user_status_update(self, event):
        # Retrieve all user profiles and sort them by last online time
        users = Profile.objects.all().order_by('-last_online')
        # Initialize an empty list to store user information
        user_list = []
        # Loop through each user profile and add their information to the user list
        for user in users:
            user_list.append({'id': user.id, 'username': user.user.username, 'online': user.is_online})
        # Send a WebSocket message to the client containing the updated user list
        await self.send(text_data=json.dumps({'type': 'user_status_update', 'users': user_list}))
