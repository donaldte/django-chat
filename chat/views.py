from django.shortcuts import render
from django.views import View



class HomeView(View):
    """ Page principale """
    
    template_name = 'index.html'
    
    def get(self, request, *args, **kwargs):
        
        return render(request, self.template_name)