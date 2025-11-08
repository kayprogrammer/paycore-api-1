from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.common.models import BaseModel

User = get_user_model()


class NotificationType(models.TextChoices):
    PAYMENT = "payment", "Payment"
    TRANSFER = "transfer", "Transfer"
    LOAN = "loan", "Loan"
    INVESTMENT = "investment", "Investment"
    CARD = "card", "Card"
    KYC = "kyc", "KYC/Compliance"
    BILL = "bill", "Bill Payment"
    WALLET = "wallet", "Wallet"
    ACCOUNT = "account", "Account"
    SECURITY = "security", "Security"
    PROMOTION = "promotion", "Promotion"
    SYSTEM = "system", "System"
    OTHER = "other", "Other"


class NotificationPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class Notification(BaseModel):
    """
    Notification model
    Supports real-time delivery via WebSockets and push notifications via FCM
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications", db_index=True
    )

    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.OTHER,
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=NotificationPriority.choices,
        default=NotificationPriority.MEDIUM,
    )

    # Status tracking
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Delivery tracking
    sent_via_push = models.BooleanField(default=False)
    push_sent_at = models.DateTimeField(null=True, blank=True)
    sent_via_websocket = models.BooleanField(default=False)
    websocket_sent_at = models.DateTimeField(null=True, blank=True)

    # Related object (polymorphic reference)
    related_object_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Model name: Payment, Loan, Card, etc.",
        null=True,
    )
    related_object_id = models.CharField(
        max_length=100, blank=True, help_text="UUID or ID of related object", null=True
    )

    # Action data (for deep linking in mobile apps)
    action_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Deep link or URL to open when notification is tapped",
    )
    action_data = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Additional data for handling notification action",
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Additional metadata for the notification",
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiration date for time-sensitive notifications",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read", "-created_at"]),
            models.Index(fields=["notification_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()

    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class NotificationTemplate(BaseModel):
    """
    Reusable notification templates
    For consistent messaging across the platform
    """

    name = models.CharField(max_length=100, unique=True)
    notification_type = models.CharField(
        max_length=20, choices=NotificationType.choices
    )
    priority = models.CharField(
        max_length=10,
        choices=NotificationPriority.choices,
        default=NotificationPriority.MEDIUM,
    )

    # Template content (supports variable substitution)
    title_template = models.CharField(
        max_length=200, help_text="Use {{variable}} for substitution"
    )
    message_template = models.TextField(help_text="Use {{variable}} for substitution")

    # Default action
    action_url_template = models.CharField(
        max_length=500, blank=True, help_text="Use {{variable}} for substitution"
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def render(self, context: dict):
        """Render template with context variables"""
        import re

        def replace_vars(template: str, ctx: dict):
            return re.sub(
                r"\{\{(\w+)\}\}",
                lambda m: str(ctx.get(m.group(1), m.group(0))),
                template,
            )

        return {
            "title": replace_vars(self.title_template, context),
            "message": replace_vars(self.message_template, context),
            "action_url": (
                replace_vars(self.action_url_template, context)
                if self.action_url_template
                else ""
            ),
        }
