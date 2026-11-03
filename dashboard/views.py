import mimetypes
from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import generic
from django.views.decorators.http import require_POST

from accounts.models import User
from config.ajax import error
from chatbot.models import ChatSession
from chatbot.services.provider_service import provider_status
from inquiries.models import Inquiry
from properties.models import Category, Consignment, ConsignmentDeed, Location, Property, PropertyImage
from properties.services import consignment_service, image_service, listing_service
from reviews.models import Article, CustomerReview

from .forms import ArticleForm, CategoryForm, LocationForm, PropertyForm, UserRoleForm
from .selectors import overview_selector as selector


def staff_required(view):
    """ไม่ login ไปหน้า login, login แล้วแต่ไม่ใช่เจ้าหน้าที่ได้ 403"""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


class StaffMixin(AccessMixin):
    raise_exception = False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AdminOnlyMixin(StaffMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_site_admin:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


@staff_required
def home(request):
    return render(request, "dashboard/home.html", selector.overview())


# ประกาศ ------------------------------------------------------------------

class PropertyList(StaffMixin, generic.ListView):
    template_name = "dashboard/property_list.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        return selector.properties(self.request.GET.get("status", ""), self.request.GET.get("q", ""))

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            statuses=Property.Status.choices,
            current_status=self.request.GET.get("status", ""),
            q=self.request.GET.get("q", ""),
            **kwargs,
        )


class PropertyCreate(StaffMixin, generic.CreateView):
    model = Property
    form_class = PropertyForm
    template_name = "dashboard/property_form.html"
    extra_context = {"title": "เพิ่มประกาศ", "back": "dashboard:properties"}

    def get_success_url(self):
        messages.success(self.request, "สร้างประกาศแล้ว เพิ่มรูปภาพได้เลย")
        return reverse_lazy("dashboard:property_edit", args=[self.object.pk])


class PropertyEdit(StaffMixin, generic.UpdateView):
    model = Property
    form_class = PropertyForm
    template_name = "dashboard/property_edit.html"
    context_object_name = "property"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            images=self.object.images.all(),
            completeness=self.object.completeness(),
            **kwargs,
        )

    def get_success_url(self):
        messages.success(self.request, "บันทึกแล้ว")
        return reverse_lazy("dashboard:property_edit", args=[self.object.pk])


@require_POST
@staff_required
def property_set_status(request, pk):
    prop = get_object_or_404(Property, pk=pk)
    try:
        listing_service.set_status(prop, request.POST.get("status"))
    except listing_service.ListingError as exc:
        return error(str(exc))
    messages.success(request, f"เปลี่ยนสถานะ {prop.property_code} เป็น {prop.get_status_display()} แล้ว")
    return redirect("dashboard:property_edit", pk=prop.pk)


@require_POST
@staff_required
def property_delete(request, pk):
    prop = get_object_or_404(Property, pk=pk)
    code = prop.property_code
    prop.delete()
    messages.success(request, f"ลบประกาศ {code} แล้ว")
    return redirect("dashboard:properties")


@require_POST
@staff_required
def property_image_upload(request, pk):
    prop = get_object_or_404(Property, pk=pk)
    file = request.FILES.get("file")
    if not file:
        return error("ไม่พบไฟล์")
    try:
        image = image_service.add_property_image(prop, file)
    except image_service.UploadError as exc:
        return error(str(exc))
    return render(request, "properties/_image_tile.html", {
        "image": image,
        "delete_url_name": "dashboard:property_image_delete",
        "cover_url_name": "dashboard:property_image_cover",
    })


@require_POST
@staff_required
def property_image_delete(request, pk):
    image_service.delete_property_image(get_object_or_404(PropertyImage, pk=pk))
    return render(request, "properties/_empty.html")


@require_POST
@staff_required
def property_image_cover(request, pk):
    image = get_object_or_404(PropertyImage, pk=pk)
    image_service.set_cover_image(image)
    messages.success(request, "ตั้งรูปหน้าปกแล้ว")
    return redirect("dashboard:property_edit", pk=image.property_id)


# ฝากขาย ------------------------------------------------------------------

class ConsignmentList(StaffMixin, generic.ListView):
    template_name = "dashboard/consignment_list.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        return Consignment.objects.exclude(status=Consignment.Status.DRAFT)


@staff_required
def consignment_detail(request, pk):
    consignment = get_object_or_404(selector.consignment_detail(), pk=pk)
    return render(request, "dashboard/consignment_detail.html", {
        "c": consignment,
        "statuses": [s for s in Consignment.Status.choices if s[0] != Consignment.Status.DRAFT],
    })


@require_POST
@staff_required
def consignment_set_status(request, pk):
    consignment = get_object_or_404(Consignment, pk=pk)
    try:
        consignment_service.set_status(consignment, request.POST.get("status"))
    except consignment_service.ConsignmentError as exc:
        return error(str(exc))
    messages.success(request, "เปลี่ยนสถานะแล้ว")
    return redirect("dashboard:consignment_detail", pk=pk)


@require_POST
@staff_required
def consignment_convert(request, pk):
    consignment = get_object_or_404(Consignment, pk=pk)
    if consignment.converted_property_id:
        messages.info(request, "คำขอนี้แปลงเป็นประกาศไปแล้ว")
        return redirect("dashboard:property_edit", pk=consignment.converted_property_id)
    try:
        consignment_service.request_conversion(consignment, request.user)
    except consignment_service.ConsignmentError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "กำลังสร้างประกาศฉบับร่าง รูปจำนวนมากอาจใช้เวลาสักครู่ รีเฟรชเพื่อดูผล")
    return redirect("dashboard:consignment_detail", pk=pk)


