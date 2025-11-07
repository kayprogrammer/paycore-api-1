from django.contrib import admin
from .models import Wallet, Currency


class CurrencyAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "symbol",
    )
    list_filter = (
        "is_active",
        "is_crypto",
    )
    search_fields = (
        "code",
        "name",
    )


class WalletAdmin(admin.ModelAdmin):
    list_display = (
        "wallet_id",
        "user",
        "currency",
        "available_balance",
        "balance",
        "created_at",
    )

    search_fields = (
        "wallet_id",
        "user__email",
    )

    list_filter = (
        "currency",
        "created_at",
    )


admin.site.register(Wallet, WalletAdmin)
admin.site.register(Currency, CurrencyAdmin)
