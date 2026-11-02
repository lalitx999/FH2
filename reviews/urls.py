from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("articles/", views.article_list, name="article_list"),
    path("articles/<str:slug>/", views.article_detail, name="article_detail"),
    path("reviews/", views.review_list, name="review_list"),
    path("reviews/submit/", views.submit_customer_review, name="submit"),
    path("reviews/<str:slug>/", views.review_detail, name="review_detail"),
]
