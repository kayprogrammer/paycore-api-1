from django.db import models
from django.contrib.auth import get_user_model
from apps.common.models import BaseModel

User = get_user_model()


class EventCategory(models.TextChoices):
    AUTHENTICATION = "authentication", "Authentication"
    AUTHORIZATION = "authorization", "Authorization"
    ACCOUNT = "account", "Account Management"
    TRANSACTION = "transaction", "Transaction"
    PAYMENT = "payment", "Payment"
    LOAN = "loan", "Loan"
    INVESTMENT = "investment", "Investment"
    COMPLIANCE = "compliance", "Compliance"
    SUPPORT = "support", "Support"
    NOTIFICATION = "notification", "Notification"
    SECURITY = "security", "Security"
    SYSTEM = "system", "System"
    DATA_ACCESS = "data_access", "Data Access"
    DATA_MODIFICATION = "data_modification", "Data Modification"
    ADMIN = "admin", "Admin Action"


class EventType(models.TextChoices):
    # Authentication Events
    LOGIN_SUCCESS = "login_success", "Login Success"
    LOGIN_FAILED = "login_failed", "Login Failed"
    LOGOUT = "logout", "Logout"
    PASSWORD_CHANGE = "password_change", "Password Change"
    PASSWORD_RESET = "password_reset", "Password Reset"
    MFA_ENABLED = "mfa_enabled", "MFA Enabled"
    MFA_DISABLED = "mfa_disabled", "MFA Disabled"
    BIOMETRICS_ENABLED = "biometrics_enabled", "Biometrics Enabled"
    BIOMETRICS_DISABLED = "biometrics_disabled", "Biometrics Disabled"

    # Account Events
    ACCOUNT_CREATED = "account_created", "Account Created"
    ACCOUNT_UPDATED = "account_updated", "Account Updated"
    ACCOUNT_DELETED = "account_deleted", "Account Deleted"
    ACCOUNT_SUSPENDED = "account_suspended", "Account Suspended"
    ACCOUNT_REACTIVATED = "account_reactivated", "Account Reactivated"
    EMAIL_VERIFIED = "email_verified", "Email Verified"
    PROFILE_UPDATED = "profile_updated", "Profile Updated"

    # Transaction Events
    TRANSACTION_CREATED = "transaction_created", "Transaction Created"
    TRANSACTION_COMPLETED = "transaction_completed", "Transaction Completed"
    TRANSACTION_FAILED = "transaction_failed", "Transaction Failed"
    TRANSACTION_REVERSED = "transaction_reversed", "Transaction Reversed"

    # Payment Events
    PAYMENT_INITIATED = "payment_initiated", "Payment Initiated"
    PAYMENT_COMPLETED = "payment_completed", "Payment Completed"
    PAYMENT_FAILED = "payment_failed", "Payment Failed"
    PAYMENT_REFUNDED = "payment_refunded", "Payment Refunded"

    # Loan Events
    LOAN_APPLIED = "loan_applied", "Loan Applied"
    LOAN_APPROVED = "loan_approved", "Loan Approved"
    LOAN_REJECTED = "loan_rejected", "Loan Rejected"
    LOAN_DISBURSED = "loan_disbursed", "Loan Disbursed"
    LOAN_REPAYMENT = "loan_repayment", "Loan Repayment"

    # Investment Events
    INVESTMENT_CREATED = "investment_created", "Investment Created"
    INVESTMENT_UPDATED = "investment_updated", "Investment Updated"
    INVESTMENT_WITHDRAWN = "investment_withdrawn", "Investment Withdrawn"

    # Compliance Events
    KYC_SUBMITTED = "kyc_submitted", "KYC Submitted"
    KYC_APPROVED = "kyc_approved", "KYC Approved"
    KYC_REJECTED = "kyc_rejected", "KYC Rejected"
    DOCUMENT_UPLOADED = "document_uploaded", "Document Uploaded"
    DOCUMENT_VERIFIED = "document_verified", "Document Verified"

    # Security Events
    SUSPICIOUS_ACTIVITY = "suspicious_activity", "Suspicious Activity"
    FAILED_LOGIN_ATTEMPTS = "failed_login_attempts", "Failed Login Attempts"
    IP_BLOCKED = "ip_blocked", "IP Blocked"
    DEVICE_REGISTERED = "device_registered", "Device Registered"
    DEVICE_REMOVED = "device_removed", "Device Removed"

    # Data Access Events
    DATA_VIEWED = "data_viewed", "Data Viewed"
    DATA_EXPORTED = "data_exported", "Data Exported"
    SENSITIVE_DATA_ACCESS = "sensitive_data_access", "Sensitive Data Access"

    # Admin Events
    ADMIN_ACTION = "admin_action", "Admin Action"
    BULK_OPERATION = "bulk_operation", "Bulk Operation"
    SETTINGS_CHANGED = "settings_changed", "Settings Changed"

    # System Events
    SYSTEM_ERROR = "system_error", "System Error"
    API_CALL = "api_call", "API Call"
    SCHEDULED_TASK = "scheduled_task", "Scheduled Task"


