from django.db import models
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async

from asgiref.sync import async_to_sync
from account.models import Profile
from django.utils import timezone


class Message(models.Model):
    """
    Name: Message model
    Description: This models holds the message, sender, receiver and the timestamps
    author: donaldtedom0@gmail.com
    """
    sender = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    def sent_time(self):
        now = timezone.now()
        diff = now - self.timestamp
        if diff.days == 0:
            if diff.seconds < 60:
                return 'just now'
            elif diff.seconds < 120:
                return '1 minute ago'
            elif diff.seconds < 3600:
                return f'{diff.seconds // 60} minutes ago'
            else:
                return f'{diff.seconds // 3600} hours ago'
        elif diff.days == 1:
            return 'yesterday'
        elif diff.days < 7:
            return f'{diff.days} days ago'
        else:
            return self.timestamp.strftime('%B %d, %Y')

    async def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            await database_sync_to_async(self.save)()

            # Send notification to the sender that the message has been read
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f'user_{self.sender.id}',
                {
                    'type': 'chat.message.read',
                    'message_id': self.id
                }
            )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user-{self.recipient.id}',
            {
                'type': 'user.new_message',
                'sender_id': self.sender.id,
                'sender_name': self.sender.profile.get_full_name(),
                'message': self.message,
                'sent_time': self.sent_time(),
            }
        )

    def __str__(self):
        return f'{self.sender.user.username} to {self.receiver.user.username}: {self.content[:50]}...'