@staff_required
def deed_file(request, pk):
    """ทางเดียวที่เปิดไฟล์โฉนดได้"""
    deed = get_object_or_404(ConsignmentDeed, pk=pk)
    content_type = mimetypes.guess_type(deed.file.name)[0] or "application/octet-stream"
    return FileResponse(deed.file.open("rb"), content_type=content_type, filename=deed.original_name)


# ข้อความ / รีวิว ----------------------------------------------------------

class InquiryList(StaffMixin, generic.ListView):
    template_name = "dashboard/inquiry_list.html"
    context_object_name = "items"
    paginate_by = 25
    queryset = Inquiry.objects.select_related("property")


@require_POST
@staff_required
def inquiry_toggle(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    inquiry.is_handled = not inquiry.is_handled
    inquiry.save(update_fields=["is_handled"])
    return render(request, "dashboard/_inquiry_status.html", {"item": inquiry})


class CustomerReviewList(StaffMixin, generic.ListView):
    template_name = "dashboard/customer_review_list.html"
    context_object_name = "items"
    paginate_by = 25
    model = CustomerReview


@require_POST
@staff_required
def customer_review_toggle(request, pk):
    review = get_object_or_404(CustomerReview, pk=pk)
    review.is_approved = not review.is_approved
    review.save(update_fields=["is_approved"])
    return render(request, "dashboard/_review_status.html", {"item": review})


@require_POST
@staff_required
def customer_review_delete(request, pk):
    get_object_or_404(CustomerReview, pk=pk).delete()
    return render(request, "properties/_empty.html")


# บทความ / หมวดหมู่ / ทำเล ใช้ CRUD ชุดเดียวกัน ------------------------------

class SimpleList(StaffMixin, generic.ListView):
    template_name = "dashboard/simple_list.html"
    context_object_name = "items"
    paginate_by = 25
    title = columns = edit_url = create_url = delete_url = None

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            title=self.title, edit_url=self.edit_url, create_url=self.create_url, delete_url=self.delete_url, **kwargs
        )


class SimpleCreate(StaffMixin, generic.CreateView):
    template_name = "dashboard/form.html"


class SimpleEdit(StaffMixin, generic.UpdateView):
    template_name = "dashboard/form.html"


def crud(model, form, title, list_name, queryset, template):
    common = {"model": model, "form_class": form, "success_url": reverse_lazy(f"dashboard:{list_name}")}
    extra = lambda heading: {"title": heading, "back": f"dashboard:{list_name}", "multipart": True}
    return {
        "list": SimpleList.as_view(
            queryset=queryset, template_name=template, title=title, edit_url=f"dashboard:{list_name}_edit",
            create_url=f"dashboard:{list_name}_new", delete_url=f"dashboard:{list_name}_delete",
        ),
        "new": SimpleCreate.as_view(extra_context=extra(f"เพิ่ม{title}"), **common),
        "edit": SimpleEdit.as_view(extra_context=extra(f"แก้ไข{title}"), **common),
        "delete": _simple_delete(model, list_name),
    }


def _simple_delete(model, list_name):
    @require_POST
    @staff_required
    def view(request, pk):
        try:
            get_object_or_404(model, pk=pk).delete()
            messages.success(request, "ลบแล้ว")
        except ProtectedError:
            messages.error(request, "ลบไม่ได้ เพราะยังมีประกาศใช้รายการนี้อยู่")
        return redirect(f"dashboard:{list_name}")

    return view


article_views = crud(Article, ArticleForm, "บทความ", "articles", selector.articles(), "dashboard/article_list.html")
category_views = crud(Category, CategoryForm, "หมวดหมู่", "categories", selector.categories(), "dashboard/category_list.html")
location_views = crud(Location, LocationForm, "ทำเล", "locations", selector.locations(), "dashboard/location_list.html")


# แชทบอท ------------------------------------------------------------------

class ChatList(StaffMixin, generic.ListView):
    template_name = "dashboard/chat_list.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        return selector.chat_sessions()

    def get_context_data(self, **kwargs):
        return super().get_context_data(providers=provider_status(), **kwargs)


@staff_required
def chat_detail(request, pk):
    session = get_object_or_404(ChatSession, pk=pk)
    chat_messages = session.messages.prefetch_related("suggestions")
    return render(request, "dashboard/chat_detail.html", {"session": session, "chat_messages": chat_messages})


# ผู้ใช้งาน (เฉพาะแอดมิน) ----------------------------------------------------

class UserList(AdminOnlyMixin, generic.ListView):
    template_name = "dashboard/user_list.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        items = User.objects.order_by("-date_joined")
        if q := self.request.GET.get("q"):
            items = items.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        return items

    def get_context_data(self, **kwargs):
        return super().get_context_data(q=self.request.GET.get("q", ""), **kwargs)


class UserEdit(AdminOnlyMixin, generic.UpdateView):
    model = User
    form_class = UserRoleForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:users")
    extra_context = {"title": "แก้ไขผู้ใช้งาน", "back": "dashboard:users", "multipart": False}
    context_object_name = "managed_user"
