from django.contrib import admin
from apps.cards.models import Card


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = [
        "card_id",
        "masked_number",
        "user",
        "wallet",
        "card_brand",
        "card_type",
        "status",
        "is_frozen",
        "total_spent",
        "created_at",
    ]
    list_filter = [
        "card_type",
        "card_brand",
        "status",
        "is_frozen",
        "card_provider",
        "is_test_mode",
    ]
    search_fields = ["card_id", "card_number", "user__email", "nickname"]
    readonly_fields = [
        "card_id",
        "card_number",
        "cvv",
        "provider_card_id",
        "provider_metadata",
        "total_spent",
        "daily_spent",
        "monthly_spent",
        "last_used_at",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Card Information",
            {
                "fields": (
                    "card_id",
                    "user",
                    "wallet",
                    "card_type",
                    "card_brand",
                    "nickname",
                )
            },
        ),
        (
            "Card Details",
            {
                "fields": (
                    "card_number",
                    "card_holder_name",
                    "expiry_month",
                    "expiry_year",
                    "cvv",
                )
            },
        ),
        (
            "Provider Integration",
            {
                "fields": (
                    "card_provider",
                    "provider_card_id",
                    "provider_metadata",
                    "is_test_mode",
                )
            },
        ),
        ("Limits", {"fields": ("spending_limit", "daily_limit", "monthly_limit")}),
        (
            "Status & Controls",
            {
                "fields": (
                    "status",
                    "is_frozen",
                    "allow_online_transactions",
                    "allow_atm_withdrawals",
                    "allow_international_transactions",
                )
            },
        ),
        (
            "Usage Tracking",
            {"fields": ("total_spent", "daily_spent", "monthly_spent", "last_used_at")},
        ),
        (
            "Additional Info",
            {
                "fields": (
                    "created_for_merchant",
                    "billing_address",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
