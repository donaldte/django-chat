from django.views import View
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Profile, Message
from django.contrib.auth.mixins import LoginRequiredMixin


@login_required
@csrf_exempt
def send_message(request):
    """
    This view sends a message from the sender to the receiver.
    """
    if request.method == 'POST':
        receiver_id = request.POST.get('receiver_id')
        receiver = get_object_or_404(Profile, id=receiver_id)
        message_content = request.POST.get('message')

        # Create a new message and save it to the database
        new_message = Message(sender=request.user.profile, receiver=receiver, content=message_content)
        new_message.save()

        # Send a message to the receiver's channel layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{receiver.user.username}",
            {
                "type": "chat.message",
                "message": message_content,
                "sender_username": request.user.username,
                "sender_avatar": request.user.profile.avatar.image.url
            }
        )

        return JsonResponse({'status': 'ok'})


class HomeView(LoginRequiredMixin, View):
    """ Page principale """

    template_name = 'index.html'

    def get(self, request, username=None, *args, **kwargs):
        # the list of users who are registered on the site.
        users = Profile.objects.exclude(user=request.user)
        # the chat room for the two users.
        receiver = get_object_or_404(Profile, user__username=username)
        messages = Message.objects.filter(sender=request.user.profile, receiver=receiver)
        context = {'receiver': receiver, 'messages': messages, 'users': users}
        return render(request, self.template_name, context)
