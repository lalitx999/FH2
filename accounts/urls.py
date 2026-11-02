from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import forms, views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("verify-email/", views.verify_email_view, name="verify_email"),
    path("verify-email/resend/", views.resend_otp_view, name="resend_otp"),
    path("profile/", views.profile_view, name="profile"),
    path(
        "profile/password/",
        auth_views.PasswordChangeView.as_view(
            form_class=forms.StyledPasswordChangeForm,
            template_name="accounts/form_page.html",
            success_url=reverse_lazy("accounts:profile"),
            extra_context={"title": "เปลี่ยนรหัสผ่าน", "submit": "บันทึกรหัสผ่าน"},
        ),
        name="password_change",
    ),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            form_class=forms.StyledPasswordResetForm,
            template_name="accounts/form_page.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
            extra_context={"title": "ลืมรหัสผ่าน", "submit": "ส่งลิงก์ตั้งรหัสใหม่"},
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/message_page.html",
            extra_context={"title": "ตรวจสอบอีเมลของคุณ", "body": "หากอีเมลนี้มีอยู่ในระบบ เราได้ส่งลิงก์ตั้งรหัสผ่านใหม่ไปให้แล้ว"},
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            form_class=forms.StyledSetPasswordForm,
            template_name="accounts/form_page.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
            extra_context={"title": "ตั้งรหัสผ่านใหม่", "submit": "บันทึกรหัสผ่าน"},
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/message_page.html",
            extra_context={"title": "ตั้งรหัสผ่านใหม่แล้ว", "body": "คุณสามารถเข้าสู่ระบบด้วยรหัสผ่านใหม่ได้เลย"},
        ),
        name="password_reset_complete",
    ),
]
