from django.contrib import admin
from apps.payments.models import (
    PaymentLink,
    Invoice,
    InvoiceItem,
    Payment,
    MerchantAPIKey,
)


@admin.register(PaymentLink)
class PaymentLinkAdmin(admin.ModelAdmin):
    list_display = [
        "link_id",
        "title",
        "slug",
        "user",
        "amount",
        "is_amount_fixed",
        "status",
        "payments_count",
        "total_collected",
        "created_at",
    ]
    list_filter = ["status", "is_amount_fixed", "is_single_use", "created_at"]
    search_fields = [
        "title",
        "slug",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]
    readonly_fields = [
        "link_id",
        "views_count",
        "payments_count",
        "total_collected",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("link_id", "user", "wallet", "title", "description", "slug")},
        ),
        (
            "Payment Configuration",
            {"fields": ("amount", "is_amount_fixed", "min_amount", "max_amount")},
        ),
        (
            "Settings",
            {"fields": ("status", "is_single_use", "expires_at", "redirect_url")},
        ),
        ("Branding", {"fields": ("logo_url", "brand_color")}),
        ("Analytics", {"fields": ("views_count", "payments_count", "total_collected")}),
        ("Metadata", {"fields": ("metadata", "created_at", "updated_at")}),
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_number",
        "title",
        "customer_name",
        "customer_email",
        "total_amount",
        "amount_due",
        "status",
        "due_date",
        "created_at",
    ]
    list_filter = ["status", "issue_date", "due_date", "created_at"]
    search_fields = [
        "invoice_number",
        "title",
        "customer_name",
        "customer_email",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]
    readonly_fields = [
        "invoice_id",
        "invoice_number",
        "created_at",
        "updated_at",
        "paid_at",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "invoice_id",
                    "invoice_number",
                    "user",
                    "wallet",
                    "title",
                    "description",
                    "notes",
                )
            },
        ),
        (
            "Customer Information",
            {
                "fields": (
                    "customer_name",
                    "customer_email",
                    "customer_phone",
                    "customer_address",
                )
            },
        ),
        (
            "Financial Details",
            {
                "fields": (
                    "subtotal",
                    "tax_amount",
                    "discount_amount",
                    "total_amount",
                    "amount_paid",
                    "amount_due",
                )
            },
        ),
        ("Status & Dates", {"fields": ("status", "issue_date", "due_date", "paid_at")}),
        ("Settings", {"fields": ("payment_link",)}),
        ("Metadata", {"fields": ("metadata", "created_at", "updated_at")}),
    )


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = [
        "item_id",
        "invoice",
        "description",
        "quantity",
        "unit_price",
        "amount",
    ]
    list_filter = ["created_at"]
    search_fields = ["description", "invoice__invoice_number"]
    readonly_fields = ["item_id", "created_at", "updated_at"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "payment_id",
        "reference",
        "payer_name",
        "merchant_user",
        "amount",
        "fee_amount",
        "net_amount",
        "status",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = [
        "reference",
        "payer_name",
        "payer_email",
        "merchant_user__email",
        "merchant_user__first_name",
        "merchant_user__last_name",
    ]
    readonly_fields = [
        "payment_id",
        "reference",
        "external_reference",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("payment_id", "reference", "external_reference")},
        ),
        ("Links", {"fields": ("payment_link", "invoice", "transaction")}),
        (
            "Payer Information",
            {"fields": ("payer_name", "payer_email", "payer_phone", "payer_wallet")},
        ),
        ("Merchant Information", {"fields": ("merchant_user", "merchant_wallet")}),
        (
            "Payment Details",
            {"fields": ("amount", "fee_amount", "net_amount", "status")},
        ),
        ("Metadata", {"fields": ("metadata", "created_at", "updated_at")}),
    )


@admin.register(MerchantAPIKey)
class MerchantAPIKeyAdmin(admin.ModelAdmin):
    list_display = [
        "key_id",
        "name",
        "prefix",
        "user",
        "is_active",
        "is_test_mode",
        "requests_count",
        "last_used_at",
        "created_at",
    ]
    list_filter = ["is_active", "is_test_mode", "created_at"]
    search_fields = [
        "name",
        "prefix",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]
    readonly_fields = [
        "key_id",
        "key",
        "prefix",
        "requests_count",
        "last_used_at",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        ("Basic Information", {"fields": ("key_id", "user", "name", "key", "prefix")}),
        ("Settings", {"fields": ("is_active", "is_test_mode")}),
        (
            "Permissions",
            {
                "fields": (
                    "can_create_links",
                    "can_create_invoices",
                    "can_view_payments",
                )
            },
        ),
        ("Usage Stats", {"fields": ("requests_count", "last_used_at")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )
