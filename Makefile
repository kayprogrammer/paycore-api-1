ifneq (,$(wildcard ./.env))
include .env
export 
ENV_FILE_PARAM = --env-file .env

endif

# ============ DOCKER COMMANDS ============
docker-build:
	docker-compose build --no-cache

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-down-v:
	docker-compose down -v

docker-restart:
	docker-compose restart

docker-logs:
	docker-compose logs -f

docker-logs-web:
	docker-compose logs -f web

docker-logs-celery:
	docker-compose logs -f celery-general celery-emails celery-payments

docker-ps:
	docker-compose ps

docker-exec-web:
	docker-compose exec web /bin/sh

docker-exec-db:
	docker-compose exec db psql -U ${DB_USER:-postgres} -d ${DB_NAME:-paycore}

# Full rebuild (clean start)
docker-rebuild:
	docker-compose down -v
	docker-compose build --no-cache
	docker-compose up -d
	docker-compose logs -f

# Quick start (build and run)
build:
	docker-compose up --build -d --remove-orphans

up:
	docker-compose up -d

down:
	docker-compose down

show-logs:
	docker-compose logs -f

run:
	uvicorn paycore.asgi:application --host 0.0.0.0 --port 8000 --reload --ws wsproto

mmig: # run with "make mmig" or "make mmig app='app'"
	if [ -z "$(app)" ]; then \
		python manage.py makemigrations; \
	else \
		python manage.py makemigrations "$(app)"; \
	fi

mig: # run with "make mig" or "make mig app='app'"
	if [ -z "$(app)" ]; then \
		python manage.py migrate; \
	else \
		python manage.py migrate "$(app)"; \
	fi

init:
	python manage.py upsert_countries && python manage.py seed_currencies && python manage.py seed_bill_providers && python manage.py seed_loan_products && python manage.py seed_investment_products && python manage.py seed_faqs && python manage.py seed_users

upc:
	python manage.py upsert_countries

sc:
	python manage.py seed_currencies

sbp:
	python manage.py seed_bill_providers

slp:
	python manage.py seed_loan_products

sip:
	python manage.py seed_investment_products

sf:
	python manage.py seed_faqs

su:
	python manage.py seed_users

test:
	pytest --disable-warnings -vv -x

shell:
	python manage.py shell

suser:
	python manage.py createsuperuser

cpass:
	python manage.py changepassword
	
req: # Install requirements
	pip install -r requirements.txt

ureq: # Update requirements
	pip freeze > requirements.txt

# Celery Management Commands
celery: # Start Celery worker
	celery -A paycore worker --loglevel=info --concurrency=4

celery-emails: # Start email queue worker
	celery -A paycore worker -Q emails --loglevel=info --concurrency=4

celery-payments: # Start payments queue worker  
	celery -A paycore worker -Q payments --loglevel=info --concurrency=2

celery-beat: # Start Celery Beat scheduler
	celery -A paycore beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

flower: # Start Flower monitoring
	celery -A paycore flower --port=5555

flower-secure: # Start Flower with authentication
	python manage.py start_flower --basic-auth=admin:paycore123

# Health Checks
health: # Check system health
	@echo "Checking system health..."
	@curl -s http://localhost:8000/health/system/ | python -m json.tool || echo "Web service not available"

health-celery: # Check Celery health
	@curl -s http://localhost:8000/health/celery/ | python -m json.tool || echo "Celery not available"

# Production Docker Commands
prod-up: # Start production environment
	docker-compose -f docker-compose.production.yml up -d --build

prod-down: # Stop production environment
	docker-compose -f docker-compose.production.yml down

prod-logs: # View production logs
	docker-compose -f docker-compose.production.yml logs -f

celery-logs: # View Celery logs
	docker-compose logs -f celery-emails celery-payments celery-general

# Task Management
purge-tasks: # Purge all queued tasks
	celery -A paycore purge -f

inspect-active: # Inspect active tasks
	celery -A paycore inspect active

inspect-stats: # Get worker statistics
	celery -A paycore inspect stats

# Infrastructure Commands
infrastructure-up: # Start RabbitMQ + Redis only
	docker run -d --name paycore-rabbitmq -p 5672:5672 -p 15672:15672 -e RABBITMQ_DEFAULT_USER=guest -e RABBITMQ_DEFAULT_PASS=guest rabbitmq:3-management || echo "RabbitMQ already running"
	docker run -d --name paycore-redis -p 6379:6379 redis:7-alpine || echo "Redis already running"