class SeverityLevel(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"
    CRITICAL = "critical", "Critical"


class AuditLog(BaseModel):
    """
    Comprehensive audit logging for all system activities
    Tracks user actions, system events, and changes for compliance and security
    """

    # Event Information
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        db_index=True,
        help_text="Type of event that occurred",
    )
    event_category = models.CharField(
        max_length=50,
        choices=EventCategory.choices,
        db_index=True,
        help_text="Category of the event",
    )
    severity = models.CharField(
        max_length=20,
        choices=SeverityLevel.choices,
        default=SeverityLevel.INFO,
        db_index=True,
        help_text="Severity level of the event",
    )

    # User Information
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="User who performed the action (null for system events)",
    )
    user_email = models.EmailField(
        null=True,
        blank=True,
        help_text="User email at time of event (preserved if user deleted)",
    )

    # Request Information
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, db_index=True, help_text="IP address of the request"
    )
    user_agent = models.TextField(
        null=True, blank=True, help_text="User agent string from request"
    )
    device_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Device type (mobile, web, tablet)",
    )

    # Action Details
    action = models.CharField(
        max_length=255, help_text="Description of the action performed"
    )
    resource_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Type of resource affected (e.g., User, Transaction, Loan)",
    )
    resource_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="ID of the affected resource",
    )

    # Request/Response Data
    request_method = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="HTTP method (GET, POST, PUT, DELETE, etc.)",
    )
    request_path = models.CharField(
        max_length=500, null=True, blank=True, help_text="API endpoint path"
    )
    request_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Request payload (sanitized - no sensitive data)",
    )
    response_status = models.IntegerField(
        null=True, blank=True, help_text="HTTP response status code"
    )

    # Changes Tracking
    old_values = models.JSONField(
        null=True, blank=True, help_text="Previous values before change"
    )
    new_values = models.JSONField(
        null=True, blank=True, help_text="New values after change"
    )

    # Additional Context
    metadata = models.JSONField(
        null=True, blank=True, help_text="Additional context and metadata"
    )
    error_message = models.TextField(
        null=True, blank=True, help_text="Error message if action failed"
    )
    stack_trace = models.TextField(
        null=True, blank=True, help_text="Stack trace for errors"
    )

    # Session Information
    session_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Session identifier",
    )

    # Compliance
    is_compliance_event = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag for events requiring compliance audit",
    )
    retention_period_days = models.IntegerField(
        default=2555,  # 7 years for financial compliance
        help_text="How long to retain this log (in days)",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["event_category", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
            models.Index(fields=["ip_address", "-created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["is_compliance_event", "-created_at"]),
        ]

    def __str__(self):
        user_info = self.user_email or "System"
        return f"{self.event_type} - {user_info} - {self.created_at}"

    @property
    def is_suspicious(self):
        return (
            self.event_type
            in [
                EventType.SUSPICIOUS_ACTIVITY,
                EventType.FAILED_LOGIN_ATTEMPTS,
                EventType.IP_BLOCKED,
            ]
            or self.severity == SeverityLevel.CRITICAL
        )

    @property
    def is_financial_event(self):
        return self.event_category in [
            EventCategory.TRANSACTION,
            EventCategory.PAYMENT,
            EventCategory.LOAN,
            EventCategory.INVESTMENT,
        ]
