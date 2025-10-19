import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from datetime import timedelta

from apps.common.models import BaseModel
from apps.accounts.models import User


class InvestmentType(models.TextChoices):
    """Types of investment products"""

    FIXED_DEPOSIT = "fixed_deposit", "Fixed Deposit"
    SAVINGS_PLAN = "savings_plan", "Savings Plan"
    MUTUAL_FUND = "mutual_fund", "Mutual Fund"
    BOND = "bond", "Bond"
    STOCK = "stock", "Stock"
    TREASURY_BILL = "treasury_bill", "Treasury Bill"
    MONEY_MARKET = "money_market", "Money Market"


class RiskLevel(models.TextChoices):
    """Investment risk levels"""

    LOW = "low", "Low Risk"
    MEDIUM = "medium", "Medium Risk"
    HIGH = "high", "High Risk"
    VERY_HIGH = "very_high", "Very High Risk"


class InterestPayoutFrequency(models.TextChoices):
    """How often interest/returns are paid"""

    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    SEMI_ANNUALLY = "semi_annually", "Semi-Annually"
    ANNUALLY = "annually", "Annually"
    AT_MATURITY = "at_maturity", "At Maturity"


class InvestmentStatus(models.TextChoices):
    """Status of a user's investment"""

    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    MATURED = "matured", "Matured"
    LIQUIDATED = "liquidated", "Liquidated (Early Exit)"
    CANCELLED = "cancelled", "Cancelled"
    RENEWED = "renewed", "Renewed"


class InvestmentProduct(BaseModel):
    """Investment products offered by the platform"""

    product_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    name = models.CharField(max_length=200)
    product_type = models.CharField(max_length=20, choices=InvestmentType.choices)
    description = models.TextField(blank=True)

    currency = models.ForeignKey(
        "wallets.Currency", on_delete=models.PROTECT, related_name="investment_products"
    )
    min_amount = models.DecimalField(max_digits=20, decimal_places=2)
    max_amount = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )

    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Annual interest rate in percentage"
    )
    payout_frequency = models.CharField(
        max_length=20,
        choices=InterestPayoutFrequency.choices,
        default=InterestPayoutFrequency.AT_MATURITY,
    )

    min_duration_days = models.PositiveIntegerField(
        help_text="Minimum investment duration in days"
    )
    max_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum investment duration in days (null for flexible)",
    )

    risk_level = models.CharField(
        max_length=20, choices=RiskLevel.choices, default=RiskLevel.LOW
    )
    is_capital_guaranteed = models.BooleanField(
        default=True, help_text="Is principal amount guaranteed?"
    )
    allows_early_liquidation = models.BooleanField(default=False)
    early_liquidation_penalty = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Penalty percentage for early liquidation",
    )
    allows_auto_renewal = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)
    available_slots = models.PositiveIntegerField(
        null=True, blank=True, help_text="Limited slots available (null for unlimited)"
    )
    slots_taken = models.PositiveIntegerField(default=0)

    terms_and_conditions = models.TextField(blank=True)
    benefits = models.JSONField(default=list, blank=True, help_text="List of benefits")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product_type", "is_active"]),
            models.Index(fields=["currency", "is_active"]),
            models.Index(fields=["risk_level"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.product_type})"

    @property
    def is_available(self):
        if not self.is_active:
            return False
        if (
            self.available_slots is not None
            and self.slots_taken >= self.available_slots
        ):
            return False
        return True


class Investment(BaseModel):
    """User's investment instances"""

    investment_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="investments")
    product = models.ForeignKey(
        InvestmentProduct, on_delete=models.PROTECT, related_name="investments"
    )
    wallet = models.ForeignKey(
        "wallets.Wallet",
        on_delete=models.PROTECT,
        related_name="investments",
        help_text="Wallet used for investment and returns",
    )

    principal_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Interest rate at time of investment (locked)",
    )
    duration_days = models.PositiveIntegerField(help_text="Investment duration in days")

    start_date = models.DateTimeField()
    maturity_date = models.DateTimeField()
    actual_maturity_date = models.DateTimeField(null=True, blank=True)

    expected_returns = models.DecimalField(
        max_digits=20, decimal_places=2, help_text="Expected total returns at maturity"
    )
    actual_returns = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text="Actual returns earned so far",
    )
    total_payout = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text="Total amount paid out (principal + returns)",
    )

    status = models.CharField(
        max_length=20,
        choices=InvestmentStatus.choices,
        default=InvestmentStatus.PENDING,
    )

    auto_renew = models.BooleanField(default=False)
    renewed_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renewals",
    )

    liquidation_date = models.DateTimeField(null=True, blank=True)
    liquidation_penalty = models.DecimalField(
        max_digits=20, decimal_places=2, default=0
    )

    investment_transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investments_created",
    )
    payout_transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investments_paid_out",
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["product", "status"]),
            models.Index(fields=["status", "maturity_date"]),
            models.Index(fields=["wallet", "-created_at"]),
        ]

    def __str__(self):
        return f"Investment {self.investment_id} - {self.user.email}"

    @property
    def is_active(self):
        return self.status == InvestmentStatus.ACTIVE

    @property
    def is_matured(self):
        return timezone.now() >= self.maturity_date

    @property
    def days_to_maturity(self):
        if self.is_matured:
            return 0
        delta = self.maturity_date - timezone.now()
        return delta.days

    @property
    def days_invested(self):
        if self.start_date:
            delta = timezone.now() - self.start_date
            return delta.days
        return 0

    @property
    def current_value(self):
        return self.principal_amount + self.actual_returns


class InvestmentReturn(BaseModel):
    """Track periodic returns/interest payouts"""

    return_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    investment = models.ForeignKey(
        Investment, on_delete=models.CASCADE, related_name="returns"
    )

    amount = models.DecimalField(max_digits=20, decimal_places=2)
    payout_date = models.DateTimeField()
    actual_payout_date = models.DateTimeField(null=True, blank=True)

    is_paid = models.BooleanField(default=False)

    transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investment_returns",
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["payout_date"]
        indexes = [
            models.Index(fields=["investment", "is_paid"]),
            models.Index(fields=["payout_date", "is_paid"]),
        ]

    def __str__(self):
        return f"Return {self.return_id} - {self.amount}"


class InvestmentPortfolio(BaseModel):
    """Aggregate portfolio view for each user"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="investment_portfolio"
    )

    total_invested = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_active_investments = models.DecimalField(
        max_digits=20, decimal_places=2, default=0
    )
    total_returns_earned = models.DecimalField(
        max_digits=20, decimal_places=2, default=0
    )
    total_matured_value = models.DecimalField(
        max_digits=20, decimal_places=2, default=0
    )

    active_investments_count = models.PositiveIntegerField(default=0)
    matured_investments_count = models.PositiveIntegerField(default=0)
    total_investments_count = models.PositiveIntegerField(default=0)

    average_return_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Average return rate across all investments",
    )

    last_calculated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Portfolio - {self.user.email}"
