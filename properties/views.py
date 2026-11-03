from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_POST

from config.ajax import ajax_login_required, error, is_ajax
from inquiries.forms import InquiryForm
from pages.services import schema_service

from .forms import ConsignmentForm, ListingForm, SearchForm
from .models import Consignment, ConsignmentDeed, ConsignmentImage, Property, PropertyImage
from .selectors import property_selector as selector
from .services import consignment_service, image_service, listing_service, loan_service, seo_service

ADVANCED_FILTERS = ("category", "location", "province", "price_min", "price_max", "bedrooms", "sub_type", "zoning")


def property_list(request):
    form = SearchForm(request.GET, provinces=selector.provinces())
    form.is_valid()  # ค่าที่ผิดรูปถูกข้าม ไม่ทำให้หน้าเว็บ error
    params = request.GET.copy()
    params.pop("page", None)
    page = Paginator(selector.search(form.cleaned_data), 12).get_page(request.GET.get("page"))
    context = {
        "form": form,
        "page": page,
        "schema": schema_service.to_script(
            schema_service.item_list(request, page.object_list),
            schema_service.breadcrumbs(request, ("รายการทรัพย์", request.path)),
        ),
        "querystring": params.urlencode(),
        "bookmarked": selector.bookmarked_ids(request.user),
        "has_filters": any(form.cleaned_data.get(name) not in (None, "") for name in ADVANCED_FILTERS),
    }
    response = render(request, "properties/_results.html" if is_ajax(request) else "properties/list.html", context)
    # URL เดียวตอบได้ทั้งหน้าเต็มและบางส่วน ต้องบอก cache ไม่ให้สลับกัน
    patch_vary_headers(response, ["X-Requested-With"])
    return response


def property_detail(request, slug):
    prop = selector.detail_or_none(slug, request.user)
    if prop is None:
        raise Http404
    summary = seo_service.summary(prop)
    schema = None
    if schema_service.is_indexable(prop):
        schema = schema_service.to_script(
            schema_service.listing(request, prop, summary),
            schema_service.breadcrumbs(
                request, ("รายการทรัพย์", reverse("properties:list")), (prop.title, prop.get_absolute_url()),
            ),
        )
    return render(request, "properties/detail.html", {
        "property": prop,
        "summary": summary,
        "schema": schema,
        "bookmarked": selector.bookmarked_ids(request.user),
        "inquiry_form": InquiryForm(initial={
            "property": prop.pk,
            "message": f"สนใจทรัพย์รหัส {prop.display_code} - {prop.title}",
        }),
        "related": selector.related(prop),
        "loan": loan_service.for_property(prop),
    })


def compare(request):
    ids = [int(part) for part in request.GET.get("ids", "").split(",") if part.isdigit()][: settings.MAX_COMPARE_ITEMS]
    return render(request, "properties/compare.html", {"items": selector.compare_items(ids)})


@login_required
def favorites(request):
    return render(request, "properties/favorites.html", {
        "items": selector.favorites(request.user),
        "bookmarked": selector.bookmarked_ids(request.user),
    })


@require_POST
@ajax_login_required
def toggle_bookmark(request, pk):
    prop = get_object_or_404(Property.objects.only("id"), pk=pk, status=Property.Status.PUBLISHED)
    is_bookmarked = listing_service.toggle_bookmark(request.user, prop)
    return render(request, "properties/_bookmark_button.html", {"property": prop, "is_bookmarked": is_bookmarked})


# ลงประกาศเอง ------------------------------------------------------------

def _own_listing(request, code):
    return get_object_or_404(Property, property_code=code, owner=request.user)


@login_required
def my_listings(request):
    return render(request, "properties/my_listings.html", {
        "listings": selector.my_listings(request.user),
        "consignments": selector.my_consignments(request.user),
    })


@login_required
def sell(request):
    user = request.user
    form = ListingForm(request.POST or None, initial={"seller_name": user.get_full_name(), "seller_phone": user.phone})
    if request.method == "POST" and form.is_valid():
        prop = listing_service.create_listing(form, user)
        return redirect("properties:sell_images", code=prop.property_code)
    return render(request, "properties/sell.html", {"form": form})


