"""
URL configuration for ait project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from tourism import views  # ✅ Make sure this line exists!

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='home'),
    path('destinations/', views.destinations, name='destinations'),
    path('planner/', views.planner, name='planner'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('chatbot-response/', views.chatbot_response, name='chatbot_response'),
    path('chat-api/', views.chatbot_response, name='chat_api'),
    path('chat-api/', views.chatbot_response, name='chatbot_response')


]

