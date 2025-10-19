from django.db import models
from django.utils import timezone
import uuid

from apps.accounts.models import User
from apps.common.models import BaseModel


class LoanProductType(models.TextChoices):
    PERSONAL = "personal", "Personal Loan"
    BUSINESS = "business", "Business Loan"
    PAYDAY = "payday", "Payday Loan"
    EMERGENCY = "emergency", "Emergency Loan"
    EDUCATION = "education", "Education Loan"
    AUTO = "auto", "Auto Loan"
    HOME = "home", "Home Loan"


class LoanStatus(models.TextChoices):
    PENDING = "pending", "Pending Review"
    UNDER_REVIEW = "under_review", "Under Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    DISBURSED = "disbursed", "Disbursed"
    ACTIVE = "active", "Active"
    OVERDUE = "overdue", "Overdue"
    DEFAULTED = "defaulted", "Defaulted"
    PAID = "paid", "Fully Paid"
    CANCELLED = "cancelled", "Cancelled"


class RepaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"
    PARTIAL = "partial", "Partially Paid"
    MISSED = "missed", "Missed"


class RepaymentFrequency(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    BIWEEKLY = "biweekly", "Bi-Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"


class CollateralType(models.TextChoices):
    NONE = "none", "No Collateral"
    PROPERTY = "property", "Property"
    VEHICLE = "vehicle", "Vehicle"
    SAVINGS = "savings", "Savings Account"
    INVESTMENT = "investment", "Investment Portfolio"
    OTHER = "other", "Other"


class CreditScoreBand(models.TextChoices):
    EXCELLENT = "excellent", "Excellent (750-850)"
    GOOD = "good", "Good (700-749)"
    FAIR = "fair", "Fair (650-699)"
    POOR = "poor", "Poor (600-649)"
    VERY_POOR = "very_poor", "Very Poor (300-599)"


class AutoRepaymentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    SUSPENDED = "suspended", "Suspended"
    FAILED = "failed", "Failed"


class RiskLevel(models.TextChoices):
    LOW = "low", "Low Risk"
    MEDIUM = "medium", "Medium Risk"
    HIGH = "high", "High Risk"
    VERY_HIGH = "very_high", "Very High Risk"


class LoanProduct(BaseModel):
    product_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    name = models.CharField(max_length=200)
    description = models.TextField()
    product_type = models.CharField(max_length=20, choices=LoanProductType.choices)

    min_amount = models.DecimalField(max_digits=20, decimal_places=2)
    max_amount = models.DecimalField(max_digits=20, decimal_places=2)

    min_interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Annual interest rate percentage"
    )
    max_interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Annual interest rate percentage"
    )

    min_tenure_months = models.PositiveIntegerField(
        help_text="Minimum loan duration in months"
    )
    max_tenure_months = models.PositiveIntegerField(
        help_text="Maximum loan duration in months"
    )

    processing_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    processing_fee_fixed = models.DecimalField(
        max_digits=20, decimal_places=2, default=0
    )
    late_payment_fee = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    early_repayment_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )

    min_credit_score = models.PositiveIntegerField(
        default=300, help_text="Minimum credit score required"
    )
    requires_collateral = models.BooleanField(default=False)
    requires_guarantor = models.BooleanField(default=False)
    min_account_age_days = models.PositiveIntegerField(
        default=30, help_text="Minimum account age in days"
    )

    allowed_repayment_frequencies = models.JSONField(
        default=list,
        help_text="List of allowed repayment frequencies: daily, weekly, biweekly, monthly, quarterly",
    )

    is_active = models.BooleanField(default=True)
    currency = models.ForeignKey(
        "wallets.Currency", on_delete=models.PROTECT, related_name="loan_products"
    )

    eligibility_criteria = models.JSONField(
        default=dict,
        help_text="Additional eligibility criteria as JSON (e.g., employment status, income requirements)",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product_type", "is_active"]),
            models.Index(fields=["currency", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.product_type})"


class LoanApplication(BaseModel):
    """User loan application"""

    application_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="loan_applications"
    )
    loan_product = models.ForeignKey(
        LoanProduct, on_delete=models.PROTECT, related_name="applications"
    )

    wallet = models.ForeignKey(
        "wallets.Wallet", on_delete=models.PROTECT, related_name="loan_applications"
    )

    requested_amount = models.DecimalField(max_digits=20, decimal_places=2)
    approved_amount = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Annual interest rate"
    )
    tenure_months = models.PositiveIntegerField(help_text="Loan duration in months")
    repayment_frequency = models.CharField(
        max_length=20, choices=RepaymentFrequency.choices
    )

    processing_fee = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_interest = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_repayable = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    monthly_repayment = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    purpose = models.CharField(max_length=200)
    purpose_details = models.TextField(null=True, blank=True)

    employment_status = models.CharField(max_length=50, null=True, blank=True)
    employer_name = models.CharField(max_length=200, null=True, blank=True)
    monthly_income = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )

    collateral_type = models.CharField(
        max_length=20, choices=CollateralType.choices, default=CollateralType.NONE
    )
    collateral_value = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    collateral_description = models.TextField(null=True, blank=True)

    guarantor_name = models.CharField(max_length=200, null=True, blank=True)
    guarantor_phone = models.CharField(max_length=20, null=True, blank=True)
    guarantor_email = models.EmailField(null=True, blank=True)
    guarantor_relationship = models.CharField(max_length=100, null=True, blank=True)

    credit_score = models.PositiveIntegerField(null=True, blank=True)
    credit_score_band = models.CharField(
        max_length=20, choices=CreditScoreBand.choices, null=True, blank=True
    )
    risk_assessment = models.JSONField(
        default=dict, help_text="Risk assessment details"
    )

    status = models.CharField(
        max_length=20, choices=LoanStatus.choices, default=LoanStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_loan_applications",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)

    disbursed_at = models.DateTimeField(null=True, blank=True)
    disbursement_transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_disbursements",
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["loan_product", "status"]),
        ]

    def __str__(self):
        return f"Loan Application {self.application_id} - {self.user.email}"

    @property
    def is_active(self):
        return self.status in [
            LoanStatus.DISBURSED,
            LoanStatus.ACTIVE,
            LoanStatus.OVERDUE,
        ]

    @property
    def is_overdue(self):
        if not self.is_active:
            return False
        return self.repayment_schedules.filter(status=RepaymentStatus.OVERDUE).exists()

    @property
    def loan_product_name(self):
        """Get loan product name"""
        return self.loan_product.name if self.loan_product else None

    @property
    def loan_product_type(self):
        """Get loan product type"""
        return self.loan_product.product_type if self.loan_product else None


