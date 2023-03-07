from django.db import models
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from channels.db import database_sync_to_async

from django.contrib.auth.models import User
from avatar.models import Avatar


class Profile(models.Model):
    """
    Name: Profile table
    Description: This table represents the profile of each table
    author: donaldtedom0@gmail.com
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    last_seen = models.DateTimeField(null=True, blank=True) # last time the user connect to the system
    last_online = models.DateTimeField(null=True, blank=True) # last time the user used the chat feature
    avatar = models.OneToOneField(Avatar, on_delete=models.CASCADE, null=True, blank=True)
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)

    def save(self, *args, **kwargs):
        if not self.avatar:
            if self.gender == 'M':
                self.avatar = Avatar.objects.create(user=self.user, primary=True, avatar_type='gravatar')
            elif self.gender == 'F':
                self.avatar = Avatar.objects.create(user=self.user, primary=True, avatar_type='female')
            else:
                # Default avatar for "other" gender
                self.avatar = Avatar.objects.create(user=self.user, primary=True, avatar_type='identicon')    
        super(Profile, self).save(*args, **kwargs)
        
    @database_sync_to_async
    async def get_unread_messages_count(self, sender):
        from chat.models import Message
        """
        Returns the number of unread messages from the given sender.
        """
        return Message.objects.filter(sender=sender, recipient=self.user, is_read=False).count()    
    
    def last_seen(self):
        if self.last_online is None:
            return 'never'
        now = timezone.now()
        diff = now - self.last_online
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
            return self.last_online.strftime('%B %d, %Y')

    def set_last_online(self):
        self.last_online = timezone.now()
        self.save()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user-{self.user.id}',
            {
                'type': 'user.last_online',
                'last_online': self.last_seen(),
            }
        )
    
