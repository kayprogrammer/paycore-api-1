from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel
from decimal import Decimal
import uuid
from autoslug import AutoSlugField


class BillCategory(models.TextChoices):
    AIRTIME = "airtime", "Airtime Recharge"
    DATA = "data", "Data Bundle"
    ELECTRICITY = "electricity", "Electricity Bill"
    CABLE_TV = "cable_tv", "Cable TV Subscription"
    INTERNET = "internet", "Internet Service"
    WATER = "water", "Water Bill"
    WASTE = "waste", "Waste Management"
    EDUCATION = "education", "Education/School Fees"
    GOVERNMENT = "government", "Government Services"
    INSURANCE = "insurance", "Insurance Premium"
    TAX = "tax", "Tax Payment"
    OTHER = "other", "Other Bills"


class BillPaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    REVERSED = "reversed", "Reversed"
    CANCELLED = "cancelled", "Cancelled"


class BillProviderFeeType(models.TextChoices):
    FLAT = "flat", "Flat Fee"
    PERCENTAGE = "percentage", "Percentage"
    NONE = "none", "No Fee"


class BillProvider(BaseModel):
    """
    Bill payment service providers.

    Examples:
    - Airtime: MTN, Airtel, Glo, 9mobile
    - Electricity: EKEDC, IKEDC, AEDC, etc.
    - Cable TV: DSTV, GOtv, StarTimes
    - Internet: Spectranet, Smile, Swift
    """

    provider_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    name = models.CharField(max_length=100)
    slug = AutoSlugField(max_length=100, unique=True, populate_from="name")
    category = models.CharField(max_length=50, choices=BillCategory.choices)
    provider_code = models.CharField(
        max_length=50, unique=True, help_text="Code used by payment gateway"
    )
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(
        default=True, help_text="Temporarily unavailable"
    )

    logo_url = models.URLField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    supports_amount_range = models.BooleanField(
        default=False, help_text="User can enter custom amount"
    )
    min_amount = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    max_amount = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )

    fee_type = models.CharField(
        max_length=20,
        choices=BillProviderFeeType.choices,
        default=BillProviderFeeType.FLAT,
    )
    fee_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    fee_cap = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum fee amount",
    )

    # Metadata
    requires_customer_validation = models.BooleanField(
        default=False, help_text="Validate customer before payment"
    )
    validation_fields = models.JSONField(
        default=dict, blank=True, help_text="Required fields for validation"
    )
    extra_fields = models.JSONField(
        default=dict, blank=True, help_text="Additional fields required"
    )

    class Meta:
        ordering = ["category", "name"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["provider_code"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def calculate_fee(self, amount: Decimal) -> Decimal:
        if self.fee_type == BillProviderFeeType.NONE:
            return Decimal("0")
        if self.fee_type == BillProviderFeeType.FLAT:
            return self.fee_amount

        if self.fee_type == BillProviderFeeType.PERCENTAGE:
            fee = amount * (self.fee_amount / 100)
            if self.fee_cap:
                return min(fee, self.fee_cap)
            return fee

        return Decimal("0")


class BillPackage(BaseModel):
    package_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    provider = models.ForeignKey(
        BillProvider, on_delete=models.CASCADE, related_name="packages"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=100, help_text="Package code from provider")
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    description = models.TextField(null=True, blank=True)
    validity_period = models.CharField(
        max_length=100, null=True, blank=True, help_text="e.g., '30 days', '1 month'"
    )
    benefits = models.JSONField(
        default=list, blank=True, help_text="List of package benefits"
    )
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["provider", "display_order", "amount"]
        indexes = [
            models.Index(fields=["provider", "is_active"]),
            models.Index(fields=["code"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "code"], name="unique_package_provider_code"
            )
        ]

    def __str__(self):
        return f"{self.provider.name} - {self.name} (₦{self.amount})"


class BillPayment(BaseModel):
    payment_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="bill_payments"
    )
    wallet = models.ForeignKey(
        "wallets.Wallet", on_delete=models.CASCADE, related_name="bill_payments"
    )
    transaction = models.OneToOneField(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bill_payment",
    )
    provider = models.ForeignKey(
        BillProvider, on_delete=models.PROTECT, related_name="payments"
    )
    package = models.ForeignKey(
        BillPackage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    category = models.CharField(max_length=50, choices=BillCategory.choices)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=20, decimal_places=2)  # amount + fee
    customer_id = models.CharField(
        max_length=200, help_text="Customer ID/Number (meter number, phone, smartcard)"
    )
    customer_name = models.CharField(max_length=200, null=True, blank=True)
    customer_email = models.EmailField(null=True, blank=True)
    customer_phone = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=BillPaymentStatus.choices,
        default=BillPaymentStatus.PENDING,
    )
    provider_reference = models.CharField(
        max_length=200, null=True, blank=True, db_index=True
    )
    provider_response = models.JSONField(default=dict, blank=True, null=True)
    token = models.CharField(max_length=500, null=True, blank=True)
    token_units = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Units purchased (kWh, GB, etc.)",
    )
    description = models.TextField(null=True, blank=True)
    extra_data = models.JSONField(
        default=dict, blank=True, help_text="Additional payment data", null=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    save_beneficiary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["provider", "-created_at"]),
            models.Index(fields=["provider_reference"]),
            models.Index(fields=["customer_id"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.provider.name} - ₦{self.amount}"

    @property
    def is_successful(self):
        return self.status == BillPaymentStatus.COMPLETED

    @property
    def is_pending(self):
        return self.status in [BillPaymentStatus.PENDING, BillPaymentStatus.PROCESSING]

    def mark_completed(self):
        self.status = BillPaymentStatus.COMPLETED
        self.completed_at = timezone.now()

    def mark_failed(self, reason: str):
        self.status = BillPaymentStatus.FAILED
        self.failed_at = timezone.now()
        self.failure_reason = reason


class BillBeneficiary(BaseModel):
    beneficiary_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="bill_beneficiaries"
    )
    provider = models.ForeignKey(
        BillProvider, on_delete=models.CASCADE, related_name="beneficiaries"
    )
    nickname = models.CharField(
        max_length=100, help_text="User-friendly name (e.g., 'Home Electricity')"
    )
    customer_id = models.CharField(max_length=200)
    customer_name = models.CharField(max_length=200, null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-last_used_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-last_used_at"]),
            models.Index(fields=["user", "provider"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider", "customer_id"],
                name="unique_user_provider_customer_beneficiary",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.nickname}"

    def increment_usage(self):
        self.usage_count += 1
        self.last_used_at = timezone.now()


class BillPaymentSchedule(BaseModel):
    schedule_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="bill_schedules"
    )
    provider = models.ForeignKey(
        BillProvider, on_delete=models.CASCADE, related_name="schedules"
    )
    wallet = models.ForeignKey(
        "wallets.Wallet", on_delete=models.CASCADE, related_name="bill_schedules"
    )
    customer_id = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    frequency = models.CharField(
        max_length=20,
        choices=[
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
        ],
    )
    next_payment_date = models.DateField()
    is_active = models.BooleanField(default=True)
    is_paused = models.BooleanField(default=False)
    total_payments = models.IntegerField(default=0)
    successful_payments = models.IntegerField(default=0)
    failed_payments = models.IntegerField(default=0)
    last_payment_date = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["next_payment_date"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["next_payment_date", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.provider.name} - {self.frequency}"
