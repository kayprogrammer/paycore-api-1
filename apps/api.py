from ninja import NinjaAPI, Schema
from ninja.responses import Response
from ninja.errors import ValidationError, AuthenticationError
from ninja.throttling import AnonRateThrottle, AuthRateThrottle
from apps.accounts.auth import AuthKycUser, AuthUser
from apps.common.exceptions import (
    ErrorCode,
    RequestError,
    request_errors,
    validation_errors,
)

from apps.accounts.views import auth_router
from apps.profiles.views import profiles_router
from apps.wallets.views import wallet_router
from apps.cards.views import card_router
from apps.cards.webhooks import webhook_router
from apps.bills.views import bill_router
from apps.transactions.views import transaction_router
from apps.payments.views import payment_router
from apps.loans.views import loan_router
from apps.investments.views import investment_router
from apps.support.views import support_router
from apps.compliance.views import compliance_router
from apps.notifications.views import notification_router
from apps.audit_logs.views import audit_router
from apps.common.health_checks import celery_health_check, system_health_check
from django.urls import path

api = NinjaAPI(
    title="PayCore API",
    description="""
# PayCore API - Production-Grade Fintech Platform

A comprehensive Fintech API built with Django Ninja for payments, wallets, cards, loans, investments, and compliance.

## 🚀 Key Features

- **Multi-Currency Wallets** - NGN, KES, GHS, USD with real-time exchange rates
- **Card Issuing** - Virtual/physical cards via Flutterwave and Sudo Africa
- **Loans & Investments** - Personal loans, fixed deposits, mutual funds
- **Payment Processing** - Payment links, invoices, merchant API
- **KYC & Compliance** - Multi-tier verification, AML checks, transaction monitoring
- **Notifications** - Email, SMS, push notifications via Firebase FCM

## 🔐 Authentication

1. **Google OAuth** (Primary) - Secure social login
2. **Email/OTP** - 6-digit OTP verification
3. **JWT Tokens** - Access and refresh token rotation

**Rate Limiting:** 5,000 req/min (anonymous) | 10,000 req/min (authenticated)

## 🛠️ Tech Stack

Django 5.2 + Django Ninja | PostgreSQL 16 | Redis | Celery + RabbitMQ | Prometheus + Grafana | Cloudinary | Django Channels

## 📚 Endpoints

`/api/v1/auth` • `/api/v1/profiles` • `/api/v1/wallets` • `/api/v1/cards` • `/api/v1/transactions` • `/api/v1/bills` • `/api/v1/payments` • `/api/v1/loans` • `/api/v1/investments` • `/api/v1/support` • `/api/v1/compliance` • `/api/v1/notifications` • `/api/v1/audit-logs`

## 🔗 Resources

- **Production API**: [https://paycore-api.fly.dev](https://paycore-api.fly.dev)
- **Admin Panel**: [https://paycore-api.fly.dev/admin](https://paycore-api.fly.dev/admin)
- **Frontend App**: [https://paycore-fe.netlify.app](https://paycore-fe.netlify.app)
- **GitHub Repository**: [https://github.com/kayprogrammer/paycore-api-1](https://github.com/kayprogrammer/paycore-api-1)

**Built by**: [Kenechi Ifeanyi](https://github.com/kayprogrammer)

**Note**: Most financial operations require KYC verification.
    """,
    version="1.0.0",
    docs_url="/",
    throttle=[
        # Anonymous users: 5000 requests per minute
        AnonRateThrottle("10000/m"),
        # Authenticated users: 10000 requests per minute
        AuthRateThrottle("20000/m"),
    ],
)

# Routes Registration
api.add_router("/api/v1/auth", auth_router)
api.add_router("/api/v1/profiles", profiles_router, auth=AuthUser())
api.add_router("/api/v1/wallets", wallet_router, auth=AuthKycUser())
api.add_router("/api/v1/cards", card_router, auth=AuthKycUser())
api.add_router("/api/v1/cards", webhook_router)
api.add_router("/api/v1/bills", bill_router, auth=AuthKycUser())
api.add_router("/api/v1/transactions", transaction_router, auth=AuthKycUser())
api.add_router("/api/v1/payments", payment_router)  # Mixed auth (some public endpoints)
api.add_router("/api/v1/loans", loan_router, auth=AuthKycUser())
api.add_router("/api/v1/support", support_router, auth=AuthUser())
api.add_router("/api/v1/investments", investment_router, auth=AuthKycUser())
api.add_router(
    "/api/v1/compliance", compliance_router
)  # Mixed auth (user and admin endpoints)
api.add_router("/api/v1/notifications", notification_router, auth=AuthUser())
api.add_router("/api/v1/audit-logs", audit_router, auth=AuthUser())


class HealthCheckResponse(Schema):
    message: str


@api.get("/api/v1/healthcheck/", response=HealthCheckResponse, tags=["HealthCheck (1)"])
async def healthcheck(request):
    return {"message": "pong"}


# Add health check endpoints outside of NinjaAPI for direct access
health_urls = [
    path("health/celery/", celery_health_check, name="celery-health"),
    path("health/system/", system_health_check, name="system-health"),
]


@api.exception_handler(RequestError)
def request_exc_handler(request, exc):
    return request_errors(exc)


@api.exception_handler(ValidationError)
def validation_exc_handler(request, exc):
    return validation_errors(exc)


@api.exception_handler(AuthenticationError)
def request_exc_handler(request, exc):
    return Response(
        {
            "status": "failure",
            "code": ErrorCode.INVALID_AUTH,
            "message": "Unauthorized User",
        },
        status=401,
    )
