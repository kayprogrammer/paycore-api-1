from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
import json

from apps.audit_logs.models import AuditLog, EventType, EventCategory, SeverityLevel


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for audit logs"""

    list_display = [
        "id",
        "event_badge",
        "category_badge",
        "severity_badge",
        "user_email",
        "action_short",
        "ip_address",
        "device_type",
        "response_status_badge",
        "created_at",
    ]

    list_filter = [
        "event_category",
        "event_type",
        "severity",
        "is_compliance_event",
        "device_type",
        "response_status",
        "created_at",
    ]

    search_fields = [
        "user_email",
        "action",
        "ip_address",
        "resource_type",
        "resource_id",
        "request_path",
    ]

    readonly_fields = [
        "id",
        "event_type",
        "event_category",
        "severity",
        "user",
        "user_email",
        "ip_address",
        "user_agent",
        "device_type",
        "action",
        "resource_type",
        "resource_id",
        "request_method",
        "request_path",
        "request_data_formatted",
        "response_status",
        "old_values_formatted",
        "new_values_formatted",
        "metadata_formatted",
        "error_message",
        "stack_trace",
        "session_id",
        "is_compliance_event",
        "retention_period_days",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Event Information",
            {
                "fields": (
                    "id",
                    "event_type",
                    "event_category",
                    "severity",
                    "created_at",
                )
            },
        ),
        ("User Information", {"fields": ("user", "user_email", "session_id")}),
        (
            "Request Information",
            {
                "fields": (
                    "ip_address",
                    "user_agent",
                    "device_type",
                    "request_method",
                    "request_path",
                    "request_data_formatted",
                    "response_status",
                )
            },
        ),
        (
            "Action Details",
            {
                "fields": (
                    "action",
                    "resource_type",
                    "resource_id",
                )
            },
        ),
        (
            "Changes",
            {
                "fields": ("old_values_formatted", "new_values_formatted"),
                "classes": ("collapse",),
            },
        ),
        (
            "Additional Context",
            {
                "fields": ("metadata_formatted", "error_message", "stack_trace"),
                "classes": ("collapse",),
            },
        ),
        ("Compliance", {"fields": ("is_compliance_event", "retention_period_days")}),
    )

    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def event_badge(self, obj):
        """Display event type as a badge"""
        color_map = {
            "authentication": "#17a2b8",  # info
            "security": "#dc3545",  # danger
            "transaction": "#28a745",  # success
            "payment": "#ffc107",  # warning
            "compliance": "#6c757d",  # secondary
        }
        color = color_map.get(obj.event_category, "#007bff")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_event_type_display(),
        )

    event_badge.short_description = "Event Type"

    def category_badge(self, obj):
        """Display category as a badge"""
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            obj.get_event_category_display(),
        )

    category_badge.short_description = "Category"

    def severity_badge(self, obj):
        """Display severity as a colored badge"""
        color_map = {
            SeverityLevel.INFO: "#17a2b8",
            SeverityLevel.WARNING: "#ffc107",
            SeverityLevel.ERROR: "#fd7e14",
            SeverityLevel.CRITICAL: "#dc3545",
        }
        color = color_map.get(obj.severity, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_severity_display().upper(),
        )

    severity_badge.short_description = "Severity"

    def response_status_badge(self, obj):
        """Display HTTP status code as a colored badge"""
        if not obj.response_status:
            return "-"

        if obj.response_status < 300:
            color = "#28a745"  # green
        elif obj.response_status < 400:
            color = "#17a2b8"  # blue
        elif obj.response_status < 500:
            color = "#ffc107"  # yellow
        else:
            color = "#dc3545"  # red

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.response_status,
        )

    response_status_badge.short_description = "Status"

    def action_short(self, obj):
        """Display truncated action"""
        if len(obj.action) > 50:
            return obj.action[:50] + "..."
        return obj.action

    action_short.short_description = "Action"

    def request_data_formatted(self, obj):
        """Format request data as JSON"""
        if not obj.request_data:
            return "-"
        return mark_safe(f"<pre>{json.dumps(obj.request_data, indent=2)}</pre>")

    request_data_formatted.short_description = "Request Data"

    def old_values_formatted(self, obj):
        """Format old values as JSON"""
        if not obj.old_values:
            return "-"
        return mark_safe(f"<pre>{json.dumps(obj.old_values, indent=2)}</pre>")

    old_values_formatted.short_description = "Old Values"

    def new_values_formatted(self, obj):
        """Format new values as JSON"""
        if not obj.new_values:
            return "-"
        return mark_safe(f"<pre>{json.dumps(obj.new_values, indent=2)}</pre>")

    new_values_formatted.short_description = "New Values"

    def metadata_formatted(self, obj):
        """Format metadata as JSON"""
        if not obj.metadata:
            return "-"
        return mark_safe(f"<pre>{json.dumps(obj.metadata, indent=2)}</pre>")

    metadata_formatted.short_description = "Metadata"
