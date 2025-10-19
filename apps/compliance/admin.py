from django.contrib import admin
from apps.compliance.models import (
    KYCVerification,
    KYCDocument,
    AMLCheck,
    SanctionsScreening,
    TransactionMonitoring,
    ComplianceReport,
)


@admin.register(KYCVerification)
class KYCVerificationAdmin(admin.ModelAdmin):
    list_display = [
        "kyc_id",
        "user",
        "level",
        "status",
        "first_name",
        "last_name",
        "nationality",
        "reviewed_at",
        "created_at",
    ]
    list_filter = [
        "status",
        "level",
        "nationality",
        "country",
        "document_type",
        "created_at",
    ]
    search_fields = [
        "kyc_id",
        "user__email",
        "first_name",
        "last_name",
        "document_number",
    ]
    readonly_fields = [
        "kyc_id",
        "is_approved",
        "is_expired",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["user", "reviewed_by"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "User & Status",
            {
                "fields": (
                    "kyc_id",
                    "user",
                    "level",
                    "status",
                    "is_approved",
                    "is_expired",
                )
            },
        ),
        (
            "Personal Information",
            {
                "fields": (
                    "first_name",
                    "middle_name",
                    "last_name",
                    "date_of_birth",
                    "nationality",
                )
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                )
            },
        ),
        (
            "Identity Document",
            {
                "fields": (
                    "document_type",
                    "document_number",
                    "document_expiry_date",
                    "document_issuing_country",
                )
            },
        ),
        (
            "Review",
            {
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                    "rejection_reason",
                    "expires_at",
                )
            },
        ),
        (
            "Additional Information",
            {"fields": ("notes", "ip_address")},
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "reviewed_by")


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = [
        "document_id",
        "kyc_verification",
        "document_type",
        "file_name",
        "file_size",
        "is_verified",
        "verified_at",
        "created_at",
    ]
    list_filter = [
        "document_type",
        "is_verified",
        "created_at",
    ]
    search_fields = [
        "document_id",
        "kyc_verification__kyc_id",
        "kyc_verification__user__email",
        "file_name",
    ]
    readonly_fields = ["document_id", "created_at", "updated_at"]
    raw_id_fields = ["kyc_verification"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "KYC Verification",
            {"fields": ("document_id", "kyc_verification", "document_type")},
        ),
        (
            "File Information",
            {"fields": ("file", "file_name", "file_size")},
        ),
        (
            "Verification Status",
            {"fields": ("is_verified", "verified_at")},
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("kyc_verification", "kyc_verification__user")
        )


@admin.register(AMLCheck)
class AMLCheckAdmin(admin.ModelAdmin):
    list_display = [
        "check_id",
        "user",
        "check_type",
        "risk_score",
        "risk_level",
        "passed",
        "requires_manual_review",
        "reviewed_at",
        "created_at",
    ]
    list_filter = [
        "risk_level",
        "passed",
        "requires_manual_review",
        "provider",
        "created_at",
    ]
    search_fields = [
        "check_id",
        "user__email",
        "check_type",
        "provider_reference",
    ]
    readonly_fields = ["check_id", "created_at", "updated_at"]
    raw_id_fields = ["user", "reviewed_by"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "check_id",
                    "user",
                    "transaction_id",
                    "check_type",
                )
            },
        ),
        (
            "Risk Assessment",
            {
                "fields": (
                    "risk_score",
                    "risk_level",
                    "passed",
                    "flagged_items",
                )
            },
        ),
        (
            "External Provider",
            {
                "fields": (
                    "provider",
                    "provider_reference",
                    "provider_response",
                )
            },
        ),
        (
            "Manual Review",
            {
                "fields": (
                    "requires_manual_review",
                    "reviewed_by",
                    "reviewed_at",
                    "review_notes",
                )
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "reviewed_by")


@admin.register(SanctionsScreening)
class SanctionsScreeningAdmin(admin.ModelAdmin):
    list_display = [
        "screening_id",
        "user",
        "full_name",
        "is_match",
        "match_score",
        "false_positive",
        "reviewed_at",
        "created_at",
    ]
    list_filter = [
        "is_match",
        "false_positive",
        "nationality",
        "provider",
        "created_at",
    ]
    search_fields = [
        "screening_id",
        "user__email",
        "full_name",
        "provider_reference",
    ]
    readonly_fields = ["screening_id", "created_at", "updated_at"]
    raw_id_fields = ["user", "reviewed_by"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "screening_id",
                    "user",
                    "full_name",
                    "date_of_birth",
                    "nationality",
                )
            },
        ),
        (
            "Screening Results",
            {
                "fields": (
                    "is_match",
                    "match_score",
                    "matched_lists",
                    "match_details",
                )
            },
        ),
        (
            "External Provider",
            {
                "fields": (
                    "provider",
                    "provider_reference",
                )
            },
        ),
        (
            "Review",
            {
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                    "false_positive",
                    "review_notes",
                )
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "reviewed_by")


@admin.register(TransactionMonitoring)
class TransactionMonitoringAdmin(admin.ModelAdmin):
    list_display = [
        "monitoring_id",
        "user",
        "transaction_id",
        "alert_type",
        "risk_level",
        "transaction_amount",
        "is_resolved",
        "is_reported",
        "created_at",
    ]
    list_filter = [
        "risk_level",
        "alert_type",
        "is_resolved",
        "is_reported",
        "created_at",
    ]
    search_fields = [
        "monitoring_id",
        "user__email",
        "transaction_id",
        "alert_type",
    ]
    readonly_fields = ["monitoring_id", "created_at", "updated_at"]
    raw_id_fields = ["user", "resolved_by"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "monitoring_id",
                    "user",
                    "transaction_id",
                    "alert_type",
                )
            },
        ),
        (
            "Risk Assessment",
            {
                "fields": (
                    "risk_score",
                    "risk_level",
                    "description",
                    "triggered_rules",
                )
            },
        ),
        (
            "Transaction Context",
            {
                "fields": (
                    "transaction_amount",
                    "transaction_type",
                    "transaction_date",
                )
            },
        ),
        (
            "Resolution",
            {
                "fields": (
                    "is_resolved",
                    "resolution",
                    "resolved_by",
                    "resolved_at",
                )
            },
        ),
        (
            "Reporting",
            {
                "fields": (
                    "is_reported",
                    "reported_at",
                )
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "resolved_by")


@admin.register(ComplianceReport)
class ComplianceReportAdmin(admin.ModelAdmin):
    list_display = [
        "report_id",
        "report_type",
        "report_period_start",
        "report_period_end",
        "total_transactions",
        "flagged_transactions",
        "total_users_screened",
        "high_risk_users",
        "created_at",
    ]
    list_filter = [
        "report_type",
        "report_period_start",
        "created_at",
    ]
    search_fields = [
        "report_id",
        "report_type",
    ]
    readonly_fields = ["report_id", "created_at", "updated_at"]
    raw_id_fields = ["generated_by"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Report Information",
            {
                "fields": (
                    "report_id",
                    "report_type",
                    "report_period_start",
                    "report_period_end",
                )
            },
        ),
        (
            "Summary",
            {"fields": ("summary",)},
        ),
        (
            "Statistics",
            {
                "fields": (
                    "total_transactions",
                    "flagged_transactions",
                    "total_users_screened",
                    "high_risk_users",
                )
            },
        ),
        (
            "Detailed Data",
            {"fields": ("data",)},
        ),
        (
            "File",
            {"fields": ("file",)},
        ),
        (
            "Metadata",
            {
                "fields": (
                    "generated_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("generated_by")
