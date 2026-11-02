from django import forms

from config.forms import BootstrapFormMixin, HoneypotMixin

from properties.models import Property

from .models import Inquiry


class InquiryForm(BootstrapFormMixin, HoneypotMixin, forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = ["property", "name", "email", "phone", "message"]
        widgets = {"property": forms.HiddenInput, "message": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ส่งข้อความได้เฉพาะทรัพย์ที่เผยแพร่อยู่ และไม่ให้ dropdown โหลดทรัพย์ทั้งหมด
        self.fields["property"].queryset = Property.objects.filter(status=Property.Status.PUBLISHED).only("id")
