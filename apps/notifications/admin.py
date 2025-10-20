from django.contrib import admin
from apps.notifications.models import (
    Notification,
    NotificationTemplate,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "title",
        "notification_type",
        "priority",
        "is_read",
        "sent_via_push",
        "sent_via_websocket",
        "created_at",
    ]
    list_filter = [
        "notification_type",
        "priority",
        "is_read",
        "sent_via_push",
        "sent_via_websocket",
        "created_at",
    ]
    search_fields = ["user__email", "title", "message", "id"]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "read_at",
        "push_sent_at",
        "websocket_sent_at",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("id", "user", "title", "message")}),
        ("Classification", {"fields": ("notification_type", "priority")}),
        ("Status", {"fields": ("is_read", "read_at")}),
        (
            "Delivery Tracking",
            {
                "fields": (
                    "sent_via_push",
                    "push_sent_at",
                    "sent_via_websocket",
                    "websocket_sent_at",
                )
            },
        ),
        ("Related Object", {"fields": ("related_object_type", "related_object_id")}),
        ("Action Data", {"fields": ("action_url", "action_data")}),
        ("Metadata", {"fields": ("metadata", "expires_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "notification_type",
        "priority",
        "is_active",
        "created_at",
    ]
    list_filter = ["notification_type", "priority", "is_active", "created_at"]
    search_fields = ["name", "title_template", "message_template"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["name"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("id", "name", "notification_type", "priority", "is_active")},
        ),
        (
            "Template Content",
            {
                "fields": ("title_template", "message_template", "action_url_template"),
                "description": "Use {{variable}} for variable substitution",
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
