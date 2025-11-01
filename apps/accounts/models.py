from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.common.models import BaseModel
from .managers import CustomUserManager


class User(AbstractBaseUser, BaseModel, PermissionsMixin):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(verbose_name=(_("Email address")), unique=True)
    phone = models.CharField(max_length=20, null=True, blank=True, unique=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    social_avatar = models.CharField(max_length=1000, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    bio = models.CharField(max_length=200, null=True, blank=True)
    dob = models.DateField(verbose_name=(_("Date of Birth")), null=True, blank=True)
    otp_code = models.IntegerField(null=True)
    otp_expires_at = models.DateTimeField(null=True)
    trust_token = models.CharField(max_length=10000, null=True, blank=True)
    trust_token_expires_at = models.DateTimeField(null=True, blank=True)
    biometrics_enabled = models.BooleanField(default=False)
    access = models.TextField(editable=False, null=True)
    refresh = models.TextField(editable=False, null=True)

    # Notifications
    push_enabled = models.BooleanField(
        default=True, help_text="Receive push notifications"
    )
    in_app_enabled = models.BooleanField(
        default=True, help_text="Receive in-app notifications"
    )
    email_enabled = models.BooleanField(
        default=True, help_text="Receive email notifications"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]
    objects = CustomUserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def avatar_url(self):
        try:
            url = self.avatar.url
        except:
            url = self.social_avatar  # from google
        return url

    def is_otp_expired(self):
        if self.otp_expires_at:
            now = timezone.now()
            return now > self.otp_expires_at
        return True

    def is_trust_token_expired(self):
        return (
            self.trust_token_expires_at and timezone.now() > self.trust_token_expires_at
        )
