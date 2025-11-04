import uuid
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel
from apps.accounts.models import User
from apps.profiles.models import Country


class KYCStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    UNDER_REVIEW = "under_review", "Under Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    EXPIRED = "expired", "Expired"


class KYCLevel(models.TextChoices):
    TIER_1 = "tier_1", "Tier 1 - Basic"
    TIER_2 = "tier_2", "Tier 2 - Intermediate"
    TIER_3 = "tier_3", "Tier 3 - Advanced"


class DocumentType(models.TextChoices):
    NATIONAL_ID = "national_id", "National ID"
    PASSPORT = "passport", "Passport"
    DRIVERS_LICENSE = "drivers_license", "Driver's License"
    RESIDENCE_PERMIT = "residence_permit", "Residence Permit"
    UTILITY_BILL = "utility_bill", "Utility Bill (Proof of Address)"
    BANK_STATEMENT = "bank_statement", "Bank Statement"
    SELFIE = "selfie", "Selfie with ID"


class RiskLevel(models.TextChoices):
    LOW = "low", "Low Risk"
    MEDIUM = "medium", "Medium Risk"
    HIGH = "high", "High Risk"
    CRITICAL = "critical", "Critical Risk"


class KYCVerification(BaseModel):
    kyc_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="kyc_verifications"
    )

    # Verification details
    level = models.CharField(
        max_length=10, choices=KYCLevel.choices, default=KYCLevel.TIER_1
    )
    status = models.CharField(
        max_length=20, choices=KYCStatus.choices, default=KYCStatus.PENDING
    )

    # Personal information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    nationality = models.CharField(
        max_length=2, help_text="ISO 3166-1 alpha-2 country code"
    )
    phone_number = models.CharField(max_length=20, blank=True)
    selfie_image = models.ImageField(null=True, upload_to="kyc_selfies/")
    # Address
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, related_name="kyc_verifications"
    )

    # Identity document
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    document_number = models.CharField(max_length=100)
    document_expiry_date = models.DateField(null=True, blank=True)
    document_issuing_country = models.ForeignKey(
        Country, on_delete=models.CASCADE, related_name="issuer_kyc_verifications"
    )

    # Review
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kyc_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)

    # External provider integration
    provider_name = models.CharField(max_length=50, blank=True)
    provider_reference_id = models.CharField(max_length=100, blank=True)
    provider_status = models.CharField(max_length=50, blank=True)
    webhook_verified_at = models.DateTimeField(null=True, blank=True)

    # Compliance flags
    is_politically_exposed = models.BooleanField(
        default=False, help_text="PEP (Politically Exposed Person) - AML flag"
    )
    verification_method = models.CharField(
        max_length=20,
        choices=[
            ("manual", "Manual Review"),
            ("automated", "Automated"),
            ("hybrid", "Hybrid"),
        ],
        default="manual",
    )

    # Metadata
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "level"]),
            models.Index(fields=["document_number"]),
        ]

    def __str__(self):
        return f"KYC {self.kyc_id} - {self.user.email} ({self.status})"

    @property
    def is_approved(self):
        return self.status == KYCStatus.APPROVED

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() >= self.expires_at
        return False


class KYCDocument(BaseModel):
    document_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    kyc_verification = models.ForeignKey(
        KYCVerification, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)

    # File
    file = models.FileField(upload_to="compliance/kyc/%Y/%m/%d/")
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()

    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.document_type} - {self.file_name}"


class AMLCheck(BaseModel):
    """Anti-Money Laundering checks"""

    check_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="aml_checks")
    transaction_id = models.UUIDField(
        null=True, blank=True, help_text="Related transaction if any"
    )

    # Check details
    check_type = models.CharField(
        max_length=50, help_text="Type of AML check performed"
    )
    risk_score = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Risk score 0-100"
    )
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices)
    fraud_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Fraud risk score from external fraud detection API",
    )

    # Results
    passed = models.BooleanField(default=True)
    flagged_items = models.JSONField(
        default=list, help_text="List of flagged items/reasons"
    )

    # External service
    provider = models.CharField(
        max_length=100, blank=True, help_text="External AML service provider"
    )
    provider_reference = models.CharField(max_length=255, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)

    # Review
    requires_manual_review = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aml_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "risk_level"]),
            models.Index(fields=["risk_level", "requires_manual_review"]),
            models.Index(fields=["transaction_id"]),
        ]

    def __str__(self):
        return f"AML Check {self.check_id} - {self.risk_level}"


class SanctionsScreening(BaseModel):
    """Sanctions list screening"""

    screening_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sanctions_screenings"
    )

    # Screening details
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=2, blank=True)

    is_match = models.BooleanField(default=False)
    match_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Match confidence score 0-100",
    )
    matched_lists = models.JSONField(
        default=list, help_text="Lists where matches were found"
    )
    match_details = models.JSONField(default=dict, blank=True)

    provider = models.CharField(max_length=100, blank=True)
    provider_reference = models.CharField(max_length=255, blank=True)

    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sanctions_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    false_positive = models.BooleanField(default=False)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_match"]),
            models.Index(fields=["is_match", "false_positive"]),
        ]

    def __str__(self):
        return f"Sanctions Screening {self.screening_id} - {'Match' if self.is_match else 'Clear'}"


class TransactionMonitoring(BaseModel):
    """Monitoring for suspicious transaction patterns"""

    monitoring_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="transaction_monitorings"
    )
    transaction_id = models.UUIDField(db_index=True)

    alert_type = models.CharField(
        max_length=100, help_text="Type of suspicious activity detected"
    )
    risk_score = models.DecimalField(max_digits=5, decimal_places=2)
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices)

    description = models.TextField()
    triggered_rules = models.JSONField(
        default=list, help_text="Rules that triggered this alert"
    )

    transaction_amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction_type = models.CharField(max_length=50)
    transaction_date = models.DateTimeField()

    is_resolved = models.BooleanField(default=False)
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_alerts",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    is_reported = models.BooleanField(
        default=False, help_text="Reported to authorities"
    )
    reported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "risk_level"]),
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["risk_level", "is_resolved"]),
            models.Index(fields=["alert_type", "is_resolved"]),
        ]

    def __str__(self):
        return f"Alert {self.monitoring_id} - {self.alert_type}"


class ComplianceReport(BaseModel):
    """Compliance reports generated for regulatory purposes"""

    report_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    report_type = models.CharField(max_length=100)
    report_period_start = models.DateField()
    report_period_end = models.DateField()

    summary = models.TextField()
    total_transactions = models.PositiveIntegerField(default=0)
    flagged_transactions = models.PositiveIntegerField(default=0)
    total_users_screened = models.PositiveIntegerField(default=0)
    high_risk_users = models.PositiveIntegerField(default=0)

    file = models.FileField(
        upload_to="compliance/reports/%Y/%m/", null=True, blank=True
    )

    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="generated_reports"
    )
    data = models.JSONField(default=dict, help_text="Detailed report data")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["report_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.report_type} - {self.report_period_start} to {self.report_period_end}"
