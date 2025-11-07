# PayCore API

A robust, production-grade Fintech API built with Django Ninja, designed for payments, wallets, transactions, and compliance.

## 🚀 Live Demo

### Backend API (Fly.io)
- **Production API**: [https://paycore-api.fly.dev](https://paycore-api.fly.dev)
- **API Documentation (Swagger)**: [https://paycore-api.fly.dev/api/docs](https://paycore-api.fly.dev/api/docs)
- **Admin Panel**: [https://paycore-api.fly.dev/admin](https://paycore-api.fly.dev/admin)

### Frontend Application (Netlify)
- **Live Application**: [https://paycore-frontend.netlify.app](https://paycore-frontend.netlify.app)
- **GitHub Repository**: [PayCore Frontend](https://github.com/kayprogrammer/paycore-frontend)

### Screenshots

**Admin Panel**
![PayCore Admin Panel](static/media/admin.png)

**API Documentation (Swagger)**
![PayCore API Documentation](static/media/api.png)

## ✨ Features

### Core Functionality
- **Multi-currency Wallet System** - NGN, KES, GHS, USD support with real-time exchange rates
- **Transaction Management** - Deposits, withdrawals, transfers, bill payments with fee calculation
- **Card Issuing & Management** - Virtual and physical cards via Flutterwave and Sudo Africa
- **Loan & Investment Products** - Personal loans, fixed deposits, mutual funds with automated calculations
- **Payment Processing** - Payment links, invoices, merchant API integration

### Security & Compliance
- **Google OAuth Authentication** - Secure third-party authentication as primary login method
- **Email/OTP Authentication** - Alternative authentication with 6-digit OTP verification
- **JWT Token Management** - Access & refresh tokens with automatic rotation
- **KYC Verification** - Multi-tier verification (Tier 1-3) with Onfido integration
- **Compliance & Risk Assessment** - AML checks, sanctions screening, transaction monitoring
- **Audit Logs** - Complete activity tracking with IP logging and user agents
- **PIN Authorization** - Transaction-level security with wallet PINs

### Communications & Support
- **Notifications** - Email, SMS, push notifications via Firebase Cloud Messaging
- **Support System** - Ticketing with SLA tracking, FAQs, canned responses, escalation management
- **Real-time Updates** - WebSocket support via Django Channels

### Monitoring & Operations
- **Prometheus Metrics** - System and application-level metrics
- **Grafana Dashboards** - Pre-configured dashboards for monitoring
- **AlertManager** - Automated alerting for critical issues
- **Health Checks** - System and Celery health endpoints
- **Celery Task Queue** - Background job processing with specialized queues

## 🛠️ Technology Stack

### Backend Framework
- **Django 5.2** - High-level Python web framework
- **Django Ninja** - Fast, type-safe API framework with automatic OpenAPI documentation
- **PostgreSQL 16** - Primary database with JSONB support
- **Redis** - Caching, rate limiting, and session storage

### Task Queue & Messaging
- **Celery** - Distributed task queue for background jobs
- **RabbitMQ** - Message broker with priority queues
- **Django Celery Beat** - Periodic task scheduler
- **Flower** - Real-time Celery monitoring

### Real-time & Notifications
- **Django Channels** - WebSocket support for real-time features
- **Firebase Cloud Messaging** - Push notifications for mobile/web
- **SMTP** - Email notifications with templating

### Security & Authentication
- **Google OAuth 2.0** - Primary authentication provider
- **JWT (JSON Web Tokens)** - Stateless authentication with refresh tokens
- **Onfido** - KYC verification and identity checks
- **bcrypt** - Password hashing

### Payment & Card Providers
- **Paystack** - Payment processing for NGN
- **Flutterwave** - Virtual card issuing (USD, NGN, GBP)
- **Sudo Africa** - Virtual card issuing (USD, NGN)
- **Internal Provider** - Mock provider for development/testing

### Storage & Media
- **Cloudinary** - Cloud-based image and file storage
- **WhiteNoise** - Static file serving for production

### Monitoring & Observability
- **Prometheus** - Metrics collection and time-series database
- **Grafana** - Visualization and dashboards
- **AlertManager** - Alert routing and management
- **Django Prometheus** - Django metrics exporter

### Development & Deployment
- **Docker & Docker Compose** - Containerization and orchestration
- **Fly.io** - Production hosting platform
- **pytest** - Testing framework with coverage
- **Black & isort** - Code formatting
- **Python 3.11+** - Runtime environment

## Quick Start with Docker

The easiest way to run PayCore API is using Docker Compose, which sets up the entire stack including PostgreSQL, Redis, RabbitMQ, Celery workers, and monitoring tools.

### Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose)
- Git

### 1. Clone and Setup Environment

```bash
git clone <repository-url>
cd paycore-api-1

# Copy environment template
cp .env.example .env

# Update .env with your settings (database, Redis, RabbitMQ, API keys)
```

### 2. Build and Start Services

```bash
# Build Docker images
make docker-build

# Start all services
make docker-up

# View logs
make docker-logs
```

The API will be available at http://localhost:8000

### 3. Run Migrations and Seed Data

```bash
# Access the web container shell
make docker-exec-web

# Inside the container:
python manage.py migrate
python manage.py init  # Runs all seed commands

# Or run seed commands individually:
python manage.py upsert_countries
python manage.py seed_bill_providers
python manage.py seed_loan_products
python manage.py seed_investment_products
python manage.py seed_faqs
python manage.py seed_users  # Creates test users with KYC & wallets

# Create superuser (optional)
python manage.py createsuperuser

# Exit container
exit
```

## Docker Services

The Docker setup includes 10 services:

| Service                   | Port        | Description                               |
| ------------------------- | ----------- | ----------------------------------------- |
| **web**             | 8000        | Django API (uvicorn with 4 workers)       |
| **db**              | 5432        | PostgreSQL 16 database                    |
| **redis**           | 6379        | Redis cache and session store             |
| **rabbitmq**        | 5672, 15672 | RabbitMQ message broker + management UI   |
| **celery-general**  | -           | General background tasks worker           |
| **celery-emails**   | -           | Email queue worker (4 concurrency)        |
| **celery-payments** | -           | Payment processing worker (2 concurrency) |
| **celery-beat**     | -           | Periodic task scheduler                   |
| **flower**          | 5555        | Celery monitoring dashboard               |

### Access Dashboards

- **API Documentation**: http://localhost:8000
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Flower Monitoring**: http://localhost:5555

### Test Credentials

After running `make init` or `make su`, you can use these test accounts:

| Email             | Password    | PIN  | Type         | KYC Status      | Wallet        |
| ----------------- | ----------- | ---- | ------------ | --------------- | ------------- |
| test@example.com  | password123 | 1234 | Regular User | Tier 2 Verified | ₦100,000 NGN |
| test2@example.com | password123 | 1234 | Staff User   | Tier 2 Verified | ₦100,000 NGN |

Both accounts have:

- Verified email
- Approved KYC (Tier 2)
- Active NGN wallet with ₦100,000 balance
- Default wallet PIN: 1234

## Docker Commands

All commands are available via the Makefile:

```bash
# Build and Run
make docker-build          # Build images from scratch
make docker-up             # Start all services
make docker-down           # Stop all services
make docker-down-v         # Stop and remove volumes
make docker-restart        # Restart all services
make docker-rebuild        # Full rebuild (down -v, build, up)

# Logs
make docker-logs           # View all logs
make docker-logs-web       # View Django logs only
make docker-logs-celery    # View Celery worker logs

# Shell Access
make docker-exec-web       # Access web container shell
make docker-exec-db        # Access PostgreSQL shell

# Status
make docker-ps             # View running containers

# Quick start with everything
make build                 # Build and start (quick rebuild)
```

## Local Development (Without Docker)

If you prefer to run services locally:

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
make req
```

### 2. Start Infrastructure

You can use Docker for infrastructure only:

```bash
make infrastructure-up     # Starts RabbitMQ + Redis in Docker
```

Or install PostgreSQL, Redis, and RabbitMQ locally.

### 3. Setup Database

```bash
# Run migrations
make mig

# Seed data
make init
```

### 4. Start Services

You'll need multiple terminal windows:

```bash
# Terminal 1: Django API
make run

# Terminal 2: Celery worker (general tasks)
make celery

# Terminal 3: Celery worker (email queue)
make celery-emails

# Terminal 4: Celery worker (payment queue)
make celery-payments

# Terminal 5: Celery Beat (scheduler)
make celery-beat

# Terminal 6: Flower (monitoring)
make flower
```

## Environment Variables

Key environment variables in `.env`:

```bash
# Database
DB_NAME=paycore
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db  # Use 'localhost' for local development
DB_PORT=5432

# Redis
REDIS_HOST=redis  # Use 'localhost' for local development
REDIS_PORT=6379

# RabbitMQ
RABBITMQ_HOST=rabbitmq  # Use 'localhost' for local development
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
SITE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# CORS (for frontend)
CORS_ALLOWED_ORIGINS=http://localhost:3000 http://127.0.0.1:3000

# Authentication
GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret

# JWT Token Settings
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_MINUTES=10080
TRUST_TOKEN_EXPIRE_DAYS=30

# Payment Providers
USE_INTERNAL_PROVIDER=False  # Set to True for development without external APIs
PAYMENT_PROVIDERS_TEST_MODE=True
PAYSTACK_TEST_SECRET_KEY=sk_test_xxx
PAYSTACK_TEST_PUBLIC_KEY=pk_test_xxx
FLUTTERWAVE_TEST_SECRET_KEY=FLWSECK_TEST-xxx
SUDO_TEST_SECRET_KEY=your-sudo-test-key

# Card Providers
CARD_PROVIDERS_TEST_MODE=True

# KYC Provider
KYC_PROVIDER=onfido
ONFIDO_API_KEY=your-onfido-api-key
ONFIDO_WEBHOOK_TOKEN=your-onfido-webhook-token

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_SSL=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@paycore.com

# Firebase Cloud Messaging (for push notifications)
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}  # Production
# OR
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json  # Development

# Notifications
NOTIFICATION_RETENTION_DAYS=90
```

## Production Deployment

For production with full monitoring stack:

```bash
# Start production services
make prod-up

# Start monitoring (Prometheus, Grafana, AlertManager)
make monitoring-up

# View all dashboards
make show-dashboards
```

Production services include:

- **Grafana**: http://localhost:3000 (admin/paycore123)
- **Prometheus**: http://localhost:9090
- **AlertManager**: http://localhost:9093
- **Node Exporter**: Metrics for host system
- **Redis Exporter**: Metrics for Redis

## 🔐 Authentication

PayCore API supports multiple authentication methods:

### 1. Google OAuth (Primary Method)
```bash
POST /api/v1/auth/google-oauth
Content-Type: application/json

{
  "token": "google-id-token-from-frontend"
}

Response:
{
  "status": "success",
  "message": "Login successful",
  "data": {
    "user": { ... },
    "access": "jwt-access-token",
    "refresh": "jwt-refresh-token"
  }
}
```

### 2. Email/OTP Authentication
```bash
# Step 1: Request OTP
POST /api/v1/auth/request-otp
{
  "email": "user@example.com"
}

# Step 2: Verify OTP
POST /api/v1/auth/verify-otp
{
  "email": "user@example.com",
  "otp": "123456"
}
```

### 3. Token Refresh
```bash
POST /api/v1/auth/refresh
{
  "refresh": "jwt-refresh-token"
}
```

### Authentication Headers
All authenticated requests require the JWT token in the Authorization header:
```bash
Authorization: Bearer <access-token>
```

## 📚 API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/api/docs (Interactive API documentation)
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json (Machine-readable API spec)
- **Admin Panel**: http://localhost:8000/admin (Django admin interface)

### API Endpoints Overview

| Category | Endpoints | Description |
|----------|-----------|-------------|
| **Authentication** | `/api/v1/auth/*` | Login, register, OTP, OAuth, token refresh |
| **Profiles** | `/api/v1/profiles/*` | User profiles, avatar upload, device management |
| **Wallets** | `/api/v1/wallets/*` | Multi-currency wallets, balance, currency exchange |
| **Cards** | `/api/v1/cards/*` | Virtual/physical cards, transactions, controls |
| **Transactions** | `/api/v1/transactions/*` | Deposits, withdrawals, transfers, history |
| **Bills** | `/api/v1/bills/*` | Bill providers, packages, payments, beneficiaries |
| **Payments** | `/api/v1/payments/*` | Payment links, invoices, merchant API |
| **Loans** | `/api/v1/loans/*` | Loan products, applications, repayments |
| **Investments** | `/api/v1/investments/*` | Investment products, portfolios, returns |
| **Support** | `/api/v1/support/*` | Tickets, messages, FAQs |
| **Notifications** | `/api/v1/notifications/*` | Push, email, SMS notifications |
| **Compliance** | `/api/v1/compliance/*` | KYC verification, document upload |

## Testing

```bash
# Run all tests
make test

# Run with coverage
pytest --cov=apps --cov-report=html

# Test specific module
pytest apps/accounts/tests/
```

## Common Tasks

```bash
# Create migrations
make mmig                  # All apps
make mmig app='accounts'   # Specific app

# Run migrations
make mig                   # All apps
make mig app='accounts'    # Specific app

# Django shell
make shell

# Create superuser
make suser

# Seed commands
make init                  # Run all seed commands
make su                    # Seed test users (with KYC & wallets)
make upc                   # Seed countries
make sbp                   # Seed bill providers
make slp                   # Seed loan products
make sip                   # Seed investment products
make sf                    # Seed FAQs

# Update requirements
make ureq
```

## Project Structure

```
paycore-api-1/
├── apps/
│   ├── accounts/          # User management, KYC
│   ├── bills/             # Bill payments
│   ├── cards/             # Card issuing & management
│   ├── common/            # Shared utilities, monitoring
│   ├── compliance/        # Audit logs, risk assessment
│   ├── investments/       # Investment products
│   ├── loans/             # Loan products & repayments
│   ├── notifications/     # Email, SMS, push notifications
│   ├── support/           # Tickets, FAQs, chat
│   ├── transactions/      # Deposits, withdrawals, transfers
│   └── wallets/           # Multi-currency wallets
├── paycore/
│   ├── settings.py        # Django settings
│   ├── urls.py            # URL routing
│   └── asgi.py            # ASGI application
├── Dockerfile             # Multi-stage Docker build
├── docker-compose.yml     # Development stack
├── Makefile               # Command shortcuts
└── requirements.txt       # Python dependencies
```

## Monitoring & Health Checks

```bash
# Check system health
make health

# Check Celery health
make health-celery

# View Celery stats
make inspect-stats

# View active tasks
make inspect-active
```

Health endpoints:

- System: http://localhost:8000/health/system/
- Celery: http://localhost:8000/health/celery/
- Metrics: http://localhost:8000/metrics/

## Troubleshooting

### Docker Issues

```bash
# View logs for specific service
docker-compose logs -f web

# Restart a specific service
docker-compose restart web

# Rebuild a specific service
docker-compose up -d --build web

# Clear everything and start fresh
make docker-down-v
make docker-build
make docker-up
```

### Database Issues

```bash
# Access PostgreSQL shell
make docker-exec-db

# Inside PostgreSQL:
\dt                        # List tables
\d notifications_notification  # Describe table
SELECT COUNT(*) FROM notifications_notification;
```

### Celery Issues

```bash
# View Celery logs
make docker-logs-celery

# Purge all queued tasks
make purge-tasks

# Check worker stats
make inspect-stats

# Access Flower UI
open http://localhost:5555
```
