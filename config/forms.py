from django import forms


class BootstrapFormMixin:
    """ใส่ class ของ Bootstrap ให้ทุก field ฟอร์มทั้งเว็บจึงหน้าตาเหมือนกัน"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.HiddenInput):
                continue
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


class HoneypotMixin(forms.Form):
    """ช่องซ่อนกันบอตในฟอร์มสาธารณะ คนจริงมองไม่เห็นจึงไม่กรอก"""

    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("ไม่สามารถส่งข้อมูลได้")
        return ""
