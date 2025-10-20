from django.utils.deprecation import MiddlewareMixin
from apps.audit_logs.services import AuditLogService
from apps.audit_logs.models import EventType, EventCategory, SeverityLevel
import json, time, logging


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log API requests for audit trail
    Only logs specific endpoints (authentication, transactions, etc.)
    """

    # Endpoints that should be logged (patterns)
    LOGGED_ENDPOINTS = [
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/logout",
        "/api/auth/password",
        "/api/transactions",
        "/api/payments",
        "/api/loans",
        "/api/investments",
        "/api/compliance",
        "/api/admin",
    ]

    # Endpoints to skip logging (health checks, static files, etc.)
    SKIP_ENDPOINTS = [
        "/health",
        "/static",
        "/media",
        "/admin/jsi18n",
    ]

    def process_request(self, request):
        """Store request start time"""
        request._audit_start_time = time.time()
        return None

    def process_response(self, request, response):
        """Log the request after response is generated"""
        # Skip if endpoint should not be logged
        if not self._should_log(request.path):
            return response

        # Skip if this is a preflight request
        if request.method == "OPTIONS":
            return response

        try:
            # Extract user if authenticated
            user = None
            if hasattr(request, "user") and request.user.is_authenticated:
                user = request.user
            elif hasattr(request, "auth") and request.auth:
                user = request.auth

            # Get request data
            request_data = self._get_request_data(request)

            # Determine event type and category
            event_type, event_category = self._determine_event_type(request, response)

            # Determine severity based on response status
            severity = self._determine_severity(response.status_code)

            # Log the request
            AuditLogService.log(
                event_type=event_type,
                event_category=event_category,
                action=f"{request.method} {request.path}",
                user=user,
                request=request,
                severity=severity,
                request_data=request_data,
                response_status=response.status_code,
            )

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log request: {str(e)}")

        return response

    def _should_log(self, path: str) -> bool:
        """Check if this path should be logged"""
        # Skip certain endpoints
        if any(skip in path for skip in self.SKIP_ENDPOINTS):
            return False

        # Log specific endpoints
        return any(endpoint in path for endpoint in self.LOGGED_ENDPOINTS)

    def _get_request_data(self, request):
        """Extract request data safely"""
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                if request.content_type == "application/json":
                    return json.loads(request.body) if request.body else {}
                elif hasattr(request, "POST"):
                    return dict(request.POST)
            elif request.method == "GET":
                return dict(request.GET)
        except Exception:
            pass
        return None

    def _determine_event_type(self, request, response):
        """Determine event type and category based on request path and status"""
        path = request.path.lower()
        method = request.method
        status_code = response.status_code

        # Authentication events
        if "/login" in path:
            if status_code == 200:
                return EventType.LOGIN_SUCCESS, EventCategory.AUTHENTICATION
            else:
                return EventType.LOGIN_FAILED, EventCategory.AUTHENTICATION
        elif "/logout" in path:
            return EventType.LOGOUT, EventCategory.AUTHENTICATION
        elif "/register" in path:
            return EventType.ACCOUNT_CREATED, EventCategory.ACCOUNT
        elif "/password" in path:
            if "reset" in path:
                return EventType.PASSWORD_RESET, EventCategory.AUTHENTICATION
            else:
                return EventType.PASSWORD_CHANGE, EventCategory.AUTHENTICATION

        # Transaction events
        elif "/transactions" in path:
            if method == "POST":
                return EventType.TRANSACTION_CREATED, EventCategory.TRANSACTION
            elif method in ["GET"]:
                return EventType.DATA_VIEWED, EventCategory.DATA_ACCESS
            elif method in ["PUT", "PATCH"]:
                return EventType.TRANSACTION_COMPLETED, EventCategory.TRANSACTION

        # Payment events
        elif "/payments" in path:
            if method == "POST":
                return EventType.PAYMENT_INITIATED, EventCategory.PAYMENT
            elif status_code == 200:
                return EventType.PAYMENT_COMPLETED, EventCategory.PAYMENT
            else:
                return EventType.PAYMENT_FAILED, EventCategory.PAYMENT

        # Loan events
        elif "/loans" in path:
            if method == "POST":
                return EventType.LOAN_APPLIED, EventCategory.LOAN
            elif method in ["PUT", "PATCH"]:
                return EventType.LOAN_APPROVED, EventCategory.LOAN

        # Investment events
        elif "/investments" in path:
            if method == "POST":
                return EventType.INVESTMENT_CREATED, EventCategory.INVESTMENT
            elif method in ["PUT", "PATCH"]:
                return EventType.INVESTMENT_UPDATED, EventCategory.INVESTMENT

        # Compliance events
        elif "/compliance" in path or "/kyc" in path:
            if method == "POST":
                return EventType.KYC_SUBMITTED, EventCategory.COMPLIANCE
            elif method in ["PUT", "PATCH"]:
                return EventType.KYC_APPROVED, EventCategory.COMPLIANCE

        # Admin events
        elif "/admin" in path:
            return EventType.ADMIN_ACTION, EventCategory.ADMIN

        # Default to API call
        return EventType.API_CALL, EventCategory.SYSTEM

    def _determine_severity(self, status_code: int) -> str:
        """Determine severity based on HTTP status code"""
        if status_code >= 500:
            return SeverityLevel.CRITICAL
        elif status_code >= 400:
            return SeverityLevel.WARNING
        else:
            return SeverityLevel.INFO
