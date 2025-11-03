import functools, logging, inspect
from typing import Any, Optional, List, Callable

from django.db.models.base import settings
from ninja.utils import contribute_operation_callback
from .manager import CacheManager

logger = logging.getLogger(__name__)


def cacheable(
    key: str,
    ttl: int = 300,
    hash_params: Optional[List[str]] = None,
    debug: bool = settings.DEBUG,
):
    """
    Decorator to cache Django Ninja API responses in Redis.
    Automatically integrates with Django Ninja's operation system.

    Args:
        key: Cache key template with placeholders (e.g., 'faq:list:{{filters}}')
        ttl: Time-to-live in seconds (default: 300 / 5 minutes)
        hash_params: List of parameter names to hash (e.g., ['filters', 'options'])
        debug: Enable debug logging

    Examples:
        ```python
        @support_router.get("/faq/list")
        @cacheable(
            key='faq:list:{{filters}}',
            hash_params=['filters'],
            ttl=300
        )
        async def list_faqs(request, filters: FAQFilterSchema):
            return CustomResponse.success("FAQs", data)
        ```
    """

    def decorator(op_func: Callable) -> Callable:
        """Decorator that integrates with Django Ninja's operation system"""

        def _apply_cache_decorator(operation):
            """
            Apply caching to the operation's run method.
            This is called after Django Ninja has created the Operation object.
            """
            original_run = operation.run

            # Check if this is an async operation
            import inspect
            is_async = inspect.iscoroutinefunction(original_run)

            if is_async:
                @functools.wraps(original_run)
                async def cached_run(request, **kw):
                    """Async wrapper for operation.run that adds caching"""
                    # Build context from resolved parameters in kw
                    context = {}

                    # Add auth info if available
                    if hasattr(request, "auth") and request.auth:
                        context["request"] = {
                            "auth": {
                                "id": str(getattr(request.auth, "id", None)),
                                "email": getattr(request.auth, "email", None),
                            }
                        }

                    # Add all resolved parameters from kw
                    for param_name, param_value in kw.items():
                        # Handle Pydantic/schema objects by converting to dict
                        if hasattr(param_value, "dict") and callable(param_value.dict):
                            try:
                                context[param_name] = param_value.dict()
                            except:
                                context[param_name] = param_value
                        elif hasattr(param_value, "model_dump") and callable(param_value.model_dump):
                            try:
                                context[param_name] = param_value.model_dump()
                            except:
                                context[param_name] = param_value
                        else:
                            context[param_name] = param_value

                    # Generate cache key
                    cache_key = CacheManager.build_key(key, context, hash_params)

                    if debug:
                        logger.info(f"[Cache] {operation.view_func.__name__} | Key: {cache_key}")

                    # Try to get from cache
                    cached_value = CacheManager.get(cache_key)
                    if cached_value is not None:
                        if debug:
                            logger.info(f"[Cache] HIT: {cache_key}")
                        return cached_value

                    if debug:
                        logger.info(f"[Cache] MISS: {cache_key}")

                    # Cache miss - execute the original operation.run (await it!)
                    result = await original_run(request, **kw)

                    # Cache the HttpResponse
                    if debug:
                        logger.info(f"[Cache] SET: {cache_key} (TTL: {ttl}s)")
                    CacheManager.set(cache_key, result, ttl)

                    return result
            else:
                @functools.wraps(original_run)
                def cached_run(request, **kw):
                    """Sync wrapper for operation.run that adds caching"""
                    # Build context from resolved parameters
                    context = {}

                    if hasattr(request, "auth") and request.auth:
                        context["request"] = {
                            "auth": {
                                "id": str(getattr(request.auth, "id", None)),
                                "email": getattr(request.auth, "email", None),
                            }
                        }

                    for param_name, param_value in kw.items():
                        if hasattr(param_value, "dict") and callable(param_value.dict):
                            try:
                                context[param_name] = param_value.dict()
                            except:
                                context[param_name] = param_value
                        elif hasattr(param_value, "model_dump") and callable(param_value.model_dump):
                            try:
                                context[param_name] = param_value.model_dump()
                            except:
                                context[param_name] = param_value
                        else:
                            context[param_name] = param_value

                    cache_key = CacheManager.build_key(key, context, hash_params)

                    if debug:
                        logger.info(f"[Cache] {operation.view_func.__name__} | Key: {cache_key}")

                    cached_value = CacheManager.get(cache_key)
                    if cached_value is not None:
                        if debug:
                            logger.info(f"[Cache] HIT: {cache_key}")
                        return cached_value

                    if debug:
                        logger.info(f"[Cache] MISS: {cache_key}")

                    result = original_run(request, **kw)

                    if debug:
                        logger.info(f"[Cache] SET: {cache_key} (TTL: {ttl}s)")
                    CacheManager.set(cache_key, result, ttl)

                    return result

            # Replace the operation's run method with our cached version
            operation.run = cached_run

        # Register the cache decorator to be applied when the operation is created
        # This works exactly like decorate_view does
        if hasattr(op_func, "_ninja_operation"):
            # Decorator applied on top of @api.method
            _apply_cache_decorator(op_func._ninja_operation)
        else:
            # Decorator applied below @api.method
            contribute_operation_callback(op_func, _apply_cache_decorator)

        return op_func

    return decorator


def invalidate_cache(patterns: List[str], debug: bool = False):
    """
    Decorator to invalidate cache entries based on patterns with wildcard support.

    Args:
        patterns: List of cache key patterns to invalidate
        debug: Enable debug logging

    Examples:
        ```python
        @invalidate_cache(
            patterns=[
                'loans:products:*',
                'loans:{{user_id}}:applications',
            ]
        )
        async def create_loan_product(data: dict):
            product = await LoanProduct.objects.acreate(**data)
            return product
        ```
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Execute the function first
            result = await func(*args, **kwargs)

            # Build context from function arguments
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            context = dict(bound_args.arguments)

            # Invalidate all matching patterns
            total_deleted = 0
            for pattern_template in patterns:
                # Resolve pattern with context
                resolved_pattern = CacheManager.build_key(pattern_template, context)

                if debug:
                    logger.info(f"[Cache Debug] Invalidating pattern: {resolved_pattern}")

                # Delete keys matching pattern
                deleted_count = CacheManager.delete_pattern(resolved_pattern)
                total_deleted += deleted_count

                if debug:
                    logger.info(f"[Cache Debug] Deleted {deleted_count} keys")

            if debug:
                logger.info(f"[Cache Debug] Total deleted: {total_deleted} keys")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Execute the function first
            result = func(*args, **kwargs)

            # Build context and invalidate
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            context = dict(bound_args.arguments)

            total_deleted = 0
            for pattern_template in patterns:
                resolved_pattern = CacheManager.build_key(pattern_template, context)
                deleted_count = CacheManager.delete_pattern(resolved_pattern)
                total_deleted += deleted_count

            return result

        # Return appropriate wrapper
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
