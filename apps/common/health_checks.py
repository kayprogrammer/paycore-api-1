"""
Health check endpoints for Celery and system monitoring
"""

import logging
from datetime import datetime, UTC
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from apps.common.monitoring import get_task_metrics

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
@csrf_exempt
def celery_health_check(request):
    """
    Health check endpoint for Celery workers and queues
    Returns 200 if healthy, 503 if unhealthy
    """
    try:
        from celery import current_app

        # Check if we can connect to broker
        try:
            inspect = current_app.control.inspect()
            stats = inspect.stats()

            if not stats:
                return JsonResponse(
                    {
                        "status": "unhealthy",
                        "message": "No active workers found",
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    status=503,
                )

            # Get task metrics
            metrics = get_task_metrics()

            # Check worker health
            worker_health = {}
            for worker_name, worker_stats in stats.items():
                worker_health[worker_name] = {
                    "status": "healthy",
                    "pool": worker_stats.get("pool", {}),
                    "rusage": worker_stats.get("rusage", {}),
                    "total_tasks": sum(worker_stats.get("total", {}).values()),
                }

            # Get queue lengths
            active_queues = inspect.active_queues()
            queue_info = {}
            if active_queues:
                for worker, queues in active_queues.items():
                    for queue in queues:
                        queue_name = queue["name"]
                        if queue_name not in queue_info:
                            queue_info[queue_name] = {
                                "workers": [],
                                "routing_key": queue.get("routing_key"),
                                "exchange": queue.get("exchange", {}).get("name"),
                            }
                        queue_info[queue_name]["workers"].append(worker)

            response_data = {
                "status": "healthy",
                "workers": worker_health,
                "queues": queue_info,
                "metrics": metrics,
                "broker_url": (
                    current_app.conf.broker_url.replace(
                        current_app.conf.broker_url.split("@")[0].split("//")[1] + "@",
                        "***@",
                    )
                    if "@" in current_app.conf.broker_url
                    else "configured"
                ),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            return JsonResponse(response_data, status=200)

        except Exception as broker_error:
            logger.error(f"Celery broker connection failed: {str(broker_error)}")
            return JsonResponse(
                {
                    "status": "unhealthy",
                    "message": f"Broker connection failed: {str(broker_error)}",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                status=503,
            )

    except ImportError:
        return JsonResponse(
            {
                "status": "unhealthy",
                "message": "Celery not available",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            status=503,
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JsonResponse(
            {
                "status": "unhealthy",
                "message": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            },
            status=503,
        )


@require_http_methods(["GET"])
@csrf_exempt
def system_health_check(request):
    """
    Overall system health check including database, cache, and Celery
    """
    health_status = {
        "status": "healthy",
        "checks": {},
        "timestamp": datetime.now(UTC).isoformat(),
    }

    overall_healthy = True

    # Check database connection
    try:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        health_status["checks"]["database"] = {
            "status": "healthy",
            "details": "Connection successful",
        }
    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check cache
    try:
        from django.core.cache import cache

        cache_key = f"health_check_{datetime.now(UTC).timestamp()}"
        cache.set(cache_key, "test", 60)
        cache_value = cache.get(cache_key)

        if cache_value == "test":
            health_status["checks"]["cache"] = {
                "status": "healthy",
                "details": "Cache read/write successful",
            }
        else:
            raise Exception("Cache read/write failed")

    except Exception as e:
        health_status["checks"]["cache"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check Celery
    try:
        from celery import current_app

        inspect = current_app.control.inspect()
        stats = inspect.stats()

        if stats:
            health_status["checks"]["celery"] = {
                "status": "healthy",
                "workers": len(stats),
                "details": "Workers active",
            }
        else:
            health_status["checks"]["celery"] = {
                "status": "unhealthy",
                "error": "No active workers",
            }
            overall_healthy = False

    except Exception as e:
        health_status["checks"]["celery"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Set overall status
    if not overall_healthy:
        health_status["status"] = "unhealthy"

    status_code = 200 if overall_healthy else 503
    return JsonResponse(health_status, status=status_code)


@require_http_methods(["POST"])
@csrf_exempt
def test_email_task(request):
    """
    Test endpoint to trigger email task for monitoring
    Only available in development/testing
    """
    from django.conf import settings

    if getattr(settings, "DEBUG", False):
        try:
            from apps.accounts.tasks import EmailTasks

            # Test with a dummy task
            task = EmailTasks.send_otp_email.delay(1, "test_email")

            return JsonResponse(
                {
                    "status": "success",
                    "task_id": task.id,
                    "message": "Test email task queued",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                status=200,
            )

        except Exception as e:
            return JsonResponse(
                {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                status=500,
            )
    else:
        return JsonResponse(
            {
                "status": "error",
                "error": "Test endpoint only available in debug mode",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            status=403,
        )
