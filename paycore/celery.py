"""
Celery configuration for Paycore API
Production-grade setup with RabbitMQ for fintech applications
"""

import os
import ssl
from celery import Celery
from celery.signals import setup_logging
from django.conf import settings
from kombu import Queue, Exchange

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paycore.settings.base")

# Create Celery instance
app = Celery("paycore")

# Configure Celery using Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Task discovery - automatically find tasks in all apps
app.autodiscover_tasks()

# Production-grade Celery configuration
app.conf.update(
    # Broker settings (RabbitMQ)
    broker_url=settings.CELERY_BROKER_URL,
    broker_connection_retry_on_startup=True,
    broker_heartbeat=30,
    broker_pool_limit=10,
    # Result backend (Redis for fast results)
    result_backend=settings.CELERY_RESULT_BACKEND,
    result_expires=3600,  # 1 hour
    result_compression="gzip",
    # Task routing and queues
    task_routes={
        "apps.accounts.tasks.send_*": {"queue": "emails"},
        "apps.notifications.tasks.*": {"queue": "notifications"},
        "apps.payments.tasks.*": {"queue": "payments"},
        "apps.audit_logs.tasks.*": {"queue": "audit"},
        "apps.compliance.tasks.*": {"queue": "compliance"},
        "loans.auto_approve_loan": {"queue": "loans"},
        "loans.auto_disburse_loan": {"queue": "loans"},
        "loans.process_auto_repayments": {"queue": "loans"},
    },
    # Queue definitions with priorities
    task_default_queue="default",
    task_queues=(
        # High priority queues
        Queue(
            "emails",
            Exchange("emails"),
            routing_key="emails",
            queue_arguments={"x-max-priority": 10},
        ),
        Queue(
            "payments",
            Exchange("payments"),
            routing_key="payments",
            queue_arguments={"x-max-priority": 10},
        ),
        Queue(
            "compliance",
            Exchange("compliance"),
            routing_key="compliance",
            queue_arguments={"x-max-priority": 10},
        ),
        Queue(
            "loans",
            Exchange("loans"),
            routing_key="loans",
            queue_arguments={"x-max-priority": 10},
        ),
        # Medium priority queues
        Queue(
            "notifications",
            Exchange("notifications"),
            routing_key="notifications",
            queue_arguments={"x-max-priority": 5},
        ),
        Queue(
            "audit",
            Exchange("audit"),
            routing_key="audit",
            queue_arguments={"x-max-priority": 5},
        ),
        # Default queue
        Queue(
            "default",
            Exchange("default"),
            routing_key="default",
            queue_arguments={"x-max-priority": 1},
        ),
    ),
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Reliability and error handling
    task_acks_late=True,  # Acknowledge task only after completion
    task_reject_on_worker_lost=True,  # Reject tasks on worker failure
    task_track_started=True,  # Track when tasks start
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit
    # Retry configuration
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    # Worker configuration
    worker_prefetch_multiplier=1,  # One task at a time for fairness
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    worker_disable_rate_limits=False,
    # Monitoring and logging
    worker_send_task_events=True,
    task_send_sent_event=True,
    # Security
    task_always_eager=False,  # Never run tasks synchronously in production
    worker_hijack_root_logger=False,
)

# SSL/TLS configuration for production RabbitMQ
if getattr(settings, "CELERY_BROKER_USE_SSL", False):
    app.conf.broker_use_ssl = {
        "keyfile": getattr(settings, "CELERY_SSL_KEYFILE", ""),
        "certfile": getattr(settings, "CELERY_SSL_CERTFILE", ""),
        "ca_certs": getattr(settings, "CELERY_SSL_CA_CERTS", ""),
        "cert_reqs": ssl.CERT_REQUIRED,
    }


@setup_logging.connect
def config_loggers(*args, **kwargs):
    """Configure logging for Celery workers"""
    from logging.config import dictConfig
    from django.conf import settings

    dictConfig(settings.LOGGING)


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f"Request: {self.request!r}")
    return {"status": "success", "worker_id": self.request.id}


# Health check task
@app.task(bind=True, name="celery.ping")
def ping_task(self):
    """Health check task for monitoring"""
    return {"status": "pong", "timestamp": app.now().isoformat()}


# Celery Beat Schedule - Periodic Tasks
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Notification cleanup tasks
    "cleanup-old-notifications": {
        "task": "notifications.cleanup_old_notifications",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
    },
    "cleanup-expired-notifications": {
        "task": "notifications.cleanup_expired_notifications",
        "schedule": crontab(minute=0),  # Every hour
    },
    "generate-daily-notification-stats": {
        "task": "notifications.generate_daily_stats",
        "schedule": crontab(hour=0, minute=5),  # 00:05 daily
    },
    # Compliance tasks (from previous implementation)
    "daily-kyc-expiry-check": {
        "task": "compliance.daily_kyc_expiry_check",
        "schedule": crontab(hour=0, minute=0),  # Midnight daily
    },
    "weekly-sanctions-rescan": {
        "task": "compliance.weekly_sanctions_rescan",
        "schedule": crontab(day_of_week=1, hour=2, minute=0),  # Monday 2 AM
    },
    # Loan tasks
    "process-auto-repayments": {
        "task": "loans.process_auto_repayments",
        "schedule": crontab(hour=3, minute=0),  # 3 AM daily
    },
    "update-overdue-schedules": {
        "task": "loans.update_overdue_schedules",
        "schedule": crontab(hour=1, minute=0),  # 1 AM daily
    },
    "cleanup-old-credit-scores": {
        "task": "loans.cleanup_old_credit_scores",
        "schedule": crontab(day_of_week=0, hour=4, minute=0),  # Sunday 4 AM
    },
}
