from django.db import models
from django.utils import timezone
import uuid, qrcode
from io import BytesIO
from django.core.files import File

from apps.accounts.models import User
from apps.common.models import BaseModel


class Currency(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)  # NGN, USD, EUR, BTC, ETH
    symbol = models.CharField(max_length=10)  # $, €, ₿, Ξ
    decimal_places = models.PositiveIntegerField(default=2)
    is_crypto = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    exchange_rate_usd = models.DecimalField(
        max_digits=20, decimal_places=8, default=1.0
    )
    icon = models.ImageField(upload_to="currencies/", null=True, blank=True)

    class Meta:
        verbose_name_plural = "Currencies"

    def __str__(self):
        return f"{self.code} ({self.name})"


class WalletType(models.TextChoices):
    MAIN = "main", "Main Wallet"
    SAVINGS = "savings", "Savings Wallet"
    BUSINESS = "business", "Business Wallet"
    CRYPTO = "crypto", "Crypto Wallet"
    VIRTUAL = "virtual", "Virtual Wallet"


class WalletStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    FROZEN = "frozen", "Frozen"
    SUSPENDED = "suspended", "Suspended"
    CLOSED = "closed", "Closed"


class AccountProvider(models.TextChoices):
    INTERNAL = "internal", "Internal"
    PAYSTACK = "paystack", "Paystack"
    FLUTTERWAVE = "flutterwave", "Flutterwave"
    WISE = "wise", "Wise"


class SplitPaymentType(models.TextChoices):
    EQUAL = "equal", "Equal Split"
    CUSTOM = "custom", "Custom Split"
    PERCENTAGE = "percentage", "Percentage Split"


class SplitPaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PARTIAL = "partial", "Partially Paid"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class ParticipantStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"


