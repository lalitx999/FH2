"""สร้างข้อมูล schema.org ทุกชนิดของเว็บ ข้อมูลต้องตรงกับที่แสดงบนหน้าเว็บเสมอ"""
import json

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from pages import content
from properties.models import Property

SITE_NAME = "Finding House"
RESIDENCE_TYPES = {"condo": "Apartment", "house": "SingleFamilyResidence", "townhome": "House"}


def base_url(request):
    return request.build_absolute_uri("/").rstrip("/")


def org_ref(request):
    return {"@id": f"{base_url(request)}/#organization"}


def to_script(*items):
    """แทนที่ < เพื่อกันข้อความในข้อมูลปิดแท็ก script เอง"""
    payload = {"@context": "https://schema.org", "@graph": [item for item in items if item]}
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return format_html('<script type="application/ld+json">{}</script>', mark_safe(data))


def organization(request):
    root = base_url(request)
    data = {
        "@type": "RealEstateAgent",
        "@id": f"{root}/#organization",
        "name": SITE_NAME,
        "url": f"{root}/",
        "image": f"{root}{static('images/cover.jpg')}",
        "description": content.ABOUT_SUMMARY,
        "slogan": "เรื่องบ้านไว้ใจเรา",
        "areaServed": {"@type": "Country", "name": "ประเทศไทย"},
        "address": {"@type": "PostalAddress", "addressRegion": "กรุงเทพมหานคร", "addressCountry": "TH"},
    }
    if settings.SITE_EMAIL:
        data["email"] = settings.SITE_EMAIL
    if settings.SITE_PHONE:
        data["telephone"] = settings.SITE_PHONE
    if settings.SITE_LINE_URL:
        data["sameAs"] = [settings.SITE_LINE_URL]
    return data


def website(request):
    root = base_url(request)
    return {
        "@type": "WebSite",
        "@id": f"{root}/#website",
        "url": f"{root}/",
        "name": SITE_NAME,
        "inLanguage": "th-TH",
        "publisher": org_ref(request),
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": f"{root}{reverse('properties:list')}?q={{search_term_string}}"},
            "query-input": "required name=search_term_string",
        },
    }


def breadcrumbs(request, *crumbs):
    """crumbs คือ (ชื่อ, path) ต่อจากหน้าแรก"""
    root = base_url(request)
    trail = [("หน้าแรก", "/"), *crumbs]
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": position, "name": name, "item": f"{root}{path}"}
            for position, (name, path) in enumerate(trail, start=1)
        ],
    }


def web_page(request, page_type, name):
    return {
        "@type": page_type,
        "name": name,
        "url": request.build_absolute_uri(request.path),
        "inLanguage": "th-TH",
        "isPartOf": {"@id": f"{base_url(request)}/#website"},
        "about": org_ref(request),
    }


def faq_page(request):
    return {
        "@type": "FAQPage",
        "url": request.build_absolute_uri(request.path),
        "inLanguage": "th-TH",
        "dateModified": content.FAQ_REVIEWED.isoformat(),
        "mainEntity": [
            {"@type": "Question", "name": item["q"], "acceptedAnswer": {"@type": "Answer", "text": item["a"]}}
            for item in content.faq_items()
        ],
    }


def services(request):
    rows = [
        ("ซื้อและเช่าทรัพย์", "ค้นหาและเปรียบเทียบทรัพย์ แล้วส่งข้อความถึงทีมงานได้ทันที"),
        ("ฝากขายและประเมินราคา", "ส่งข้อมูลทรัพย์ให้เจ้าหน้าที่ดูแลการขายแทนเจ้าของ"),
        ("ดูแลเอกสารและการโอน", "ช่วยดูแลเอกสารและประสานงานจนถึงวันโอน"),
    ]
    return [
        {
            "@type": "Service",
            "name": name,
            "description": description,
            "provider": org_ref(request),
            "areaServed": {"@type": "Country", "name": "ประเทศไทย"},
        }
        for name, description in rows
    ]


