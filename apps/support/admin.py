from django.contrib import admin
from apps.support.models import (
    SupportTicket,
    TicketMessage,
    TicketAttachment,
    FAQ,
    CannedResponse,
    TicketEscalation,
)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        "ticket_number",
        "subject",
        "user",
        "category",
        "priority",
        "status",
        "assigned_to",
        "created_at",
    ]
    list_filter = ["status", "priority", "category", "created_at"]
    search_fields = ["ticket_number", "subject", "user__email", "description"]
    readonly_fields = ["ticket_id", "ticket_number", "created_at", "updated_at"]
    raw_id_fields = ["user", "assigned_to"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Ticket Info", {"fields": ("ticket_id", "ticket_number", "user")}),
        (
            "Details",
            {"fields": ("subject", "description", "category", "priority", "status")},
        ),
        ("Assignment", {"fields": ("assigned_to", "assigned_at")}),
        (
            "Related Entities",
            {
                "fields": (
                    "related_transaction_id",
                    "related_wallet_id",
                    "related_loan_id",
                    "related_investment_id",
                )
            },
        ),
        (
            "Tracking",
            {
                "fields": (
                    "first_response_at",
                    "resolved_at",
                    "closed_at",
                    "reopened_at",
                )
            },
        ),
        ("Feedback", {"fields": ("satisfaction_rating", "feedback")}),
        (
            "Metadata",
            {"fields": ("tags", "internal_notes", "created_at", "updated_at")},
        ),
    )


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = [
        "ticket",
        "sender",
        "is_from_customer",
        "is_internal",
        "is_read",
        "created_at",
    ]
    list_filter = ["is_from_customer", "is_internal", "is_read", "created_at"]
    search_fields = ["message", "ticket__ticket_number", "sender__email"]
    readonly_fields = ["message_id", "created_at"]
    raw_id_fields = ["ticket", "sender"]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = [
        "question",
        "category",
        "is_published",
        "view_count",
        "helpfulness_score",
        "order",
    ]
    list_filter = ["category", "is_published", "created_at"]
    search_fields = ["question", "answer"]
    readonly_fields = [
        "faq_id",
        "view_count",
        "helpful_count",
        "not_helpful_count",
        "helpfulness_score",
    ]

    fieldsets = (
        ("Content", {"fields": ("question", "answer", "category")}),
        ("Display", {"fields": ("order", "is_published")}),
        (
            "Metrics",
            {
                "fields": (
                    "view_count",
                    "helpful_count",
                    "not_helpful_count",
                    "helpfulness_score",
                )
            },
        ),
        ("SEO", {"fields": ("tags",)}),
    )


@admin.register(CannedResponse)
class CannedResponseAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "is_active", "usage_count", "created_by"]
    list_filter = ["category", "is_active", "created_at"]
    search_fields = ["title", "content"]
    readonly_fields = ["response_id", "usage_count"]
    raw_id_fields = ["created_by"]