class LoanRepaymentSchedule(BaseModel):
    """Repayment schedule for each installment"""

    schedule_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    loan = models.ForeignKey(
        LoanApplication, on_delete=models.CASCADE, related_name="repayment_schedules"
    )

    installment_number = models.PositiveIntegerField(
        help_text="Installment sequence number"
    )
    due_date = models.DateField()

    principal_amount = models.DecimalField(max_digits=20, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=20, decimal_places=2)
    total_amount = models.DecimalField(max_digits=20, decimal_places=2)

    amount_paid = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=20, decimal_places=2)

    status = models.CharField(
        max_length=20, choices=RepaymentStatus.choices, default=RepaymentStatus.PENDING
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    days_overdue = models.PositiveIntegerField(default=0)
    late_fee = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    class Meta:
        ordering = ["loan", "installment_number"]
        indexes = [
            models.Index(fields=["loan", "status"]),
            models.Index(fields=["due_date", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "installment_number"],
                name="unique_loan_installment_number",
            )
        ]

    def __str__(self):
        return (
            f"Repayment #{self.installment_number} for Loan {self.loan.application_id}"
        )

    @property
    def is_overdue(self):
        if self.status in [RepaymentStatus.PAID]:
            return False
        return timezone.now().date() > self.due_date


class LoanRepayment(BaseModel):
    """Individual loan repayment transactions"""

    repayment_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    loan = models.ForeignKey(
        LoanApplication, on_delete=models.CASCADE, related_name="repayments"
    )
    schedule = models.ForeignKey(
        LoanRepaymentSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repayments",
        help_text="Specific schedule this payment applies to",
    )

    amount = models.DecimalField(max_digits=20, decimal_places=2)
    principal_paid = models.DecimalField(max_digits=20, decimal_places=2)
    interest_paid = models.DecimalField(max_digits=20, decimal_places=2)
    late_fee_paid = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    wallet = models.ForeignKey(
        "wallets.Wallet", on_delete=models.PROTECT, related_name="loan_repayments"
    )
    transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_repayments",
    )

    is_early_repayment = models.BooleanField(default=False)
    early_repayment_fee = models.DecimalField(
        max_digits=20, decimal_places=2, default=0
    )

    reference = models.CharField(max_length=100, unique=True, db_index=True)
    external_reference = models.CharField(max_length=200, null=True, blank=True)

    status = models.CharField(max_length=20, default="completed")
    payment_method = models.CharField(max_length=50, default="wallet")

    notes = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["loan", "-created_at"]),
            models.Index(fields=["reference"]),
            models.Index(fields=["wallet", "-created_at"]),
        ]

    def __str__(self):
        return f"Repayment {self.repayment_id} - {self.amount}"


class RiskLevel(models.TextChoices):
    LOW = "low", "Low Risk"
    MEDIUM = "medium", "Medium Risk"
    HIGH = "high", "High Risk"
    VERY_HIGH = "very_high", "Very High Risk"


