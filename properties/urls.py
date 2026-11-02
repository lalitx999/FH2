from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "properties"

urlpatterns = [
    path("properties/", views.property_list, name="list"),
    path("properties/compare/", views.compare, name="compare"),
    path("properties/create/", RedirectView.as_view(pattern_name="properties:sell", permanent=True)),
    path("properties/<int:pk>/bookmark/", views.toggle_bookmark, name="bookmark"),
    # ต้องใช้ str เพราะตัวแปลง slug ของ Django รับเฉพาะ ASCII แต่ slug ของเราเป็นภาษาไทย
    path("properties/<str:slug>/", views.property_detail, name="detail"),
    path("favorites/", views.favorites, name="favorites"),
    path("my-listings/", views.my_listings, name="my_listings"),
    path("sell/", views.sell, name="sell"),
    path("sell/images/<int:pk>/delete/", views.sell_image_delete, name="sell_image_delete"),
    path("sell/<str:code>/images/", views.sell_images, name="sell_images"),
    path("sell/<str:code>/images/upload/", views.sell_image_upload, name="sell_image_upload"),
    path("sell/<str:code>/submit/", views.sell_submit, name="sell_submit"),
    path("consignment/", views.consignment_new, name="consignment"),
    path("consignment/<int:pk>/files/", views.consignment_files, name="consignment_files"),
    path("consignment/<int:pk>/upload/<str:kind>/", views.consignment_upload, name="consignment_upload"),
    path("consignment/<int:pk>/submit/", views.consignment_submit, name="consignment_submit"),
    path("consignment/images/<int:pk>/delete/", views.consignment_image_delete, name="consignment_image_delete"),
    path("consignment/deeds/<int:pk>/delete/", views.consignment_deed_delete, name="consignment_deed_delete"),
]
