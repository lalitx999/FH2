from django.urls import path

from . import views

app_name = "dashboard"


def crud_paths(prefix, name, group):
    return [
        path(f"{prefix}/", group["list"], name=name),
        path(f"{prefix}/new/", group["new"], name=f"{name}_new"),
        path(f"{prefix}/<int:pk>/", group["edit"], name=f"{name}_edit"),
        path(f"{prefix}/<int:pk>/delete/", group["delete"], name=f"{name}_delete"),
    ]


urlpatterns = [
    path("", views.home, name="home"),
    path("properties/", views.PropertyList.as_view(), name="properties"),
    path("properties/new/", views.PropertyCreate.as_view(), name="property_new"),
    path("properties/<int:pk>/", views.PropertyEdit.as_view(), name="property_edit"),
    path("properties/<int:pk>/status/", views.property_set_status, name="property_status"),
    path("properties/<int:pk>/delete/", views.property_delete, name="property_delete"),
    path("properties/<int:pk>/images/", views.property_image_upload, name="property_image_upload"),
    path("images/<int:pk>/delete/", views.property_image_delete, name="property_image_delete"),
    path("images/<int:pk>/cover/", views.property_image_cover, name="property_image_cover"),
    path("consignments/", views.ConsignmentList.as_view(), name="consignments"),
    path("consignments/<int:pk>/", views.consignment_detail, name="consignment_detail"),
    path("consignments/<int:pk>/status/", views.consignment_set_status, name="consignment_status"),
    path("consignments/<int:pk>/convert/", views.consignment_convert, name="consignment_convert"),
    path("deeds/<int:pk>/", views.deed_file, name="deed_file"),
    path("inquiries/", views.InquiryList.as_view(), name="inquiries"),
    path("inquiries/<int:pk>/toggle/", views.inquiry_toggle, name="inquiry_toggle"),
    path("customer-reviews/", views.CustomerReviewList.as_view(), name="customer_reviews"),
    path("customer-reviews/<int:pk>/toggle/", views.customer_review_toggle, name="customer_review_toggle"),
    path("customer-reviews/<int:pk>/delete/", views.customer_review_delete, name="customer_review_delete"),
    path("chats/", views.ChatList.as_view(), name="chats"),
    path("chats/<uuid:pk>/", views.chat_detail, name="chat_detail"),
    path("users/", views.UserList.as_view(), name="users"),
    path("users/<int:pk>/", views.UserEdit.as_view(), name="user_edit"),
    *crud_paths("articles", "articles", views.article_views),
    *crud_paths("categories", "categories", views.category_views),
    *crud_paths("locations", "locations", views.location_views),
]