class CreditScore(BaseModel):
    """User credit score history"""

    score_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="credit_scores"
    )

    score = models.PositiveIntegerField(help_text="Credit score (300-850)")
    score_band = models.CharField(max_length=20, choices=CreditScoreBand.choices)

    payment_history_score = models.PositiveIntegerField(
        default=0, help_text="Score based on payment history"
    )
    credit_utilization_score = models.PositiveIntegerField(
        default=0, help_text="Score based on credit usage"
    )
    account_age_score = models.PositiveIntegerField(
        default=0, help_text="Score based on account age"
    )
    loan_history_score = models.PositiveIntegerField(
        default=0, help_text="Score based on loan history"
    )

    total_loans = models.PositiveIntegerField(default=0)
    active_loans = models.PositiveIntegerField(default=0)
    completed_loans = models.PositiveIntegerField(default=0)
    defaulted_loans = models.PositiveIntegerField(default=0)

    on_time_payments = models.PositiveIntegerField(default=0)
    late_payments = models.PositiveIntegerField(default=0)
    missed_payments = models.PositiveIntegerField(default=0)

    total_borrowed = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_repaid = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    current_debt = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    risk_level = models.CharField(
        max_length=20, choices=RiskLevel.choices, default=RiskLevel.MEDIUM
    )

    account_age_days = models.PositiveIntegerField(default=0)

    factors = models.JSONField(default=dict, help_text="Detailed scoring factors")
    recommendations = models.JSONField(
        default=list, help_text="Recommendations to improve score"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["score"]),
        ]

    def __str__(self):
        return f"Credit Score {self.score} ({self.score_band}) - {self.user.email}"

    @staticmethod
    def get_score_band(score: int) -> str:
        if score >= 750:
            return CreditScoreBand.EXCELLENT
        elif score >= 700:
            return CreditScoreBand.GOOD
        elif score >= 650:
            return CreditScoreBand.FAIR
        elif score >= 600:
            return CreditScoreBand.POOR
        else:
            return CreditScoreBand.VERY_POOR


class AutoRepayment(BaseModel):
    """Automatic loan repayment configuration"""

    auto_repayment_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    loan = models.OneToOneField(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name="auto_repayment",
        help_text="Loan to auto-repay",
    )
    wallet = models.ForeignKey(
        "wallets.Wallet",
        on_delete=models.PROTECT,
        related_name="loan_auto_repayments",
        help_text="Wallet to debit automatically",
    )

    is_enabled = models.BooleanField(
        default=True, help_text="Whether auto-repayment is active"
    )
    status = models.CharField(
        max_length=20,
        choices=AutoRepaymentStatus.choices,
        default=AutoRepaymentStatus.ACTIVE,
    )

    auto_pay_full_amount = models.BooleanField(
        default=True, help_text="Pay full installment amount automatically"
    )
    custom_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Custom amount to pay (if not full amount)",
    )

    days_before_due = models.PositiveIntegerField(
        default=0,
        help_text="Number of days before due date to trigger payment (0 = on due date)",
    )

    retry_on_failure = models.BooleanField(
        default=True, help_text="Retry if payment fails due to insufficient balance"
    )
    max_retry_attempts = models.PositiveIntegerField(
        default=3, help_text="Maximum number of retry attempts"
    )
    retry_interval_hours = models.PositiveIntegerField(
        default=24, help_text="Hours between retry attempts"
    )

    total_payments_made = models.PositiveIntegerField(
        default=0, help_text="Total number of automatic payments processed"
    )
    last_payment_date = models.DateTimeField(
        null=True, blank=True, help_text="Last successful automatic payment"
    )
    last_payment_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount of last automatic payment",
    )
    last_failure_date = models.DateTimeField(
        null=True, blank=True, help_text="Last failed payment attempt"
    )
    last_failure_reason = models.TextField(
        null=True, blank=True, help_text="Reason for last failure"
    )
    consecutive_failures = models.PositiveIntegerField(
        default=0, help_text="Number of consecutive failed attempts"
    )

    send_notification_on_success = models.BooleanField(
        default=True, help_text="Send notification when payment succeeds"
    )
    send_notification_on_failure = models.BooleanField(
        default=True, help_text="Send notification when payment fails"
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["loan", "status"]),
            models.Index(fields=["is_enabled", "status"]),
            models.Index(fields=["wallet", "-created_at"]),
        ]

    def __str__(self):
        return f"Auto-Repayment for Loan {self.loan.application_id} - {self.status}"

    @property
    def is_active(self):
        return self.is_enabled and self.status == AutoRepaymentStatus.ACTIVE

    def suspend(self, reason: str = None):
        self.status = AutoRepaymentStatus.SUSPENDED
        if reason and self.metadata:
            self.metadata["suspension_reason"] = reason
            self.metadata["suspended_at"] = timezone.now().isoformat()

    def reactivate(self):
        if self.status == AutoRepaymentStatus.SUSPENDED:
            self.status = AutoRepaymentStatus.ACTIVE
            self.consecutive_failures = 0