infrastructure-down: # Stop infrastructure
	docker stop paycore-rabbitmq paycore-redis || echo "Containers not found"
	docker rm paycore-rabbitmq paycore-redis || echo "Containers not found"

# Setup Commands

setup-celery: # Run Celery migrations
	python manage.py migrate django_celery_beat
	python manage.py migrate django_celery_results

# Testing Commands  
test-metrics: # Test metrics endpoint
	@echo "Testing Prometheus metrics..."
	curl -s http://localhost:8000/metrics/ | head -10 || echo "Django not running"

test-health: # Test health endpoints
	@echo "Testing system health..."
	curl -s http://localhost:8000/health/system/ | python -m json.tool || echo "Django not running"
	@echo ""
	@echo "Testing Celery health..."
	curl -s http://localhost:8000/health/celery/ | python -m json.tool || echo "Django not running"

test-email-task: # Test email task queueing
	python manage.py shell -c "from apps.accounts.tasks import EmailTasks; task = EmailTasks.send_otp_email.delay(1, 'test'); print(f'Task queued: {task.id}')"

# Start Services Commands
start-celery-workers: # Start all Celery workers (use separate terminals)
	@echo "Start each command in separate terminals:"
	@echo "Terminal 1: make celery-emails"  
	@echo "Terminal 2: make celery"
	@echo "Terminal 3: make celery-beat"

# Monitoring Commands
monitoring-up: # Start full monitoring stack
	@echo "Starting monitoring stack (this may take a while on first run)..."
	docker-compose -f docker-compose.production.yml pull prometheus grafana alertmanager node-exporter redis-exporter || echo "Pull failed, trying to start anyway..."
	docker-compose -f docker-compose.production.yml up -d prometheus grafana alertmanager node-exporter redis-exporter

monitoring-up-local: # Start monitoring with locally available images only
	docker-compose -f docker-compose.production.yml up -d --no-deps prometheus grafana alertmanager node-exporter redis-exporter

monitoring-only: # Start monitoring without Redis (use when Redis is already running locally)
	docker-compose -f docker-compose.production.yml up -d prometheus grafana alertmanager node-exporter redis-exporter

monitoring-down: # Stop monitoring stack
	docker-compose -f docker-compose.production.yml stop prometheus grafana alertmanager node-exporter redis-exporter

monitoring-check: # Check monitoring configuration files
	@echo "Checking monitoring configuration..."
	@ls -la monitoring/ 2>/dev/null || echo "❌ monitoring/ directory missing"
	@ls -la monitoring/prometheus.yml 2>/dev/null || echo "❌ prometheus.yml missing"
	@ls -la monitoring/alert_rules.yml 2>/dev/null || echo "❌ alert_rules.yml missing"
	@ls -la monitoring/alertmanager.yml 2>/dev/null || echo "❌ alertmanager.yml missing"

show-dashboards: # Show monitoring URLs
	@echo "📊 Monitoring Dashboards:"
	@echo "  Grafana:      http://localhost:3000 (admin/paycore123)"
	@echo "  Prometheus:   http://localhost:9090"
	@echo "  AlertManager: http://localhost:9093"
	@echo "  Flower:       http://localhost:5555 (admin/paycore123)" 
	@echo "  RabbitMQ:     http://localhost:15672 (guest/guest)"

# Quick Start for Development with Monitoring
quick-start: req mig build monitoring-up
	@echo "🚀 Paycore API with Full Monitoring Stack!"
	@echo ""
	@echo "📊 Services:"
	@echo "  Web API:      http://localhost:8000"
	@echo "  Flower:       http://localhost:5555" 
	@echo "  RabbitMQ:     http://localhost:15672"
	@echo "  Grafana:      http://localhost:3000"
	@echo "  Prometheus:   http://localhost:9090"
	@echo "  AlertManager: http://localhost:9093"
	@echo ""
	@echo "🔧 Credentials:"
	@echo "  RabbitMQ:     guest / guest"
	@echo "  Flower:       admin / paycore123"
	@echo "  Grafana:      admin / paycore123"

seed-bill:
	python manage.py seed_bill_providers