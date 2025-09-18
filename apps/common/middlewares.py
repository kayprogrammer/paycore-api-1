from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

ALLOWED_CLIENT_TYPES = ["web", "mobile"]


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to all responses
    Essential for fintech applications
    """

    def process_response(self, request, response):
        # Prevent clickjacking attacks
        response["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # XSS Protection
        response["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy (basic, adjust as needed)
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'"
        )

        # Permissions Policy (formerly Feature Policy)
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=(), "
            "accelerometer=(), ambient-light-sensor=()"
        )

        # HSTS (only if HTTPS is used)
        if request.is_secure():
            response["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response


class ClientTypeMiddleware:
    """
    Middleware to detect and set client type for proper authentication handling.
    Supports both strict mode (requires X-Client-Type header) and flexible mode
    (auto-detection based on user agent)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get client type from header or detect from user agent
        client_type = request.headers.get("X-Client-Type", "").lower()
        user_agent = request.META.get("HTTP_USER_AGENT", "").lower()

        # If explicit client type provided, validate it
        if client_type:
            if client_type not in ALLOWED_CLIENT_TYPES:
                return JsonResponse(
                    {
                        "status": "failure",
                        "message": f"Invalid X-Client-Type header. Allowed: {', '.join(ALLOWED_CLIENT_TYPES)}",
                    },
                    status=400,
                )
            request.client_type = client_type
        else:
            # Auto-detect based on user agent for backward compatibility
            if any(
                browser in user_agent
                for browser in [
                    "mozilla",
                    "chrome",
                    "safari",
                    "edge",
                    "firefox",
                    "opera",
                ]
            ):
                request.client_type = "web"
            else:
                request.client_type = "mobile"

        return self.get_response(request)
