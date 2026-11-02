from django.db.models import Count, OuterRef, Q, Subquery

from chatbot.models import ChatMessage, ChatSession
from inquiries.models import Inquiry
from properties.models import Category, Consignment, Location, Property
from reviews.models import Article, CustomerReview


def pending_counts():
    """ตัวเลขงานค้างบนเมนูด้านข้าง"""
    return {
        "listings": Property.objects.filter(status=Property.Status.REVIEW).count(),
        "consignments": Consignment.objects.filter(status=Consignment.Status.PENDING).count(),
        "inquiries": Inquiry.objects.filter(is_handled=False).count(),
        "reviews": CustomerReview.objects.filter(is_approved=False).count(),
    }


def overview():
    property_counts = Property.objects.aggregate(
        published=Count("id", filter=Q(status=Property.Status.PUBLISHED)),
        review=Count("id", filter=Q(status=Property.Status.REVIEW)),
    )
    return {
        "stats": [
            {"label": "ประกาศเผยแพร่", "value": property_counts["published"], "icon": "fa-house", "tone": "green", "url": "dashboard:properties"},
            {"label": "ประกาศรอตรวจ", "value": property_counts["review"], "icon": "fa-hourglass-half", "tone": "gold", "url": "dashboard:properties"},
            {"label": "ฝากขายรอตรวจ", "value": Consignment.objects.filter(status=Consignment.Status.PENDING).count(), "icon": "fa-file-signature", "tone": "blue", "url": "dashboard:consignments"},
            {"label": "ข้อความใหม่", "value": Inquiry.objects.filter(is_handled=False).count(), "icon": "fa-envelope", "tone": "rose", "url": "dashboard:inquiries"},
        ],
        "pending_listings": Property.objects.filter(status=Property.Status.REVIEW).only("title", "property_code")[:5],
        "pending_consignments": Consignment.objects.filter(status=Consignment.Status.PENDING).only("owner_name", "district", "property_type")[:5],
        "new_inquiries": Inquiry.objects.filter(is_handled=False).only("name", "message", "phone")[:5],
    }


def properties(status="", q=""):
    items = Property.objects.select_related("category", "location", "agent").annotate(image_count=Count("images")).defer("description", "landmarks", "features").order_by("-created_at")
    if status:
        items = items.filter(status=status)
    if q:
        items = items.filter(Q(title__icontains=q) | Q(property_code__icontains=q))
    return items


def consignment_detail():
    return Consignment.objects.select_related("owner", "converted_property").prefetch_related("images", "deeds")


def articles():
    return Article.objects.defer("content")


def categories():
    return Category.objects.annotate(property_count=Count("properties")).order_by("sort_order", "id")


def locations():
    return Location.objects.annotate(property_count=Count("properties")).order_by("name")


def chat_sessions():
    first_question = ChatMessage.objects.filter(session=OuterRef("pk"), role=ChatMessage.Role.USER).order_by("id")
    return (
        ChatSession.objects.select_related("user")
        .annotate(message_count=Count("messages"), first_question=Subquery(first_question.values("content")[:1]))
        .order_by("-updated_at")
    )
