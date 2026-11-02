import logging

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm

from django.template.loader import render_to_string
from kombu.exceptions import OperationalError

from accounts.tasks import send_email
from config.forms import BootstrapFormMixin

from .models import User

logger = logging.getLogger(__name__)


class LoginForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(label="อีเมล")
    password = forms.CharField(label="รหัสผ่าน", widget=forms.PasswordInput)

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class RegisterForm(BootstrapFormMixin, forms.ModelForm):
    password1 = forms.CharField(label="รหัสผ่าน", widget=forms.PasswordInput)
    password2 = forms.CharField(label="ยืนยันรหัสผ่าน", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]
        labels = {"first_name": "ชื่อ", "last_name": "นามสกุล"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def validate_unique(self):
        # อีเมลที่สมัครค้างไว้แต่ยังไม่ยืนยัน สมัครซ้ำได้ ตรวจเองใน clean_email
        pass

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        self.pending_user = User.objects.filter(email=email).first()
        if self.pending_user and self.pending_user.is_active:
            raise forms.ValidationError("อีเมลนี้ถูกใช้งานแล้ว")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p1 != p2:
            self.add_error("password2", "รหัสผ่านไม่ตรงกัน")
        elif p1:
            try:
                password_validation.validate_password(p1, self.instance)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = getattr(self, "pending_user", None) or self.instance
        for field in self.Meta.fields:
            setattr(user, field, self.cleaned_data[field])
        user.is_active = False
        user.set_password(self.cleaned_data["password1"])
        user.save()
        return user


class VerifyForm(BootstrapFormMixin, forms.Form):
    code = forms.CharField(
        label="รหัส OTP 6 หลัก",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}),
    )


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone"]
        labels = {"first_name": "ชื่อ", "last_name": "นามสกุล"}


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class StyledPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        # ส่งเบื้องหลังแทนการส่งในคำขอ
        subject = "".join(render_to_string(subject_template_name, context).splitlines())
        try:
            send_email.delay(subject, render_to_string(email_template_name, context), [to_email])
        except OperationalError:
            # ตอบหน้าเดิมเสมอ เพื่อไม่ให้รู้ว่าอีเมลนี้มีบัญชีหรือไม่
            logger.exception("ส่งงานอีเมลรีเซ็ตรหัสผ่านเข้าคิวไม่สำเร็จ")


class StyledSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass
