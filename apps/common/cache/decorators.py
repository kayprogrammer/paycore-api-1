from typing import Any, List, Callable
import hashlib

from django.db.models.base import settings
from ninja.utils import contribute_operation_callback
from django.http import HttpResponse
from .manager import CacheManager
import functools, logging, inspect

logger = logging.getLogger(__name__)


def cacheable(
    key: str,
    ttl: int = 300,
    debug: bool = settings.DEBUG,
):
    """
    Decorator to cache Django Ninja API responses in Redis.

    Cache key format: {prefix}:{key_template}:{query_hash}
    - Path params are replaced in the template for explicit invalidation
    - Query params are automatically hashed and appended
    - User ID is always available as {{user_id}}

    Args:
        key: Cache key template with {{placeholders}} for path params (e.g., 'tickets:detail:{{ticket_id}}:{{user_id}}')
        ttl: Time-to-live in seconds (default: 300 / 5 minutes)
        debug: Enable debug logging

    Examples:
        ```python
        # List endpoint with query params (filters)
        @support_router.get("/faq/list")
        @cacheable(key='faq:list:{{user_id}}', ttl=300)
        async def list_faqs(request, filters: FAQFilterSchema = Query(...)):
            # Query params automatically hashed
            return CustomResponse.success("FAQs", data)

        # Detail endpoint with path param
        @support_router.get("/tickets/{ticket_id}")
        @cacheable(key='tickets:detail:{{ticket_id}}:{{user_id}}', ttl=60)
        async def get_ticket(request, ticket_id: UUID):
            return CustomResponse.success("Ticket", ticket)
        ```

    Invalidation:
        # Invalidate all caches for a specific ticket (all query variations)
        @invalidate_cache(patterns=['paycore:tickets:detail:123e4567-...:*'])

        # Invalidate all FAQ lists (all users, all query params)
        @invalidate_cache(patterns=['paycore:faq:list:*'])

        # Invalidate FAQ lists for specific user (all query params)
        @invalidate_cache(patterns=['paycore:faq:list:user-uuid:*'])
    """

    def decorator(op_func: Callable) -> Callable:
        def _apply_cache_decorator(operation):
            original_run = operation.run
            is_async = inspect.iscoroutinefunction(original_run)

            if is_async:
                @functools.wraps(original_run)
                async def cached_run(request, **kw):
                    path_params = {}

                    user_id = "anon"
                    if operation.auth_callbacks:
                        for auth_callback in operation.auth_callbacks:
                            auth_result = await auth_callback(request)
                            if auth_result:
                                user_id = str(auth_result.id)
                                request.auth = auth_result
                                break
                    elif hasattr(request, 'auth') and request.auth:
                        user_id = str(request.auth.id)

                    path_params['user_id'] = user_id

                    for param_name, param_value in kw.items():
                        if not hasattr(param_value, 'model_dump') and not hasattr(param_value, 'dict'):
                            path_params[param_name] = str(param_value)

                    resolved_key = key
                    for param_name, param_value in path_params.items():
                        placeholder = f"{{{{{param_name}}}}}"
                        if placeholder in resolved_key:
                            resolved_key = resolved_key.replace(placeholder, str(param_value))

                    query_string = request.META.get('QUERY_STRING', '')
                    if query_string:
                        query_hash = hashlib.md5(query_string.encode()).hexdigest()[:12]
                        cache_key = f"paycore:{resolved_key}:{query_hash}"
                    else:
                        cache_key = f"paycore:{resolved_key}"

                    if debug:
                        logger.info(f"[Cache] {operation.view_func.__name__} | Path: {path_params} | Query: {query_string[:50]} | Key: {cache_key}")

                    cached_response = CacheManager.get(cache_key)
                    if cached_response is not None:
                        if debug:
                            logger.info(f"[Cache] HIT: {cache_key}")
                        response = HttpResponse(
                            content=cached_response['content'],
                            status=cached_response['status'],
                            content_type=cached_response['content_type']
                        )
                        return response

                    if debug:
                        logger.info(f"[Cache] MISS: {cache_key}")

                    result = await original_run(request, **kw)

                    if hasattr(result, 'content') and hasattr(result, 'status_code'):
                        cache_data = {
                            'content': result.content.decode('utf-8') if isinstance(result.content, bytes) else result.content,
                            'status': result.status_code,
                            'content_type': result.get('Content-Type', 'application/json')
                        }
                        if debug:
                            logger.info(f"[Cache] SET: {cache_key} (TTL: {ttl}s)")
                        CacheManager.set(cache_key, cache_data, ttl)

                    return result
            else:
                @functools.wraps(original_run)
                def cached_run(request, **kw):
                    path_params = {}

                    user_id = "anon"
                    if operation.auth_callbacks:
                        for auth_callback in operation.auth_callbacks:
                            auth_result = auth_callback(request)
                            if auth_result:
                                user_id = str(auth_result.id)
                                request.auth = auth_result
                                break
                    elif hasattr(request, 'auth') and request.auth:
                        user_id = str(request.auth.id)

                    path_params['user_id'] = user_id

                    for param_name, param_value in kw.items():
                        if not hasattr(param_value, 'model_dump') and not hasattr(param_value, 'dict'):
                            path_params[param_name] = str(param_value)

                    resolved_key = key
                    for param_name, param_value in path_params.items():
                        placeholder = f"{{{{{param_name}}}}}"
                        if placeholder in resolved_key:
                            resolved_key = resolved_key.replace(placeholder, str(param_value))

                    query_string = request.META.get('QUERY_STRING', '')
                    if query_string:
                        query_hash = hashlib.md5(query_string.encode()).hexdigest()[:12]
                        cache_key = f"paycore:{resolved_key}:{query_hash}"
                    else:
                        cache_key = f"paycore:{resolved_key}"

                    if debug:
                        logger.info(f"[Cache] {operation.view_func.__name__} | Path: {path_params} | Query: {query_string[:50]} | Key: {cache_key}")

                    cached_response = CacheManager.get(cache_key)
                    if cached_response is not None:
                        if debug:
                            logger.info(f"[Cache] HIT: {cache_key}")
                        response = HttpResponse(
                            content=cached_response['content'],
                            status=cached_response['status'],
                            content_type=cached_response['content_type']
                        )
                        return response

                    if debug:
                        logger.info(f"[Cache] MISS: {cache_key}")

                    result = original_run(request, **kw)

                    if hasattr(result, 'content') and hasattr(result, 'status_code'):
                        cache_data = {
                            'content': result.content.decode('utf-8') if isinstance(result.content, bytes) else result.content,
                            'status': result.status_code,
                            'content_type': result.get('Content-Type', 'application/json')
                        }
                        if debug:
                            logger.info(f"[Cache] SET: {cache_key} (TTL: {ttl}s)")
                        CacheManager.set(cache_key, cache_data, ttl)

                    return result

            operation.run = cached_run

        if hasattr(op_func, "_ninja_operation"):
            _apply_cache_decorator(op_func._ninja_operation)
        else:
            contribute_operation_callback(op_func, _apply_cache_decorator)

        return op_func

    return decorator


def invalidate_cache(patterns: List[str], debug: bool = False):
    """
    Decorator to invalidate cache entries based on wildcard patterns.

    Args:
        patterns: List of Redis key patterns with wildcards (e.g., ['paycore:faq:list:*'])
        debug: Enable debug logging

    Examples:
        ```python
        @support_router.post("/faq/create")
        @invalidate_cache(patterns=['paycore:faq:list:*'])
        async def create_faq(request, data: FAQSchema):
            faq = await FAQ.objects.acreate(**data)
            return CustomResponse.success("FAQ created", faq)

        @invalidate_cache(patterns=[
            'paycore:wallets:summary:*',
            'paycore:transactions:list:*',
        ])
        async def create_transaction(request, data: dict):
            transaction = await Transaction.objects.acreate(**data)
            return transaction
        ```
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs)

            total_deleted = 0
            for pattern in patterns:
                if debug:
                    logger.info(f"[Cache Invalidate] Pattern: {pattern}")

                deleted_count = CacheManager.delete_pattern(pattern)
                total_deleted += deleted_count

                if debug:
                    logger.info(f"[Cache Invalidate] Deleted {deleted_count} keys")

            if debug:
                logger.info(f"[Cache Invalidate] Total: {total_deleted} keys deleted")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)

            total_deleted = 0
            for pattern in patterns:
                if debug:
                    logger.info(f"[Cache Invalidate] Pattern: {pattern}")

                deleted_count = CacheManager.delete_pattern(pattern)
                total_deleted += deleted_count

                if debug:
                    logger.info(f"[Cache Invalidate] Deleted {deleted_count} keys")

            if debug:
                logger.info(f"[Cache Invalidate] Total: {total_deleted} keys deleted")

            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
