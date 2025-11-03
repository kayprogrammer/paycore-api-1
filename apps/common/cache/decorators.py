import functools
import inspect
import logging
from typing import Any, Optional, List, Callable
from .manager import CacheManager

logger = logging.getLogger(__name__)


def cacheable(
    key: str,
    ttl: int = 300,
    hash_params: Optional[List[str]] = None,
    debug: bool = False,
):
    """
    Decorator to cache function results in Redis with template-based key generation.

    Args:
        key: Cache key template with placeholders (e.g., 'user:{{user_id}}:posts')
        ttl: Time-to-live in seconds (default: 300 / 5 minutes)
        hash_params: List of parameter names to hash (e.g., ['filters', 'options'])
        debug: Enable debug logging

    Placeholder syntax:
        - {{param_name}}: Direct parameter access
        - {{context.req.user_id}}: Nested access via dot notation
        - {{filters}}: Parameter that will be hashed if in hash_params

    Examples:
        ```python
        @cacheable(
            key='user:{{user_id}}:profile',
            ttl=600
        )
        async def get_user_profile(user_id: int):
            user = await User.objects.aget(id=user_id)
            return user

        @cacheable(
            key='loans:products:{{currency_code}}:{{filters}}',
            hash_params=['filters'],
            ttl=1800,
            debug=True
        )
        async def get_loan_products(currency_code: str, filters: dict = None):
            products = await LoanProduct.objects.filter(
                currency__code=currency_code
            ).all()
            return products

        # With request object (Django Ninja)
        @cacheable(
            key='wallets:summary:{{request.user.id}}',
            ttl=300
        )
        async def get_wallet_summary(request):
            wallets = await Wallet.objects.filter(user=request.user).all()
            return wallets
        ```
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Build context from function arguments
            context = _build_context(func, args, kwargs)

            # Generate cache key
            cache_key = CacheManager.build_key(key, context, hash_params)

            if debug:
                logger.info(f"[Cache Debug] Function: {func.__name__}")
                logger.info(f"[Cache Debug] Key Template: {key}")
                logger.info(f"[Cache Debug] Resolved Key: {cache_key}")
                logger.info(f"[Cache Debug] Context: {context}")

            # Try to get from cache
            cached_value = CacheManager.get(cache_key)
            if cached_value is not None:
                if debug:
                    logger.info(f"[Cache Debug] HIT for {cache_key}")
                return cached_value

            if debug:
                logger.info(f"[Cache Debug] MISS for {cache_key}")

            # Cache miss - execute function
            result = await func(*args, **kwargs)

            # Cache the result
            CacheManager.set(cache_key, result, ttl)

            if debug:
                logger.info(f"[Cache Debug] Cached result for {cache_key} (TTL: {ttl}s)")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Build context from function arguments
            context = _build_context(func, args, kwargs)

            # Generate cache key
            cache_key = CacheManager.build_key(key, context, hash_params)

            if debug:
                logger.info(f"[Cache Debug] Function: {func.__name__}")
                logger.info(f"[Cache Debug] Key Template: {key}")
                logger.info(f"[Cache Debug] Resolved Key: {cache_key}")
                logger.info(f"[Cache Debug] Context: {context}")

            # Try to get from cache
            cached_value = CacheManager.get(cache_key)
            if cached_value is not None:
                if debug:
                    logger.info(f"[Cache Debug] HIT for {cache_key}")
                return cached_value

            if debug:
                logger.info(f"[Cache Debug] MISS for {cache_key}")

            # Cache miss - execute function
            result = func(*args, **kwargs)

            # Cache the result
            CacheManager.set(cache_key, result, ttl)

            if debug:
                logger.info(f"[Cache Debug] Cached result for {cache_key} (TTL: {ttl}s)")

            return result

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def invalidate_cache(patterns: List[str], debug: bool = False):
    """
    Decorator to invalidate cache entries based on patterns with wildcard support.

    Args:
        patterns: List of cache key patterns to invalidate
        debug: Enable debug logging

    Pattern syntax:
        - 'user:{{user_id}}:*': Invalidate all keys for a user
        - 'wallets:{{user_id}}:*': Invalidate all wallet caches for user
        - 'loans:products:*': Invalidate all loan product caches

    Examples:
        ```python
        @invalidate_cache(
            patterns=[
                'user:{{user_id}}:profile',
                'wallets:{{user_id}}:*',
            ]
        )
        async def update_user_profile(user_id: int, data: dict):
            user = await User.objects.aget(id=user_id)
            for key, value in data.items():
                setattr(user, key, value)
            await user.asave()
            return user

        @invalidate_cache(
            patterns=[
                'loans:products:*',
                'loans:{{user_id}}:applications',
            ],
            debug=True
        )
        async def create_loan_product(data: dict):
            product = await LoanProduct.objects.acreate(**data)
            return product

        # Invalidate on transaction (Django Ninja)
        @invalidate_cache(
            patterns=[
                'wallets:summary:{{request.user.id}}',
                'transactions:{{request.user.id}}:recent',
            ]
        )
        async def create_transaction(request, data: dict):
            transaction = await Transaction.objects.acreate(
                user=request.user,
                **data
            )
            return transaction
        ```
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Execute the function first
            result = await func(*args, **kwargs)

            # Build context from function arguments
            context = _build_context(func, args, kwargs)

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
                    logger.info(
                        f"[Cache Debug] Deleted {deleted_count} keys for pattern: {resolved_pattern}"
                    )

            if debug:
                logger.info(
                    f"[Cache Debug] Total deleted: {total_deleted} keys for function: {func.__name__}"
                )

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Execute the function first
            result = func(*args, **kwargs)

            # Build context from function arguments
            context = _build_context(func, args, kwargs)

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
                    logger.info(
                        f"[Cache Debug] Deleted {deleted_count} keys for pattern: {resolved_pattern}"
                    )

            if debug:
                logger.info(
                    f"[Cache Debug] Total deleted: {total_deleted} keys for function: {func.__name__}"
                )

            return result

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _build_context(func: Callable, args: tuple, kwargs: dict) -> dict:
    """
    Build context dictionary from function arguments.

    Handles both positional and keyword arguments, creating a flat dictionary
    that can be used for cache key template resolution.

    Args:
        func: The decorated function
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Dictionary with all function arguments
    """
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()

    context = {}

    for param_name, param_value in bound_args.arguments.items():
        # Handle context objects (Django Ninja, DRF, etc.)
        if param_name == "context" and hasattr(param_value, "req"):
            # Extract nested context attributes
            context["context"] = {
                "req": _extract_request_attrs(param_value.req)
            }
        elif param_name == "request" and hasattr(param_value, "user"):
            # Handle Django request objects
            context["request"] = {
                "user_id": getattr(param_value.user, "id", None),
                "user": getattr(param_value.user, "email", None),
            }
        else:
            # Regular parameters
            context[param_name] = param_value

    return context


def _extract_request_attrs(req_obj: Any) -> dict:
    """
    Extract useful attributes from request object.

    Args:
        req_obj: Request object (Django HttpRequest, etc.)

    Returns:
        Dictionary with extracted attributes
    """
    attrs = {}

    # Common attributes to extract
    attr_names = [
        "user_id",
        "organization_id",
        "tenant_id",
        "workspace_id",
        "user",
        "email",
    ]

    for attr_name in attr_names:
        if hasattr(req_obj, attr_name):
            attrs[attr_name] = getattr(req_obj, attr_name)

    # Extract user ID if user object exists
    if hasattr(req_obj, "user") and hasattr(req_obj.user, "id"):
        attrs["user_id"] = req_obj.user.id

    return attrs
