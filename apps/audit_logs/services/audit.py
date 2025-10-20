from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.http import HttpRequest
import logging, traceback

from apps.audit_logs.models import AuditLog, EventType, EventCategory, SeverityLevel

User = get_user_model()
logger = logging.getLogger(__name__)


class AuditLogService:
    """Service for creating and managing audit logs"""

    # Sensitive fields to exclude from request data logging
    SENSITIVE_FIELDS = {
        "password",
        "token",
        "access",
        "refresh",
        "secret",
        "api_key",
        "private_key",
        "credit_card",
        "cvv",
        "pin",
        "otp",
        "ssn",
        "trust_token",
        "authorization",
        "cookie",
    }

    @staticmethod
    def _sanitize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from data before logging"""
        if not data:
            return {}

        sanitized = {}
        for key, value in data.items():
            # Check if key contains sensitive keywords
            if any(
                sensitive in key.lower()
                for sensitive in AuditLogService.SENSITIVE_FIELDS
            ):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = AuditLogService._sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    (
                        AuditLogService._sanitize_data(item)
                        if isinstance(item, dict)
                        else item
                    )
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    @staticmethod
    def _get_client_ip(request: Optional[HttpRequest]) -> Optional[str]:
        """Extract client IP address from request"""
        if not request:
            return None

        # Check for proxy headers
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        return request.META.get("REMOTE_ADDR")

    @staticmethod
    def _get_user_agent(request: Optional[HttpRequest]) -> Optional[str]:
        if not request:
            return None
        return request.META.get("HTTP_USER_AGENT")

    @staticmethod
    def _detect_device_type(user_agent: Optional[str]) -> Optional[str]:
        if not user_agent:
            return None

        user_agent_lower = user_agent.lower()
        if (
            "mobile" in user_agent_lower
            or "android" in user_agent_lower
            or "iphone" in user_agent_lower
        ):
            return "mobile"
        elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
            return "tablet"
        else:
            return "web"

    @staticmethod
    def log(
        event_type: str,
        event_category: str,
        action: str,
        user: Optional[User] = None,
        request: Optional[HttpRequest] = None,
        severity: str = SeverityLevel.INFO,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_status: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        is_compliance_event: bool = False,
        session_id: Optional[str] = None,
    ) -> AuditLog:
        try:
            # Extract request metadata
            ip_address = AuditLogService._get_client_ip(request)
            user_agent = AuditLogService._get_user_agent(request)
            device_type = AuditLogService._detect_device_type(user_agent)

            # Sanitize sensitive data
            sanitized_request_data = (
                AuditLogService._sanitize_data(request_data) if request_data else None
            )
            sanitized_old_values = (
                AuditLogService._sanitize_data(old_values) if old_values else None
            )
            sanitized_new_values = (
                AuditLogService._sanitize_data(new_values) if new_values else None
            )

            audit_log = AuditLog.objects.create(
                event_type=event_type,
                event_category=event_category,
                severity=severity,
                user=user,
                user_email=user.email if user else None,
                ip_address=ip_address,
                user_agent=user_agent,
                device_type=device_type,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                request_method=request.method if request else None,
                request_path=request.path if request else None,
                request_data=sanitized_request_data,
                response_status=response_status,
                old_values=sanitized_old_values,
                new_values=sanitized_new_values,
                metadata=metadata,
                error_message=error_message,
                session_id=session_id,
                is_compliance_event=is_compliance_event,
            )

            # Log suspicious activities
            if audit_log.is_suspicious:
                logger.warning(
                    f"Suspicious activity detected: {event_type} - User: {user_email or 'System'} - IP: {ip_address}"
                )

            return audit_log

        except Exception as e:
            # Log error but don't fail the main operation
            logger.error(
                f"Failed to create audit log: {str(e)}\n{traceback.format_exc()}"
            )
            return None

    @staticmethod
    def log_authentication(
        event_type: str,
        user: Optional[User],
        request: Optional[HttpRequest],
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        severity = SeverityLevel.INFO if success else SeverityLevel.WARNING

        return AuditLogService.log(
            event_type=event_type,
            event_category=EventCategory.AUTHENTICATION,
            action=f"User authentication: {event_type}",
            user=user,
            request=request,
            severity=severity,
            resource_type="User",
            resource_id=user.id if user else None,
            response_status=200 if success else 401,
            error_message=error_message,
            metadata=metadata,
            is_compliance_event=True,
        )

    @staticmethod
    def log_data_change(
        event_type: str,
        user: User,
        resource_type: str,
        resource_id: Any,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
        request: Optional[HttpRequest] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        return AuditLogService.log(
            event_type=event_type,
            event_category=EventCategory.DATA_MODIFICATION,
            action=f"{resource_type} modified",
            user=user,
            request=request,
            resource_type=resource_type,
            resource_id=str(resource_id),
            old_values=old_values,
            new_values=new_values,
            metadata=metadata,
            is_compliance_event=True,
        )

    @staticmethod
    def log_transaction(
        event_type: str,
        user: User,
        transaction_id: Any,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        request: Optional[HttpRequest] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        severity = SeverityLevel.INFO if success else SeverityLevel.ERROR

        transaction_metadata = metadata or {}
        if amount is not None:
            transaction_metadata["amount"] = amount
        if currency:
            transaction_metadata["currency"] = currency

        return AuditLogService.log(
            event_type=event_type,
            event_category=EventCategory.TRANSACTION,
            action=f"Transaction {event_type}",
            user=user,
            request=request,
            severity=severity,
            resource_type="Transaction",
            resource_id=str(transaction_id),
            response_status=200 if success else 400,
            error_message=error_message,
            metadata=transaction_metadata,
            is_compliance_event=True,
        )

    @staticmethod
    def log_security_event(
        event_type: str,
        action: str,
        user: Optional[User] = None,
        request: Optional[HttpRequest] = None,
        severity: str = SeverityLevel.WARNING,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        return AuditLogService.log(
            event_type=event_type,
            event_category=EventCategory.SECURITY,
            action=action,
            user=user,
            request=request,
            severity=severity,
            metadata=metadata,
            is_compliance_event=True,
        )

    @staticmethod
    def log_error(
        event_type: str,
        action: str,
        error: Exception,
        user: Optional[User] = None,
        request: Optional[HttpRequest] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        return AuditLogService.log(
            event_type=event_type,
            event_category=EventCategory.SYSTEM,
            action=action,
            user=user,
            request=request,
            severity=SeverityLevel.ERROR,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            metadata=metadata,
        )

    @staticmethod
    def get_user_activity(
        user: User,
        limit: int = 100,
        event_category: Optional[str] = None,
        event_type: Optional[str] = None,
    ):
        queryset = AuditLog.objects.filter(user=user)

        if event_category:
            queryset = queryset.filter(event_category=event_category)
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        return queryset[:limit]

    @staticmethod
    def get_suspicious_activities(
        limit: int = 100,
        severity: Optional[str] = None,
    ):
        queryset = AuditLog.objects.filter(
            event_type__in=[
                EventType.SUSPICIOUS_ACTIVITY,
                EventType.FAILED_LOGIN_ATTEMPTS,
                EventType.IP_BLOCKED,
            ]
        )

        if severity:
            queryset = queryset.filter(severity=severity)
        return queryset[:limit]

    @staticmethod
    def get_compliance_logs(
        start_date=None,
        end_date=None,
        event_category: Optional[str] = None,
    ):
        queryset = AuditLog.objects.filter(is_compliance_event=True)
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        if event_category:
            queryset = queryset.filter(event_category=event_category)
        return queryset
