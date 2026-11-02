from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, role=User.Role.ADMIN)
        return self._create(email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "ลูกค้า"
        AGENT = "AGENT", "นายหน้า"
        ADMIN = "ADMIN", "ผู้ดูแลระบบ"

    username = None
    email = models.EmailField("อีเมล", unique=True)
    phone = models.CharField("เบอร์โทรศัพท์", max_length=30, blank=True)
    # สมัครใหม่เป็นลูกค้าเสมอ สิทธิ์นายหน้า/แอดมินต้องให้จาก Dashboard เท่านั้น
    role = models.CharField("บทบาท", max_length=10, choices=Role.choices, default=Role.CUSTOMER)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        self.is_staff = self.is_superuser or self.role in (self.Role.AGENT, self.Role.ADMIN)
        super().save(*args, **kwargs)

    @property
    def is_site_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def display_name(self):
        return self.get_full_name() or self.email


class EmailOTP(models.Model):
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
