from ninja import ModelSchema, Schema
from pydantic import field_validator, Field
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from apps.common.schemas import BaseSchema, PaginatedResponseDataSchema, ResponseSchema
from apps.compliance.models import (
    KYCVerification,
    KYCDocument,
    AMLCheck,
    SanctionsScreening,
    TransactionMonitoring,
    ComplianceReport,
    KYCStatus,
    KYCLevel,
    DocumentType,
    RiskLevel,
)
from apps.profiles.schemas import UserSchema
from datetime import date, timedelta

# ==================== KYC SCHEMAS ====================


class CreateKYCSchema(BaseSchema):
    """Schema for submitting KYC verification"""

    level: KYCLevel = Field(..., description="KYC level: tier_1, tier_2, tier_3")

    # Personal information
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    date_of_birth: date
    nationality: str = Field(
        ..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2"
    )

    # Address
    address_line_1: str = Field(..., max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., max_length=100)
    state: str = Field(..., max_length=100)
    postal_code: str = Field(..., max_length=20)
    country_id: UUID = Field(..., description="Country ID from profiles.Country")

    # Identity document
    document_type: DocumentType
    document_number: str = Field(..., max_length=100)
    document_expiry_date: Optional[date] = None
    document_issuing_country_id: UUID = Field(
        ..., description="Country ID from profiles.Country"
    )

    notes: Optional[str] = None

    @field_validator("date_of_birth")
    def validate_date_of_birth(cls, value: date):
        min_age = 18
        today = date.today()
        min_birth_date = today - timedelta(days=min_age * 365.25)

        if value > min_birth_date:
            raise ValueError("User must be at least 18 years old")
        return value


class UpdateKYCStatusSchema(BaseSchema):
    status: KYCStatus
    rejection_reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class KYCDocumentSchema(ModelSchema):
    class Meta:
        model = KYCDocument
        fields = [
            "document_id",
            "document_type",
            "file_name",
            "file_size",
            "is_verified",
            "verified_at",
            "created_at",
        ]


class KYCVerificationSchema(ModelSchema):
    user: UserSchema
    documents: List[KYCDocumentSchema] = []

    class Meta:
        model = KYCVerification
        exclude = ["id", "deleted_at"]


class KYCVerificationListSchema(BaseSchema):
    kyc_id: UUID
    user: UserSchema
    level: str
    status: str
    first_name: str
    last_name: str
    document_type: str
    reviewed_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime


class KYCVerificationDataResponseSchema(BaseSchema):
    message: str
    data: KYCVerificationSchema


class KYCVerificationListDataResponseSchema(BaseSchema):
    message: str
    data: List[KYCVerificationListSchema]


class KYCVerificationPaginatedDataResponseSchema(PaginatedResponseDataSchema):
    data: List[KYCVerificationListSchema] = Field(..., alias="items")


class KYCVerificationsResponseSchema(ResponseSchema):
    data: KYCVerificationPaginatedDataResponseSchema


class KYCLevelSchema(BaseSchema):
    level: KYCLevel = Field(
        None, description="KYC level: tier_1, tier_2, tier_3", example="tier_1"
    )


# ==================== AML SCHEMAS ====================
class CreateAMLCheckSchema(BaseSchema):
    user_id: UUID
    transaction_id: Optional[UUID] = None
    check_type: str
    provider: Optional[str] = None


class AMLCheckSchema(ModelSchema):
    user: UserSchema

    class Meta:
        model = AMLCheck
        fields = [
            "check_id",
            "transaction_id",
            "check_type",
            "risk_score",
            "risk_level",
            "passed",
            "flagged_items",
            "provider",
            "provider_reference",
            "requires_manual_review",
            "reviewed_at",
            "review_notes",
            "created_at",
        ]


class AMLCheckListSchema(BaseSchema):
    check_id: UUID
    user: UserSchema
    check_type: str
    risk_score: Decimal
    risk_level: str
    passed: bool
    requires_manual_review: bool
    created_at: datetime


class UpdateAMLReviewSchema(BaseSchema):
    review_notes: str


class AMLCheckDataResponseSchema(BaseSchema):
    message: str
    data: AMLCheckSchema


class AMLCheckListDataResponseSchema(BaseSchema):
    message: str
    data: List[AMLCheckListSchema]


class AMLCheckPaginatedDataResponseSchema(PaginatedResponseDataSchema):
    data: List[AMLCheckListSchema] = Field(..., alias="items")


# ==================== SANCTIONS SCREENING SCHEMAS ====================


class CreateSanctionsScreeningSchema(BaseSchema):
    user_id: UUID
    full_name: str
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = Field(None, min_length=2, max_length=2)
    provider: Optional[str] = None