def guide_article(request, headline, description, modified):
    return {
        "@type": "Article",
        "headline": headline,
        "description": description,
        "url": request.build_absolute_uri(request.path),
        "inLanguage": "th-TH",
        "dateModified": modified.isoformat(),
        "author": org_ref(request),
        "publisher": org_ref(request),
    }


def article(request, item):
    root = base_url(request)
    data = {
        "@type": "Article",
        "headline": item.title[:110],
        "description": item.excerpt,
        "articleSection": item.category,
        "url": request.build_absolute_uri(item.get_absolute_url()),
        "mainEntityOfPage": request.build_absolute_uri(item.get_absolute_url()),
        "inLanguage": "th-TH",
        "datePublished": item.created_at.isoformat(),
        "dateModified": item.updated_at.isoformat(),
        "author": org_ref(request),
        "publisher": org_ref(request),
    }
    if item.cover_image:
        data["image"] = f"{root}{item.cover_image.url}"
    return data


def person(request):
    """ข้อมูลตรงกับหน้านามบัตรออนไลน์"""
    return {
        "@type": "ProfilePage",
        "url": request.build_absolute_uri(request.path),
        "mainEntity": {
            "@type": "Person",
            "name": "ภัคภพ แก้วเกตุ",
            "alternateName": "ณัฐ",
            "jobTitle": "CEO",
            "worksFor": org_ref(request),
        },
    }


def is_indexable(prop):
    """ทรัพย์ตัวอย่างและที่ไม่ได้เผยแพร่ต้องไม่ถูกแสดงเป็นข้อเสนอจริง"""
    return prop.status == Property.Status.PUBLISHED and not prop.is_sample


def _offer(prop, url):
    offer = {
        "@type": "Offer",
        "price": str(prop.price),
        "priceCurrency": "THB",
        "availability": "https://schema.org/InStock",
        "url": url,
    }
    if prop.property_type == Property.Type.RENT:
        offer["businessFunction"] = "http://purl.org/goodrelations/v1#LeaseOut"
        offer["priceSpecification"] = {
            "@type": "UnitPriceSpecification", "price": str(prop.price), "priceCurrency": "THB", "unitCode": "MON",
        }
    else:
        offer["businessFunction"] = "http://purl.org/goodrelations/v1#Sell"
    return offer


def _place(prop):
    place = {
        "@type": RESIDENCE_TYPES.get(prop.category.slug, "Place"),
        "name": prop.title,
        "address": {"@type": "PostalAddress", "addressLocality": prop.district or prop.location.name, "addressCountry": "TH"},
    }
    if prop.province:
        place["address"]["addressRegion"] = prop.province
    if place["@type"] != "Place":
        if prop.bedrooms:
            place["numberOfBedrooms"] = prop.bedrooms
        if prop.bathrooms:
            place["numberOfBathroomsTotal"] = prop.bathrooms
        if prop.size_usable:
            place["floorSize"] = {"@type": "QuantitativeValue", "value": float(prop.size_usable), "unitCode": "MTK"}
    if prop.has_coordinates:
        place["geo"] = {"@type": "GeoCoordinates", "latitude": prop.latitude, "longitude": prop.longitude}
    return place


def listing(request, prop, summary):
    if not is_indexable(prop):
        return None
    url = request.build_absolute_uri(prop.get_absolute_url())
    images = [request.build_absolute_uri(image.image.url) for image in prop.images.all()[:5]]
    data = {
        "@type": "RealEstateListing",
        "name": prop.title,
        "description": summary,
        "identifier": prop.display_code,
        "url": url,
        "inLanguage": "th-TH",
        "dateModified": prop.updated_at.isoformat(),
        "provider": org_ref(request),
        "mainEntity": _place(prop),
        "offers": _offer(prop, url),
    }
    if prop.published_at:
        data["datePosted"] = prop.published_at.isoformat()
    if images:
        data["image"] = images
    return data


def item_list(request, items):
    real = [item for item in items if not item.is_sample]
    if not real:
        return None
    return {
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": item.title,
                "url": request.build_absolute_uri(item.get_absolute_url()),
            }
            for position, item in enumerate(real, start=1)
        ],
    }
