from django.contrib import admin
from apps.investments.models import (
    InvestmentProduct,
    Investment,
    InvestmentReturn,
    InvestmentPortfolio,
)


@admin.register(InvestmentProduct)
class InvestmentProductAdmin(admin.ModelAdmin):
    list_display = [
        "product_id",
        "name",
        "product_type",
        "interest_rate",
        "risk_level",
        "min_amount",
        "is_active",
        "is_available",
        "slots_taken",
    ]
    list_filter = [
        "product_type",
        "risk_level",
        "is_active",
        "is_capital_guaranteed",
        "allows_early_liquidation",
        "currency",
    ]
    search_fields = ["name", "product_id"]
    readonly_fields = ["product_id", "created_at", "updated_at", "is_available"]
    raw_id_fields = ["currency"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "product_id",
                    "name",
                    "product_type",
                    "description",
                    "is_active",
                )
            },
        ),
        (
            "Financial Details",
            {
                "fields": (
                    "currency",
                    "min_amount",
                    "max_amount",
                    "interest_rate",
                    "payout_frequency",
                )
            },
        ),
        (
            "Duration",
            {"fields": ("min_duration_days", "max_duration_days")},
        ),
        (
            "Risk & Features",
            {
                "fields": (
                    "risk_level",
                    "is_capital_guaranteed",
                    "allows_early_liquidation",
                    "early_liquidation_penalty",
                    "allows_auto_renewal",
                )
            },
        ),
        (
            "Availability",
            {
                "fields": (
                    "available_slots",
                    "slots_taken",
                    "is_available",
                )
            },
        ),
        (
            "Additional Information",
            {"fields": ("terms_and_conditions", "benefits")},
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("currency")


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = [
        "investment_id",
        "user",
        "product",
        "principal_amount",
        "status",
        "maturity_date",
        "days_to_maturity",
        "auto_renew",
        "created_at",
    ]
    list_filter = [
        "status",
        "auto_renew",
        "product__product_type",
        "product__risk_level",
        "created_at",
    ]
    search_fields = [
        "investment_id",
        "user__email",
        "user__first_name",
        "user__last_name",
        "product__name",
    ]
    readonly_fields = [
        "investment_id",
        "expected_returns",
        "actual_returns",
        "current_value",
        "days_to_maturity",
        "days_invested",
        "is_active",
        "is_matured",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = [
        "user",
        "product",
        "wallet",
        "renewed_from",
        "investment_transaction",
        "payout_transaction",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "investment_id",
                    "user",
                    "product",
                    "wallet",
                    "status",
                )
            },
        ),
        (
            "Investment Details",
            {
                "fields": (
                    "principal_amount",
                    "interest_rate",
                    "duration_days",
                    "start_date",
                    "maturity_date",
                )
            },
        ),
        (
            "Returns",
            {
                "fields": (
                    "expected_returns",
                    "actual_returns",
                    "current_value",
                    "total_payout",
                )
            },
        ),
        (
            "Status & Properties",
            {
                "fields": (
                    "is_active",
                    "is_matured",
                    "days_to_maturity",
                    "days_invested",
                )
            },
        ),
        (
            "Auto-Renewal",
            {
                "fields": (
                    "auto_renew",
                    "renewed_from",
                )
            },
        ),
        (
            "Early Liquidation",
            {
                "fields": (
                    "liquidation_date",
                    "liquidation_penalty",
                    "actual_maturity_date",
                )
            },
        ),
        (
            "Transactions",
            {
                "fields": (
                    "investment_transaction",
                    "payout_transaction",
                )
            },
        ),
        ("Notes", {"fields": ("notes",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "product", "wallet", "wallet__currency")
        )


@admin.register(InvestmentReturn)
class InvestmentReturnAdmin(admin.ModelAdmin):
    list_display = [
        "return_id",
        "investment",
        "amount",
        "payout_date",
        "actual_payout_date",
        "is_paid",
        "created_at",
    ]
    list_filter = [
        "is_paid",
        "payout_date",
        "created_at",
    ]
    search_fields = [
        "return_id",
        "investment__investment_id",
        "investment__user__email",
    ]
    readonly_fields = [
        "return_id",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["investment", "transaction"]
    date_hierarchy = "payout_date"

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "return_id",
                    "investment",
                    "amount",
                    "is_paid",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "payout_date",
                    "actual_payout_date",
                )
            },
        ),
        (
            "Transaction",
            {"fields": ("transaction",)},
        ),
        ("Notes", {"fields": ("notes",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("investment", "investment__user", "transaction")
        )


@admin.register(InvestmentPortfolio)
class InvestmentPortfolioAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "total_invested",
        "total_active_investments",
        "total_returns_earned",
        "average_return_rate",
        "active_investments_count",
        "last_calculated_at",
    ]
    list_filter = [
        "last_calculated_at",
        "created_at",
    ]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
    ]
    readonly_fields = [
        "total_invested",
        "total_active_investments",
        "total_returns_earned",
        "total_matured_value",
        "active_investments_count",
        "matured_investments_count",
        "total_investments_count",
        "average_return_rate",
        "last_calculated_at",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["user"]

    fieldsets = (
        (
            "User",
            {"fields": ("user",)},
        ),
        (
            "Financial Totals",
            {
                "fields": (
                    "total_invested",
                    "total_active_investments",
                    "total_returns_earned",
                    "total_matured_value",
                )
            },
        ),
        (
            "Investment Counts",
            {
                "fields": (
                    "active_investments_count",
                    "matured_investments_count",
                    "total_investments_count",
                )
            },
        ),
        (
            "Performance",
            {"fields": ("average_return_rate",)},
        ),
        (
            "Metadata",
            {
                "fields": (
                    "last_calculated_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")