class SanctionsScreeningSchema(ModelSchema):
    user: UserSchema

    class Meta:
        model = SanctionsScreening
        fields = [
            "screening_id",
            "full_name",
            "date_of_birth",
            "nationality",
            "is_match",
            "match_score",
            "matched_lists",
            "match_details",
            "provider",
            "provider_reference",
            "reviewed_at",
            "false_positive",
            "review_notes",
            "created_at",
        ]


class SanctionsScreeningListSchema(BaseSchema):
    screening_id: UUID
    user: UserSchema
    full_name: str
    is_match: bool
    match_score: Optional[Decimal]
    matched_lists: List
    false_positive: bool
    created_at: datetime


class UpdateSanctionsReviewSchema(BaseSchema):
    false_positive: bool
    review_notes: str


class SanctionsScreeningDataResponseSchema(BaseSchema):
    message: str
    data: SanctionsScreeningSchema


class SanctionsScreeningListDataResponseSchema(BaseSchema):
    message: str
    data: List[SanctionsScreeningListSchema]


class SanctionsScreeningPaginatedDataResponseSchema(PaginatedResponseDataSchema):
    data: List[SanctionsScreeningListSchema] = Field(..., alias="items")


# ==================== TRANSACTION MONITORING SCHEMAS ====================


class TransactionMonitoringSchema(ModelSchema):
    user: UserSchema

    class Meta:
        model = TransactionMonitoring
        fields = [
            "monitoring_id",
            "transaction_id",
            "alert_type",
            "risk_score",
            "risk_level",
            "description",
            "triggered_rules",
            "transaction_amount",
            "transaction_type",
            "transaction_date",
            "is_resolved",
            "resolution",
            "resolved_at",
            "is_reported",
            "reported_at",
            "created_at",
        ]


class TransactionMonitoringListSchema(BaseSchema):
    monitoring_id: UUID
    user: UserSchema
    transaction_id: UUID
    alert_type: str
    risk_score: Decimal
    risk_level: str
    transaction_amount: Decimal
    is_resolved: bool
    is_reported: bool
    created_at: datetime


class ResolveMonitoringAlertSchema(BaseSchema):
    resolution: str
    is_reported: bool = False


class TransactionMonitoringDataResponseSchema(BaseSchema):
    message: str
    data: TransactionMonitoringSchema


class TransactionMonitoringListDataResponseSchema(BaseSchema):
    message: str
    data: List[TransactionMonitoringListSchema]


class TransactionMonitoringPaginatedDataResponseSchema(PaginatedResponseDataSchema):
    data: List[TransactionMonitoringListSchema] = Field(..., alias="items")


# ==================== COMPLIANCE REPORT SCHEMAS ====================


class CreateComplianceReportSchema(BaseSchema):
    report_type: str
    report_period_start: date
    report_period_end: date

    @field_validator("report_period_end")
    @classmethod
    def validate_dates(cls, value: date, info):
        start = info.data.get("report_period_start")
        if start and value < start:
            raise ValueError("End date must be after start date")
        return value


class ComplianceReportSchema(ModelSchema):
    class Meta:
        model = ComplianceReport
        fields = [
            "report_id",
            "report_type",
            "report_period_start",
            "report_period_end",
            "summary",
            "total_transactions",
            "flagged_transactions",
            "total_users_screened",
            "high_risk_users",
            "data",
            "created_at",
        ]


class ComplianceReportListSchema(BaseSchema):
    report_id: UUID
    report_type: str
    report_period_start: date
    report_period_end: date
    total_transactions: int
    flagged_transactions: int
    created_at: datetime


class ComplianceReportDataResponseSchema(BaseSchema):
    message: str
    data: ComplianceReportSchema


class ComplianceReportListDataResponseSchema(BaseSchema):
    message: str
    data: List[ComplianceReportListSchema]


class ComplianceReportPaginatedDataResponseSchema(PaginatedResponseDataSchema):
    data: List[ComplianceReportListSchema] = Field(..., alias="items")


# ==================== COMPLIANCE STATISTICS SCHEMAS ====================


class ComplianceStatisticsSchema(BaseSchema):
    # KYC stats
    total_kyc_verifications: int
    pending_kyc_verifications: int
    approved_kyc_verifications: int
    rejected_kyc_verifications: int
    expired_kyc_verifications: int

    # AML stats
    total_aml_checks: int
    high_risk_aml_checks: int
    aml_checks_requiring_review: int

    # Sanctions stats
    total_sanctions_screenings: int
    sanctions_matches: int
    false_positives: int

    # Transaction monitoring stats
    total_alerts: int
    unresolved_alerts: int
    high_risk_alerts: int
    reported_alerts: int


class ComplianceStatisticsDataResponseSchema(BaseSchema):
    message: str
    data: ComplianceStatisticsSchema
