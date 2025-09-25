from django.db import models

from apps.accounts.models import User
from apps.common.models import BaseModel


class Country(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)  # ISO country code
    currency = models.CharField(max_length=10)  # e.g. USD, EUR
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class KYCStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    UNDER_REVIEW = "under_review", "Under Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    RESUBMIT_REQUIRED = "resubmit_required", "Resubmit Required"


class DocumentType(models.TextChoices):
    NATIONAL_ID = "national_id", "National ID"
    PASSPORT = "passport", "Passport"
    DRIVERS_LICENSE = "drivers_license", "Driver's License"
    UTILITY_BILL = "utility_bill", "Utility Bill"


class RiskLevel(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


class VerificationMethod(models.TextChoices):
    MANUAL = "manual", "Manual Review"
    AUTOMATED = "automated", "Automated"
    HYBRID = "hybrid", "Hybrid"


class KYC(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc")

    # Basic KYC details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    # Address details
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    # Document uploads
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    document_number = models.CharField(max_length=100, unique=True)
    document_expiry_date = models.DateField(blank=True, null=True)
    document_file = models.FileField(upload_to="kyc/documents/")
    document_back_file = models.FileField(
        upload_to="kyc/documents/", blank=True, null=True
    )
    selfie_file = models.FileField(upload_to="kyc/selfies/", blank=True, null=True)

    # Verification status
    status = models.CharField(
        max_length=30, choices=KYCStatus.choices, default=KYCStatus.PENDING
    )
    notes = models.TextField(blank=True, null=True)  # reviewer/admin notes
    rejection_reason = models.TextField(blank=True, null=True)

    # Audit fields
    reviewed_at = models.DateTimeField(blank=True, null=True)
    provider_name = models.CharField(max_length=50, blank=True, null=True)
    provider_reference_id = models.CharField(max_length=100, blank=True, null=True)
    provider_status = models.CharField(max_length=50, blank=True, null=True)
    webhook_verified_at = models.DateTimeField(blank=True, null=True)

    # Compliance flags
    is_politically_exposed = models.BooleanField(default=False)  # AML flag
    aml_check_passed = models.BooleanField(default=False)
    risk_level = models.CharField(
        max_length=20, choices=RiskLevel.choices, default=RiskLevel.LOW
    )
    fraud_score = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )  # e.g. from 3rd party fraud API
    verification_method = models.CharField(
        max_length=20,
        choices=VerificationMethod.choices,
        default=VerificationMethod.MANUAL,
    )

    def __str__(self):
        return f"KYC - {self.user.email} ({self.status})"
