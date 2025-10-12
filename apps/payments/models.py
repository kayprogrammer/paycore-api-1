from autoslug import AutoSlugField
from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel
import uuid
import secrets


class PaymentLinkStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    EXPIRED = "expired", "Expired"
    COMPLETED = "completed", "Completed"


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"
    PAID = "paid", "Paid"
    PARTIALLY_PAID = "partially_paid", "Partially Paid"
    OVERDUE = "overdue", "Overdue"
    CANCELLED = "cancelled", "Cancelled"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class PaymentLink(BaseModel):
    """
    Payment Links - Shareable URLs for collecting payments.

    Merchants can create payment links to collect payments from customers
    without requiring integration. Links can be shared via email, SMS, or social media.
    """

    link_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="payment_links"
    )
    wallet = models.ForeignKey(
        "wallets.Wallet", on_delete=models.CASCADE, related_name="payment_links"
    )

    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    slug = AutoSlugField(
        max_length=100, unique=True, db_index=True, populate_from="title"
    )

    amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    is_amount_fixed = models.BooleanField(default=True)
    min_amount = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    max_amount = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=PaymentLinkStatus.choices,
        default=PaymentLinkStatus.ACTIVE,
    )
    is_single_use = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    redirect_url = models.URLField(null=True, blank=True)

    logo_url = models.URLField(null=True, blank=True)
    brand_color = models.CharField(max_length=7, default="#3B82F6")  # Hex color

    views_count = models.IntegerField(default=0)
    payments_count = models.IntegerField(default=0)
    total_collected = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.link_id}"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_active(self):
        return (
            self.status == PaymentLinkStatus.ACTIVE
            and not self.is_expired
            and (not self.is_single_use or self.payments_count == 0)
        )


class Invoice(BaseModel):
    """
    Invoices - Professional invoices for billing customers.

    Create, send, and track invoices with line items, taxes, and due dates.
    """

    invoice_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="invoices"
    )
    wallet = models.ForeignKey(
        "wallets.Wallet", on_delete=models.CASCADE, related_name="invoices"
    )

    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, null=True, blank=True)
    customer_address = models.TextField(null=True, blank=True)

    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=20, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=20, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2)

    status = models.CharField(
        max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT
    )
    issue_date = models.DateField()
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)

    payment_link = models.ForeignKey(
        PaymentLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["invoice_number"]),
            models.Index(fields=["status", "-due_date"]),
            models.Index(fields=["customer_email"]),
        ]

    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.customer_name}"

    @property
    def is_overdue(self):
        if self.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]:
            return False
        return timezone.now().date() > self.due_date


class InvoiceItem(BaseModel):
    """
    Invoice Line Items.
    """

    item_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")

    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=20, decimal_places=2)
    amount = models.DecimalField(max_digits=20, decimal_places=2)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.description} - {self.amount}"


class Payment(BaseModel):
    """
    Payment Transactions - Records of payments made through links or invoices.
    """

    payment_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    payment_link = models.ForeignKey(
        PaymentLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    transaction = models.OneToOneField(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merchant_payment",
    )

    payer_name = models.CharField(max_length=200, null=True, blank=True)
    payer_email = models.EmailField(null=True, blank=True)
    payer_phone = models.CharField(max_length=20, null=True, blank=True)
    payer_wallet = models.ForeignKey(
        "wallets.Wallet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merchant_payments_made",
    )

    merchant_user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="merchant_payments"
    )
    merchant_wallet = models.ForeignKey(
        "wallets.Wallet",
        on_delete=models.CASCADE,
        related_name="merchant_payments_received",
    )

    amount = models.DecimalField(max_digits=20, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=20, decimal_places=2)  # amount - fee

    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )

    reference = models.CharField(max_length=100, unique=True, db_index=True)
    external_reference = models.CharField(max_length=200, null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant_user", "-created_at"]),
            models.Index(fields=["reference"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"Payment {self.reference} - {self.amount}"


class MerchantAPIKey(BaseModel):
    """
    API Keys for merchant integrations.

    Merchants can generate API keys to accept payments programmatically.
    """

    key_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="api_keys"
    )

    name = models.CharField(max_length=100)
    key = models.CharField(max_length=64, unique=True, db_index=True)
    prefix = models.CharField(max_length=8)  # First 8 chars for display

    is_active = models.BooleanField(default=True)
    is_test_mode = models.BooleanField(default=False)

    can_create_links = models.BooleanField(default=True)
    can_create_invoices = models.BooleanField(default=True)
    can_view_payments = models.BooleanField(default=True)

    last_used_at = models.DateTimeField(null=True, blank=True)
    requests_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["key"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.prefix}..."

    def save(self, *args, **kwargs):
        if not self.key:
            # Generate API key: pk_live_xxxxx or pk_test_xxxxx
            mode = "test" if self.is_test_mode else "live"
            random_key = secrets.token_urlsafe(32)
            self.key = f"pk_{mode}_{random_key}"
            self.prefix = self.key[:8]
        super().save(*args, **kwargs)