@login_required
def sell_images(request, code):
    prop = _own_listing(request, code)
    if prop.status != Property.Status.DRAFT:
        messages.info(request, "ประกาศนี้ส่งตรวจสอบแล้ว")
        return redirect("properties:my_listings")
    return render(request, "properties/sell_images.html", {
        "property": prop,
        "images": prop.images.all(),
        "min_images": settings.MIN_LISTING_IMAGES,
        "max_images": settings.MAX_LISTING_IMAGES,
    })


@require_POST
@ajax_login_required
def sell_image_upload(request, code):
    prop = _own_listing(request, code)
    if prop.status != Property.Status.DRAFT:
        return error("ประกาศนี้ส่งตรวจสอบแล้ว")
    file = request.FILES.get("file")
    if not file:
        return error("ไม่พบไฟล์")
    try:
        image = image_service.add_property_image(prop, file)
    except image_service.UploadError as exc:
        return error(str(exc))
    return render(request, "properties/_image_tile.html", {
        "image": image,
        "delete_url_name": "properties:sell_image_delete",
    })


@require_POST
@ajax_login_required
def sell_image_delete(request, pk):
    image = get_object_or_404(PropertyImage, pk=pk, property__owner=request.user, property__status=Property.Status.DRAFT)
    image_service.delete_property_image(image)
    return render(request, "properties/_empty.html")


@require_POST
@login_required
def sell_submit(request, code):
    prop = _own_listing(request, code)
    try:
        listing_service.submit_for_review(prop)
    except listing_service.ListingError as exc:
        messages.error(request, str(exc))
        return redirect("properties:sell_images", code=code)
    messages.success(request, "ส่งประกาศแล้ว เจ้าหน้าที่จะตรวจสอบก่อนเผยแพร่")
    return redirect("properties:my_listings")


# ฝากขาย ------------------------------------------------------------------

def _own_draft_consignment(request, pk):
    return get_object_or_404(Consignment, pk=pk, owner=request.user, status=Consignment.Status.DRAFT)


@login_required
def consignment_new(request):
    user = request.user
    form = ConsignmentForm(request.POST or None, initial={
        "owner_name": user.get_full_name(), "owner_phone": user.phone, "owner_email": user.email,
    })
    if request.method == "POST" and form.is_valid():
        consignment = consignment_service.create_consignment(form, user)
        return redirect("properties:consignment_files", pk=consignment.pk)
    return render(request, "properties/consignment.html", {"form": form})


@login_required
def consignment_files(request, pk):
    consignment = _own_draft_consignment(request, pk)
    return render(request, "properties/consignment_files.html", {
        "consignment": consignment,
        "images": consignment.images.all(),
        "deeds": consignment.deeds.all(),
        "min_images": settings.MIN_LISTING_IMAGES,
        "max_images": settings.MAX_LISTING_IMAGES,
        "max_deeds": settings.MAX_DEED_FILES,
    })


@require_POST
@ajax_login_required
def consignment_upload(request, pk, kind):
    consignment = _own_draft_consignment(request, pk)
    file = request.FILES.get("file")
    if not file:
        return error("ไม่พบไฟล์")
    try:
        if kind == "image":
            image = image_service.add_consignment_image(consignment, file)
            return render(request, "properties/_consignment_image_tile.html", {"image": image})
        deed = image_service.add_consignment_deed(consignment, file)
        return render(request, "properties/_deed_row.html", {"deed": deed})
    except image_service.UploadError as exc:
        return error(str(exc))


@require_POST
@ajax_login_required
def consignment_image_delete(request, pk):
    get_object_or_404(ConsignmentImage, pk=pk, consignment__owner=request.user, consignment__status=Consignment.Status.DRAFT).delete()
    return render(request, "properties/_empty.html")


@require_POST
@ajax_login_required
def consignment_deed_delete(request, pk):
    get_object_or_404(ConsignmentDeed, pk=pk, consignment__owner=request.user, consignment__status=Consignment.Status.DRAFT).delete()
    return render(request, "properties/_empty.html")


@require_POST
@login_required
def consignment_submit(request, pk):
    consignment = _own_draft_consignment(request, pk)
    try:
        consignment_service.submit(consignment)
    except consignment_service.ConsignmentError as exc:
        messages.error(request, str(exc))
        return redirect("properties:consignment_files", pk=pk)
    messages.success(request, "ส่งเรื่องฝากขายแล้ว เจ้าหน้าที่จะติดต่อกลับ")
    return redirect("properties:my_listings")
