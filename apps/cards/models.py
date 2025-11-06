from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

from apps.common.models import BaseModel


def get_current_date():
    """Helper function to get current date (not datetime) for DateField defaults"""
    return timezone.now().date()


class CardType(models.TextChoices):
    VIRTUAL = "virtual", "Virtual Card"
    PHYSICAL = "physical", "Physical Card"


class CardBrand(models.TextChoices):
    VISA = "visa", "Visa"
    MASTERCARD = "mastercard", "Mastercard"
    VERVE = "verve", "Verve"


class CardStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    FROZEN = "frozen", "Frozen"
    BLOCKED = "blocked", "Blocked"
    EXPIRED = "expired", "Expired"


class CardProvider(models.TextChoices):
    INTERNAL = "internal", "Internal"
    FLUTTERWAVE = "flutterwave", "Flutterwave"
    SUDO = "sudo", "Sudo"
    STRIPE = "stripe", "Stripe"
    PAYSTACK = "paystack", "Paystack"


class Card(BaseModel):
    wallet = models.ForeignKey(
        "wallets.Wallet", on_delete=models.CASCADE, related_name="cards"
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="cards"
    )

    card_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    card_type = models.CharField(
        max_length=20, choices=CardType.choices, default=CardType.VIRTUAL
    )
    card_brand = models.CharField(
        max_length=20, choices=CardBrand.choices, default=CardBrand.VISA
    )

    card_number = models.CharField(max_length=19, unique=True, db_index=True)
    card_holder_name = models.CharField(max_length=100)
    expiry_month = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    expiry_year = models.PositiveIntegerField()
    cvv = models.CharField(max_length=4)  # Should be encrypted

    # Provider Integration
    card_provider = models.CharField(
        max_length=20,
        choices=CardProvider.choices,
        help_text="Provider managing this card",
    )
    provider_card_id = models.CharField(
        max_length=100, db_index=True, help_text="Provider's internal card ID"
    )
    provider_metadata = models.JSONField(
        default=dict, blank=True, help_text="Provider-specific metadata"
    )
    is_test_mode = models.BooleanField(
        default=False, help_text="Indicates if card is in test/sandbox mode"
    )

    # Card Settings
    spending_limit = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum amount that can be spent per transaction",
    )
    daily_limit = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum daily spending limit",
    )
    monthly_limit = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum monthly spending limit",
    )

    # Status and Security
    status = models.CharField(
        max_length=20, choices=CardStatus.choices, default=CardStatus.INACTIVE
    )
    is_frozen = models.BooleanField(default=False)

    total_spent = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    daily_spent = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    monthly_spent = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_daily_reset = models.DateField(default=get_current_date)
    last_monthly_reset = models.DateField(default=get_current_date)

    allow_online_transactions = models.BooleanField(default=True)
    allow_atm_withdrawals = models.BooleanField(default=True)
    allow_international_transactions = models.BooleanField(default=False)

    # Metadata
    nickname = models.CharField(max_length=50, blank=True, null=True)
    created_for_merchant = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Specific merchant this card was created for (e.g., Netflix)",
    )
    billing_address = models.JSONField(
        default=dict, blank=True, help_text="Billing address for card"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["wallet"]),
            models.Index(fields=["card_provider", "provider_card_id"]),
        ]

    def __str__(self):
        return f"{self.card_brand.upper()} {self.card_type} - {self.masked_number} ({self.user.email})"

    @property
    def masked_number(self):
        if len(self.card_number) >= 4:
            return f"**** **** **** {self.card_number[-4:]}"
        return "****"

    @property
    def is_expired(self):
        now = timezone.now()
        return (now.year > self.expiry_year) or (
            now.year == self.expiry_year and now.month > self.expiry_month
        )

    @property
    def can_transact(self):
        return (
            self.status == CardStatus.ACTIVE
            and not self.is_frozen
            and not self.is_expired
        )

    def can_spend(self, amount):
        if not self.can_transact:
            return False, "Card cannot be used for transactions"

        # Check per-transaction limit
        if self.spending_limit and amount > self.spending_limit:
            return (
                False,
                f"Amount exceeds per-transaction limit of {self.wallet.currency.symbol}{self.spending_limit}",
            )

        # Check daily limit
        if self.daily_limit and (self.daily_spent + amount) > self.daily_limit:
            return (
                False,
                f"Daily spending limit of {self.wallet.currency.symbol}{self.daily_limit} exceeded",
            )

        # Check monthly limit
        if self.monthly_limit and (self.monthly_spent + amount) > self.monthly_limit:
            return (
                False,
                f"Monthly spending limit of {self.wallet.currency.symbol}{self.monthly_limit} exceeded",
            )

        # Check wallet balance
        if amount > self.wallet.available_balance:
            return False, "Insufficient wallet balance"

        return True, None

    def reset_daily_limits(self):
        today = timezone.now().date()
        if self.last_daily_reset < today:
            self.daily_spent = 0
            self.last_daily_reset = today
            self.save(update_fields=["daily_spent", "last_daily_reset", "updated_at"])

    def reset_monthly_limits(self):
        today = timezone.now().date()
        if (
            self.last_monthly_reset.month != today.month
            or self.last_monthly_reset.year != today.year
        ):
            self.monthly_spent = 0
            self.last_monthly_reset = today
            self.save(
                update_fields=["monthly_spent", "last_monthly_reset", "updated_at"]
            )

    def freeze(self):
        """Freeze the card (temporary block)."""
        self.is_frozen = True

    def unfreeze(self):
        """Unfreeze the card."""
        self.is_frozen = False
