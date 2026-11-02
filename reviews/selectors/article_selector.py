from reviews.models import Article, CustomerReview


def _published(kind):
    return Article.objects.filter(kind=kind, is_published=True).defer("content")


def published_articles():
    return _published(Article.Kind.ARTICLE)


def published_property_reviews():
    return _published(Article.Kind.REVIEW)


def latest_articles(limit):
    return published_articles()[:limit]


def article_detail_or_none(kind, slug):
    return Article.objects.filter(kind=kind, slug=slug, is_published=True).select_related("property").first()


def approved_customer_reviews(limit):
    return CustomerReview.objects.filter(is_approved=True)[:limit]


def published_article_bodies():
    """ใช้สร้าง llms-full.txt เท่านั้น เพราะต้องการเนื้อหาเต็ม"""
    return Article.objects.filter(kind=Article.Kind.ARTICLE, is_published=True)
