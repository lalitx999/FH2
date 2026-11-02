import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from accounts.models import EmailOTP, User
from accounts.services.otp_service import MAX_ATTEMPTS

PASSWORD = "pw-Long-12345"


class RegisterOTPTests(TestCase):
    def setUp(self):
        cache.clear()

    def register(self, email="new@example.com"):
        return self.client.post("/register/", {
            "first_name": "ก", "last_name": "ข", "email": email, "phone": "081",
            "password1": PASSWORD, "password2": PASSWORD,
        })

    def code_from_mail(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def test_new_user_is_customer_and_inactive_until_verified(self):
        self.assertRedirects(self.register(), "/verify-email/")
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.is_active)
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_staff)
        self.assertEqual(len(mail.outbox), 1)

        self.client.post("/verify-email/", {"code": self.code_from_mail()})
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_otp_is_not_stored_in_plain_text(self):
        self.register()
        self.assertNotEqual(EmailOTP.objects.get().code_hash, self.code_from_mail())

    def test_wrong_code_locks_after_max_attempts(self):
        self.register()
        code = self.code_from_mail()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(MAX_ATTEMPTS):
            self.client.post("/verify-email/", {"code": wrong})
        self.client.post("/verify-email/", {"code": code})
        self.assertFalse(User.objects.get(email="new@example.com").is_active)

    def test_expired_code_rejected(self):
        self.register()
        EmailOTP.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.client.post("/verify-email/", {"code": self.code_from_mail()})
        self.assertFalse(User.objects.get(email="new@example.com").is_active)

    def test_used_code_cannot_be_reused(self):
        self.register()
        code = self.code_from_mail()
        self.client.post("/verify-email/", {"code": code})
        User.objects.filter(email="new@example.com").update(is_active=False)
        self.client.logout()
        session = self.client.session
        session["pending_email"] = "new@example.com"
        session.save()
        self.client.post("/verify-email/", {"code": code})
        self.assertFalse(User.objects.get(email="new@example.com").is_active)

    def test_resend_has_cooldown(self):
        self.register()
        response = self.client.post("/verify-email/resend/")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 1)

    def test_taken_email_rejected_but_unverified_can_retry(self):
        User.objects.create_user("used@example.com", PASSWORD)
        self.assertEqual(self.register("used@example.com").status_code, 200)
        self.register("again@example.com")
        self.assertEqual(self.register("again@example.com").status_code, 302)
        self.assertEqual(User.objects.filter(email="again@example.com").count(), 1)

    def test_unverified_login_goes_to_verify(self):
        self.register()
        EmailOTP.objects.all().delete()
        response = self.client.post("/login/", {"email": "new@example.com", "password": PASSWORD})
        self.assertRedirects(response, "/verify-email/")
        self.assertNotIn("_auth_user_id", self.client.session)


class LoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("user@example.com", PASSWORD)

    def test_auth_pages_use_their_own_photo_before_the_form(self):
        for url, photo in (("/login/", "images/auth-login-800.webp"), ("/register/", "images/auth-register-800.webp")):
            html = self.client.get(url).content.decode()
            self.assertIn(photo, html)
            self.assertLess(html.index("fh-auth-photo"), html.index("fh-auth-form"))

    def test_login_is_case_insensitive_on_email(self):
        response = self.client.post("/login/", {"email": "USER@example.com", "password": PASSWORD})
        self.assertRedirects(response, "/")

    def test_wrong_password(self):
        response = self.client.post("/login/", {"email": "user@example.com", "password": "nope"})
        self.assertContains(response, "ไม่ถูกต้อง")

    def test_next_blocks_external_redirect(self):
        response = self.client.post("/login/", {"email": "user@example.com", "password": PASSWORD, "next": "https://evil.example.com/"})
        self.assertRedirects(response, "/")

    def test_staff_lands_on_dashboard(self):
        User.objects.create_user("agent@example.com", PASSWORD, role=User.Role.AGENT)
        response = self.client.post("/login/", {"email": "agent@example.com", "password": PASSWORD})
        self.assertRedirects(response, "/dashboard/")

    def test_password_reset_mail_contains_working_link(self):
        self.client.post("/password-reset/", {"email": "user@example.com"})
        link = re.search(r"http://testserver(/password-reset/\S+)", mail.outbox[-1].body).group(1)
        self.assertEqual(self.client.get(link, follow=True).status_code, 200)

    def test_login_locks_after_repeated_failures_but_keeps_other_accounts_open(self):
        for _ in range(5):
            self.client.post("/login/", {"email": "user@example.com", "password": "nope"})
        response = self.client.post("/login/", {"email": "user@example.com", "password": PASSWORD})
        self.assertContains(response, "ลองผิดหลายครั้ง")
        self.assertNotIn("_auth_user_id", self.client.session)
        User.objects.create_user("other@example.com", PASSWORD)
        response = self.client.post("/login/", {"email": "other@example.com", "password": PASSWORD})
        self.assertRedirects(response, "/")

    def test_new_accounts_cannot_escalate_role_through_register(self):
        self.client.post("/register/", {
            "first_name": "ก", "last_name": "ข", "email": "x@example.com", "phone": "081",
            "password1": PASSWORD, "password2": PASSWORD, "role": "ADMIN", "is_staff": "on",
        })
        user = User.objects.get(email="x@example.com")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_staff)
