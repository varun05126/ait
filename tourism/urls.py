from django.contrib import admin
from django.urls import path
from tourism import views

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
