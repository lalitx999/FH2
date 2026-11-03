from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from properties.models import Property
from reviews.models import Article


class StaticSitemap(Sitemap):
    def items(self):
        return ["pages:home", "properties:list", "pages:about", "pages:services", "pages:contact",
                "pages:faq", "pages:fee_guide", "pages:loan_calculator", "reviews:article_list", "reviews:review_list", "pages:namecard"]

    def location(self, name):
        return reverse(name)


class PropertySitemap(Sitemap):
    def items(self):
        # ทรัพย์ตัวอย่างต้องไม่ถูกส่งให้เครื่องมือค้นหา
        return Property.objects.filter(status=Property.Status.PUBLISHED, is_sample=False).only("slug", "updated_at")

    def lastmod(self, obj):
        return obj.updated_at


class ArticleSitemap(Sitemap):
    def items(self):
        return Article.objects.filter(is_published=True).only("slug", "kind", "updated_at")

    def lastmod(self, obj):
        return obj.updated_at


sitemaps = {"pages": StaticSitemap, "properties": PropertySitemap, "articles": ArticleSitemap}
