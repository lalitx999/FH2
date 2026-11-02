from django.urls import path

from . import views

app_name = "inquiries"

urlpatterns = [path("inquiries/submit/", views.submit, name="submit")]
