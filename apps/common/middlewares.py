from django.http import JsonResponse

ALLOWED_CLIENT_TYPES = ["web", "mobile"]


class ClientTypeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        client_type = request.headers.get("X-Client-Type")

        if not client_type or client_type.lower() not in ALLOWED_CLIENT_TYPES:
            return JsonResponse(
                {
                    "status": "failure",
                    "message": "Invalid or missing X-Client-Type header",
                },
                status=400,
            )

        # Attach to request for downstream use
        request.client_type = client_type.lower()
        return self.get_response(request)