class PaymentFrequency(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    YEARLY = "yearly", "Yearly"


class Wallet(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wallets")
    currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, related_name="wallets"
    )

    # Wallet Identity
    wallet_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100, help_text="User-defined wallet name")
    wallet_type = models.CharField(
        max_length=20, choices=WalletType.choices, default=WalletType.MAIN
    )

    # Account Number (for receiving external deposits - like PalmPay/Kuda)
    account_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        help_text="Unique account number for receiving deposits (auto-generated for main wallets)",
    )
    account_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Account holder name (usually user's full name)",
    )
    bank_name = models.CharField(
        max_length=100, default="PayCore", help_text="Bank name shown for this account"
    )

    # Provider Integration (for multi-currency virtual accounts)
    account_provider = models.CharField(
        max_length=20,
        choices=AccountProvider.choices,
        default=AccountProvider.INTERNAL,
        help_text="Provider managing this account (internal, paystack, flutterwave, wise)",
    )
    provider_account_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="External provider's account ID reference",
    )
    provider_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific metadata and configuration",
    )
    is_test_mode = models.BooleanField(
        default=False, help_text="Indicates if this account is in test/sandbox mode"
    )

    # Balance and Limits
    balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    available_balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    pending_balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    # Spending Limits
    daily_limit = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    monthly_limit = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    daily_spent = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    monthly_spent = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    last_daily_reset = models.DateField(default=timezone.now)
    last_monthly_reset = models.DateField(default=timezone.now)

    # Status and Security
    status = models.CharField(
        max_length=20, choices=WalletStatus.choices, default=WalletStatus.ACTIVE
    )
    is_default = models.BooleanField(default=False)
    pin_hash = models.CharField(max_length=255, null=True, blank=True)
    requires_pin = models.BooleanField(default=False)
    requires_biometric = models.BooleanField(default=False)

    # Metadata
    description = models.TextField(blank=True, null=True)
    last_transaction_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "currency", "wallet_type", "is_default"],
                name="unique_default_wallet_per_currency",
            )
        ]
        indexes = [
            models.Index(fields=["user", "currency"]),
            models.Index(fields=["wallet_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.name} ({self.currency.code})"

    @property
    def formatted_balance(self):
        return f"{self.currency.symbol}{self.balance:,.{self.currency.decimal_places}f}"

    def can_spend(self, amount):
        if self.status != WalletStatus.ACTIVE:
            return False, "Wallet is not active"

        if amount > self.available_balance:
            return False, "Insufficient balance"

        # Check daily limit
        if self.daily_limit and (self.daily_spent + amount) > self.daily_limit:
            return False, "Daily spending limit exceeded"

        # Check monthly limit
        if self.monthly_limit and (self.monthly_spent + amount) > self.monthly_limit:
            return False, "Monthly spending limit exceeded"

        return True, None

    def reset_daily_limits(self):
        today = timezone.now().date()
        if self.last_daily_reset < today:
            self.daily_spent = 0
            self.last_daily_reset = today
            self.save()

    def reset_monthly_limits(self):
        today = timezone.now().date()
        if (
            self.last_monthly_reset.month != today.month
            or self.last_monthly_reset.year != today.year
        ):
            self.monthly_spent = 0
            self.last_monthly_reset = today
            self.save()


class QRCode(BaseModel):
    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="qr_codes"
    )

    # QR Code Details
    qr_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qr_image = models.ImageField(upload_to="qr_codes/", null=True, blank=True)

    # Payment Details
    amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    description = models.CharField(max_length=200, blank=True, null=True)

    # Settings
    is_single_use = models.BooleanField(default=False)
    is_amount_fixed = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Usage Tracking
    times_used = models.PositiveIntegerField(default=0)
    total_received = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"QR Code - {self.qr_id} ({self.wallet.name})"

    def generate_qr_code(self):
        qr_data = {
            "wallet_id": str(self.wallet.wallet_id),
            "qr_id": str(self.qr_id),
            "amount": str(self.amount) if self.amount else None,
            "description": self.description,
        }

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(str(qr_data))
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")

        filename = f"qr_{self.qr_id}.png"
        self.qr_image.save(filename, File(buffer), save=False)
        buffer.close()

    def is_expired(self):
        return self.expires_at and timezone.now() > self.expires_at

    def can_be_used(self):
        if not self.is_active or self.is_expired():
            return False, "QR code is inactive or expired"

        if self.is_single_use and self.times_used > 0:
            return False, "QR code is single-use and already used"

        return True, None


class SplitPayment(BaseModel):
    payment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    total_amount = models.DecimalField(max_digits=20, decimal_places=8)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    description = models.CharField(max_length=200)

    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_split_payments"
    )

    split_type = models.CharField(
        max_length=20, choices=SplitPaymentType.choices, default=SplitPaymentType.EQUAL
    )

    status = models.CharField(
        max_length=20,
        choices=SplitPaymentStatus.choices,
        default=SplitPaymentStatus.PENDING,
    )

    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Split Payment - {self.payment_id} ({self.total_amount} {self.currency.code})"


class SplitPaymentParticipant(BaseModel):
    split_payment = models.ForeignKey(
        SplitPayment, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    amount_owed = models.DecimalField(max_digits=20, decimal_places=8)
    amount_paid = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=ParticipantStatus.choices,
        default=ParticipantStatus.PENDING,
    )

    paid_at = models.DateTimeField(null=True, blank=True)
    reminded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [["split_payment", "user"]]

    def __str__(self):
        return (
            f"{self.user.email} - {self.amount_owed} {self.split_payment.currency.code}"
        )

    @property
    def amount_remaining(self):
        return self.amount_owed - self.amount_paid


class RecurringPayment(BaseModel):
    payment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    from_wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="outgoing_recurring"
    )
    to_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="incoming_recurring",
        null=True,
        blank=True,
    )
    to_external = models.CharField(
        max_length=200, null=True, blank=True
    )  # External account details

    amount = models.DecimalField(max_digits=20, decimal_places=8)
    frequency = models.CharField(max_length=20, choices=PaymentFrequency.choices)

    next_payment_date = models.DateTimeField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    auto_retry = models.BooleanField(default=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)

    description = models.CharField(max_length=200)
    reference = models.CharField(max_length=100, blank=True, null=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)
    total_payments_made = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Recurring - {self.description} ({self.amount} {self.from_wallet.currency.code})"
