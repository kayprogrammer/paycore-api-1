# PayCore API

A robust, production-grade Fintech API built with Django Ninja, designed for payments, wallets, transactions, and compliance.

## Features

- **Multi-currency Wallet System** - NGN, KES, GHS, USD support
- **Transaction Management** - Deposits, withdrawals, transfers, bill payments
- **Card Issuing & Management** - Virtual and physical cards
- **Loan & Investment Products** - Personal loans, fixed deposits, mutual funds
- **Compliance & KYC** - Document verification, risk assessment, audit trails
- **Notifications** - Email, SMS, push notifications via Celery
- **Support System** - Ticketing, FAQs, real-time chat
- **Monitoring** - Prometheus metrics, Grafana dashboards, AlertManager

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

# Create superuser
python manage.py createsuperuser

# Exit container
exit
```

## Docker Services

The Docker setup includes 10 services:

| Service | Port | Description |
|---------|------|-------------|
| **web** | 8000 | Django API (uvicorn with 4 workers) |
| **db** | 5432 | PostgreSQL 16 database |
| **redis** | 6379 | Redis cache and session store |
| **rabbitmq** | 5672, 15672 | RabbitMQ message broker + management UI |
| **celery-general** | - | General background tasks worker |
| **celery-emails** | - | Email queue worker (4 concurrency) |
| **celery-payments** | - | Payment processing worker (2 concurrency) |
| **celery-beat** | - | Periodic task scheduler |
| **flower** | 5555 | Celery monitoring dashboard |

### Access Dashboards

- **API Documentation**: http://localhost:8000/api/docs
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Flower Monitoring**: http://localhost:5555

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

# Payment Providers
PAYSTACK_SECRET_KEY=sk_test_xxx
PAYSTACK_PUBLIC_KEY=pk_test_xxx
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-xxx

# Email (if using real SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
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

## API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/api/docs
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json

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

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary and confidential.
