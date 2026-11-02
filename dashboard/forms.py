from django import forms

from accounts.models import User
from config.forms import BootstrapFormMixin
from properties.forms import PropertyExtrasMixin
from properties.models import Category, Location, Property
from reviews.models import Article


class PropertyForm(BootstrapFormMixin, PropertyExtrasMixin, forms.ModelForm):
    class Meta:
        model = Property
        exclude = ["owner", "published_at"]
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}


class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "code_prefix", "sort_order"]


class LocationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name"]


class ArticleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Article
        fields = ["kind", "category", "title", "excerpt", "content", "cover_image", "property", "is_published"]
        widgets = {"excerpt": forms.Textarea(attrs={"rows": 2}), "content": forms.Textarea(attrs={"rows": 12})}


class UserRoleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "role", "is_active"]
        labels = {"first_name": "ชื่อ", "last_name": "นามสกุล", "is_active": "เปิดใช้งาน"}
