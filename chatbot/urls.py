from django.urls import path

from . import views

app_name = "chatbot"

urlpatterns = [
    path("chat/send/", views.send, name="send"),
    path("chat/messages/<int:pk>/", views.message, name="message"),
    path("chat/history/", views.history, name="history"),
]
