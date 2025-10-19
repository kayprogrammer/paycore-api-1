from django.contrib import admin
from apps.loans.models import (
    AutoRepayment,
    LoanProduct,
    LoanApplication,
    LoanRepaymentSchedule,
    LoanRepayment,
    CreditScore,
)


@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = [
        "product_id",
        "name",
        "product_type",
        "min_amount",
        "max_amount",
        "min_interest_rate",
        "max_interest_rate",
        "min_tenure_months",
        "max_tenure_months",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "product_type",
        "is_active",
        "currency",
        "requires_collateral",
        "requires_guarantor",
    ]
    search_fields = ["name", "product_type"]
    readonly_fields = ["product_id", "created_at", "updated_at"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "product_id",
                    "name",
                    "description",
                    "product_type",
                    "currency",
                )
            },
        ),
        ("Loan Limits", {"fields": ("min_amount", "max_amount")}),
        ("Interest Rates", {"fields": ("min_interest_rate", "max_interest_rate")}),
        ("Tenure", {"fields": ("min_tenure_months", "max_tenure_months")}),
        (
            "Fees",
            {
                "fields": (
                    "processing_fee_percentage",
                    "processing_fee_fixed",
                    "late_payment_fee",
                    "early_repayment_fee_percentage",
                )
            },
        ),
        (
            "Requirements",
            {
                "fields": (
                    "min_credit_score",
                    "requires_collateral",
                    "requires_guarantor",
                    "min_account_age_days",
                )
            },
        ),
        ("Repayment", {"fields": ("allowed_repayment_frequencies",)}),
        ("Status", {"fields": ("is_active",)}),
        ("Eligibility", {"fields": ("eligibility_criteria",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = [
        "application_id",
        "user",
        "loan_product",
        "requested_amount",
        "approved_amount",
        "status",
        "credit_score",
        "tenure_months",
        "disbursed_at",
        "created_at",
    ]
    list_filter = [
        "status",
        "loan_product__product_type",
        "collateral_type",
        "credit_score_band",
        "repayment_frequency",
        "created_at",
        "disbursed_at",
    ]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "purpose",
        "guarantor_name",
        "guarantor_email",
    ]
    readonly_fields = [
        "application_id",
        "credit_score",
        "credit_score_band",
        "risk_assessment",
        "created_at",
        "updated_at",
        "reviewed_at",
        "disbursed_at",
    ]
    raw_id_fields = [
        "user",
        "loan_product",
        "wallet",
        "reviewed_by",
        "disbursement_transaction",
    ]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("application_id", "user", "loan_product", "wallet")},
        ),
        (
            "Loan Details",
            {
                "fields": (
                    "requested_amount",
                    "approved_amount",
                    "interest_rate",
                    "tenure_months",
                    "repayment_frequency",
                )
            },
        ),
        (
            "Calculated Amounts",
            {
                "fields": (
                    "processing_fee",
                    "total_interest",
                    "total_repayable",
                    "monthly_repayment",
                )
            },
        ),
        ("Purpose", {"fields": ("purpose", "purpose_details")}),
        (
            "Employment & Income",
            {"fields": ("employment_status", "employer_name", "monthly_income")},
        ),
        (
            "Collateral",
            {
                "fields": (
                    "collateral_type",
                    "collateral_value",
                    "collateral_description",
                )
            },
        ),
        (
            "Guarantor",
            {
                "fields": (
                    "guarantor_name",
                    "guarantor_phone",
                    "guarantor_email",
                    "guarantor_relationship",
                )
            },
        ),
        (
            "Credit Assessment",
            {"fields": ("credit_score", "credit_score_band", "risk_assessment")},
        ),
        (
            "Status & Review",
            {"fields": ("status", "reviewed_by", "reviewed_at", "rejection_reason")},
        ),
        ("Disbursement", {"fields": ("disbursed_at", "disbursement_transaction")}),
        ("Metadata", {"fields": ("metadata", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "user", "loan_product", "wallet", "wallet__currency", "reviewed_by"
            )
        )


@admin.register(LoanRepaymentSchedule)
class LoanRepaymentScheduleAdmin(admin.ModelAdmin):
    list_display = [
        "schedule_id",
        "loan",
        "installment_number",
        "due_date",
        "total_amount",
        "amount_paid",
        "outstanding_amount",
        "status",
        "days_overdue",
    ]
    list_filter = ["status", "due_date", "created_at"]
    search_fields = [
        "loan__user__email",
        "loan__user__first_name",
        "loan__user__last_name",
        "loan__application_id",
    ]
    readonly_fields = ["schedule_id", "created_at", "updated_at", "paid_at"]
    raw_id_fields = ["loan"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("schedule_id", "loan", "installment_number", "due_date")},
        ),
        (
            "Amounts",
            {
                "fields": (
                    "principal_amount",
                    "interest_amount",
                    "total_amount",
                    "amount_paid",
                    "outstanding_amount",
                )
            },
        ),
        ("Status", {"fields": ("status", "paid_at")}),
        ("Late Payment", {"fields": ("days_overdue", "late_fee")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("loan", "loan__user")


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = [
        "repayment_id",
        "loan",
        "amount",
        "principal_paid",
        "interest_paid",
        "reference",
        "status",
        "created_at",
    ]
    list_filter = ["status", "is_early_repayment", "payment_method", "created_at"]
    search_fields = [
        "reference",
        "external_reference",
        "loan__user__email",
        "loan__user__first_name",
        "loan__user__last_name",
        "loan__application_id",
    ]
    readonly_fields = ["repayment_id", "reference", "created_at", "updated_at"]
    raw_id_fields = ["loan", "schedule", "wallet", "transaction"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "repayment_id",
                    "loan",
                    "schedule",
                    "reference",
                    "external_reference",
                )
            },
        ),
        (
            "Payment Details",
            {"fields": ("amount", "principal_paid", "interest_paid", "late_fee_paid")},
        ),
        ("Early Repayment", {"fields": ("is_early_repayment", "early_repayment_fee")}),
        ("Payment Source", {"fields": ("wallet", "transaction", "payment_method")}),
        ("Status & Notes", {"fields": ("status", "notes")}),
        ("Metadata", {"fields": ("metadata", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("loan", "loan__user", "wallet", "transaction", "schedule")
        )


@admin.register(CreditScore)
class CreditScoreAdmin(admin.ModelAdmin):
    list_display = [
        "score_id",
        "user",
        "score",
        "score_band",
        "risk_level",
        "total_loans",
        "active_loans",
        "defaulted_loans",
        "created_at",
    ]
    list_filter = ["score_band", "risk_level", "created_at"]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
    ]
    readonly_fields = [
        "score_id",
        "score",
        "score_band",
        "payment_history_score",
        "credit_utilization_score",
        "account_age_score",
        "loan_history_score",
        "factors",
        "recommendations",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["user"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("score_id", "user", "score", "score_band", "risk_level")},
        ),
        (
            "Component Scores",
            {
                "fields": (
                    "payment_history_score",
                    "credit_utilization_score",
                    "account_age_score",
                    "loan_history_score",
                )
            },
        ),
        (
            "Loan Metrics",
            {
                "fields": (
                    "total_loans",
                    "active_loans",
                    "completed_loans",
                    "defaulted_loans",
                )
            },
        ),
        (
            "Payment Metrics",
            {"fields": ("on_time_payments", "late_payments", "missed_payments")},
        ),
        (
            "Financial Metrics",
            {"fields": ("total_borrowed", "total_repaid", "current_debt")},
        ),
        ("Account Info", {"fields": ("account_age_days",)}),
        ("Details", {"fields": ("factors", "recommendations")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")


@admin.register(AutoRepayment)
class AutoRepaymentAdmin(admin.ModelAdmin):
    list_display = [
        "auto_repayment_id",
        "loan",
        "wallet",
        "is_enabled",
        "status",
        "total_payments_made",
        "consecutive_failures",
        "last_payment_date",
        "created_at",
    ]
    list_filter = [
        "is_enabled",
        "status",
        "auto_pay_full_amount",
        "retry_on_failure",
        "created_at",
    ]
    search_fields = [
        "loan__user__email",
        "loan__user__first_name",
        "loan__user__last_name",
        "loan__application_id",
    ]
    readonly_fields = [
        "auto_repayment_id",
        "total_payments_made",
        "last_payment_date",
        "last_payment_amount",
        "last_failure_date",
        "last_failure_reason",
        "consecutive_failures",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["loan", "wallet"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "auto_repayment_id",
                    "loan",
                    "wallet",
                    "is_enabled",
                    "status",
                )
            },
        ),
        (
            "Payment Configuration",
            {
                "fields": (
                    "auto_pay_full_amount",
                    "custom_amount",
                    "days_before_due",
                )
            },
        ),
        (
            "Retry Configuration",
            {
                "fields": (
                    "retry_on_failure",
                    "max_retry_attempts",
                    "retry_interval_hours",
                )
            },
        ),
        (
            "Notification Settings",
            {
                "fields": (
                    "send_notification_on_success",
                    "send_notification_on_failure",
                )
            },
        ),
        (
            "Payment Tracking",
            {
                "fields": (
                    "total_payments_made",
                    "last_payment_date",
                    "last_payment_amount",
                )
            },
        ),
        (
            "Failure Tracking",
            {
                "fields": (
                    "consecutive_failures",
                    "last_failure_date",
                    "last_failure_reason",
                )
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("loan", "loan__user", "wallet", "wallet__currency")
        )
