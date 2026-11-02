from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from pages.sitemaps import sitemaps

urlpatterns = [
    path("", include("pages.urls")),
    path("", include("accounts.urls")),
    path("", include("properties.urls")),
    path("", include("inquiries.urls")),
    path("", include("reviews.urls")),
    path("", include("chatbot.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
