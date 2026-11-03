from django.urls import path
from django.views.generic import RedirectView, TemplateView

from . import views

app_name = "pages"


def static_page(template):
    return TemplateView.as_view(template_name=f"pages/{template}.html")


urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("faq/", views.faq, name="faq"),
    path("guides/transfer-fees/", views.fee_guide, name="fee_guide"),
    path("tools/loan-calculator/", views.loan_calculator, name="loan_calculator"),
    path("services/", static_page("services"), name="services"),
    path("projects/", static_page("projects"), name="projects"),
    path("contact/", views.contact, name="contact"),
    path("namecard/", static_page("namecard"), name="namecard"),
    path("robots.txt", views.robots, name="robots"),
    path("favicon.ico", views.favicon),
    path("llms.txt", views.llms, name="llms"),
    path("llms-full.txt", views.llms_full, name="llms_full"),
    path("llm.txt", RedirectView.as_view(pattern_name="pages:llms", permanent=True)),
    path("llm-full.txt", RedirectView.as_view(pattern_name="pages:llms_full", permanent=True)),
]
