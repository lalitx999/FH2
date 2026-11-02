from django.conf import settings


def site(request):
    return {
        "site": {
            "phone": settings.SITE_PHONE,
            "email": settings.SITE_EMAIL,
            "line_id": settings.SITE_LINE_ID,
            "line_url": settings.SITE_LINE_URL,
        },
        "max_compare_items": settings.MAX_COMPARE_ITEMS,
    }
