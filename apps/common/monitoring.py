"""
Celery monitoring and metrics collection
Production-grade monitoring for fintech applications
"""

import logging
import time
from datetime import datetime, UTC
from celery.signals import (
    task_prerun,
    task_postrun,
    task_failure,
    task_retry,
    worker_ready,
    worker_shutdown,
)
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from django.conf import settings

logger = logging.getLogger(__name__)

# Prometheus metrics registry
REGISTRY = CollectorRegistry()

# Task metrics
TASK_COUNTER = Counter(
    "celery_tasks_total",
    "Total number of Celery tasks",
    ["task_name", "status", "queue"],
    registry=REGISTRY,
)

TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Task execution duration in seconds",
    ["task_name", "queue"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    registry=REGISTRY,
)

TASK_RETRY_COUNTER = Counter(
    "celery_task_retries_total",
    "Total number of task retries",
    ["task_name", "queue"],
    registry=REGISTRY,
)

ACTIVE_TASKS = Gauge(
    "celery_active_tasks",
    "Number of currently active tasks",
    ["queue"],
    registry=REGISTRY,
)

WORKER_STATUS = Gauge(
    "celery_workers_active",
    "Number of active Celery workers",
    ["worker_name"],
    registry=REGISTRY,
)

# Task execution tracking
task_start_times = {}


@task_prerun.connect
def task_prerun_handler(
    sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds
):
    """Handle task pre-execution for monitoring"""
    task_name = task.name if task else "unknown"
    queue_name = getattr(task, "queue", "default") if task else "default"

    # Record start time
    task_start_times[task_id] = time.time()

    # Update active tasks gauge
    ACTIVE_TASKS.labels(queue=queue_name).inc()

    # Log task start for audit trail
    logger.info(
        f"Task {task_name} started",
        extra={
            "task_id": task_id,
            "task_name": task_name,
            "queue": queue_name,
            "task_args": str(args)[:200] if args else None,
            "task_kwargs": str(kwargs)[:200] if kwargs else None,
            "status": "started",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@task_postrun.connect
def task_postrun_handler(
    sender=None,
    task_id=None,
    task=None,
    args=None,
    kwargs=None,
    retval=None,
    state=None,
    **kwds,
):
    """Handle task post-execution for monitoring"""
    task_name = task.name if task else "unknown"
    queue_name = getattr(task, "queue", "default") if task else "default"

    # Calculate duration
    start_time = task_start_times.pop(task_id, time.time())
    duration = time.time() - start_time

    # Update metrics
    TASK_COUNTER.labels(task_name=task_name, status="success", queue=queue_name).inc()
    TASK_DURATION.labels(task_name=task_name, queue=queue_name).observe(duration)
    ACTIVE_TASKS.labels(queue=queue_name).dec()

    # Log task completion
    logger.info(
        f"Task {task_name} completed successfully",
        extra={
            "task_id": task_id,
            "task_name": task_name,
            "queue": queue_name,
            "duration": duration,
            "state": state,
            "status": "completed",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@task_failure.connect
def task_failure_handler(
    sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds
):
    """Handle task failures for monitoring and alerting"""
    task_name = sender.name if sender else "unknown"
    queue_name = getattr(sender, "queue", "default") if sender else "default"

    # Calculate duration if start time exists
    start_time = task_start_times.pop(task_id, None)
    duration = time.time() - start_time if start_time else 0

    # Update metrics
    TASK_COUNTER.labels(task_name=task_name, status="failure", queue=queue_name).inc()
    if duration > 0:
        TASK_DURATION.labels(task_name=task_name, queue=queue_name).observe(duration)
    ACTIVE_TASKS.labels(queue=queue_name).dec()

    # Log failure with full context
    logger.error(
        f"Task {task_name} failed: {str(exception)}",
        extra={
            "task_id": task_id,
            "task_name": task_name,
            "queue": queue_name,
            "duration": duration,
            "exception": str(exception),
            "status": "failed",
            "timestamp": datetime.now(UTC).isoformat(),
        },
        exc_info=einfo,
    )

    # Alert on critical failures (emails, payments)
    if queue_name in ["emails", "payments", "compliance"]:
        alert_critical_task_failure(task_name, task_id, str(exception), queue_name)


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwds):
    """Handle task retries for monitoring"""
    task_name = sender.name if sender else "unknown"
    queue_name = getattr(sender, "queue", "default") if sender else "default"

    # Update retry counter
    TASK_RETRY_COUNTER.labels(task_name=task_name, queue=queue_name).inc()

    # Log retry attempt
    logger.warning(
        f"Task {task_name} retrying: {str(reason)}",
        extra={
            "task_id": task_id,
            "task_name": task_name,
            "queue": queue_name,
            "reason": str(reason),
            "status": "retry",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@worker_ready.connect
def worker_ready_handler(sender=None, **kwds):
    """Handle worker startup"""
    worker_name = sender.hostname if sender else "unknown"

    # Update worker status
    WORKER_STATUS.labels(worker_name=worker_name).set(1)

    logger.info(
        f"Celery worker {worker_name} ready",
        extra={
            "worker_name": worker_name,
            "status": "ready",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwds):
    """Handle worker shutdown"""
    worker_name = sender.hostname if sender else "unknown"

    # Update worker status
    WORKER_STATUS.labels(worker_name=worker_name).set(0)

    logger.info(
        f"Celery worker {worker_name} shutting down",
        extra={
            "worker_name": worker_name,
            "status": "shutdown",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


def alert_critical_task_failure(task_name, task_id, error_message, queue_name):
    """
    Send alerts for critical task failures
    Integrate with your alerting system (Slack, PagerDuty, etc.)
    """
    alert_message = {
        "severity": "critical",
        "service": "paycore-celery",
        "task_name": task_name,
        "task_id": task_id,
        "queue": queue_name,
        "error": error_message,
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": getattr(settings, "ENVIRONMENT", "unknown"),
    }

    # Log critical alert
    logger.critical(
        f"CRITICAL: Task failure in {queue_name} queue", extra=alert_message
    )

    # TODO: Integrate with your alerting system
    # Examples:
    # - Send to Slack webhook
    # - Send to PagerDuty
    # - Send email to on-call team
    # - Push to monitoring dashboard


def get_task_metrics():
    """Get current task metrics for health checks"""
    try:
        from celery import current_app

        # Get active tasks count
        inspect = current_app.control.inspect()
        active_tasks = inspect.active()

        if active_tasks:
            total_active = sum(len(tasks) for tasks in active_tasks.values())
        else:
            total_active = 0

        # Get worker status
        stats = inspect.stats()
        worker_count = len(stats) if stats else 0

        return {
            "active_tasks": total_active,
            "active_workers": worker_count,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get task metrics: {str(e)}")
        return {"error": str(e), "timestamp": datetime.now(UTC).isoformat()}
