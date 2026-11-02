from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from config.ajax import error
from config.throttle import client_ip, hit
from pages.services import schema_service

from .forms import CustomerReviewForm
from .models import Article
from .selectors import article_selector as selector


def _detail(request, kind, slug):
    article = selector.article_detail_or_none(kind, slug)
    if article is None:
        raise Http404
    list_name = "รีวิว" if kind == Article.Kind.REVIEW else "บทความ"
    list_url = reverse("reviews:review_list" if kind == Article.Kind.REVIEW else "reviews:article_list")
    return render(request, "reviews/article_detail.html", {
        "article": article,
        "schema": schema_service.to_script(
            schema_service.article(request, article),
            schema_service.breadcrumbs(request, (list_name, list_url), (article.title, article.get_absolute_url())),
        ),
    })


def article_list(request):
    return render(request, "reviews/article_list.html", {
        "page": Paginator(selector.published_articles(), 12).get_page(request.GET.get("page")),
        "title": "บทความ",
    })


def article_detail(request, slug):
    return _detail(request, Article.Kind.ARTICLE, slug)


def review_list(request):
    return render(request, "reviews/review_list.html", {
        "page": Paginator(selector.published_property_reviews(), 12).get_page(request.GET.get("page")),
        "customer_reviews": selector.approved_customer_reviews(12),
        "form": CustomerReviewForm(),
    })


def review_detail(request, slug):
    return _detail(request, Article.Kind.REVIEW, slug)


@require_POST
def submit_customer_review(request):
    if hit("review", client_ip(request), 5, 60 * 60):
        return error("ส่งรีวิวบ่อยเกินไป กรุณาลองใหม่ภายหลัง", status=429)
    form = CustomerReviewForm(request.POST)
    if not form.is_valid():
        return render(request, "reviews/_review_form.html", {"form": form}, status=422)
    form.save()
    return render(request, "reviews/_review_thanks.html")
