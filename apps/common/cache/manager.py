from typing import Any, Optional, List
from django.core.cache import cache
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django_redis import get_redis_connection
import json, hashlib, logging, traceback
from django.forms.models import model_to_dict

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Centralized cache management for Redis operations.
    Handles get, set, delete, and pattern-based invalidation.
    """

    @staticmethod
    def _prepare_for_cache(value: Any) -> Any:
        """
        Prepare value for caching by converting Django models to serializable dicts.
        This runs BEFORE django-redis's JSONSerializer.
        """
        # Handle Django model instances
        if isinstance(value, Model):
            return CacheManager._model_to_dict(value)

        # Handle lists that might contain Django models
        if isinstance(value, list):
            if value and isinstance(value[0], Model):
                return [CacheManager._model_to_dict(item) for item in value]
            # Recursively handle nested lists
            return [CacheManager._prepare_for_cache(item) for item in value]

        # Handle tuples (like CustomResponse.success returns)
        if isinstance(value, tuple):
            # Check if it's the (status_code, response_data) pattern
            if len(value) == 2 and isinstance(value[1], dict):
                status_code, response_data = value
                # Make a copy to avoid modifying original
                response_data = response_data.copy()

                # Check if 'data' field contains models
                if "data" in response_data:
                    response_data["data"] = CacheManager._prepare_for_cache(
                        response_data["data"]
                    )

                return (status_code, response_data)

            # Generic tuple handling
            return tuple(CacheManager._prepare_for_cache(item) for item in value)

        # Handle dictionaries recursively
        if isinstance(value, dict):
            return {k: CacheManager._prepare_for_cache(v) for k, v in value.items()}

        # Return as-is for primitive types
        return value

    @staticmethod
    def _model_to_dict(instance: Model) -> dict:
        """Convert Django model instance to dictionary."""

        # Get all fields including related fields
        data = model_to_dict(instance)

        # Add pk/id if not present
        if "id" not in data:
            data["id"] = str(instance.pk)
        else:
            # Convert UUID to string
            data["id"] = str(data["id"])

        # Convert any UUID fields to strings
        for key, value in data.items():
            if hasattr(value, "hex"):  # UUID has hex attribute
                data[key] = str(value)

        return data

    @staticmethod
    def _hash_params(params: dict) -> str:
        """Create a consistent hash from parameters."""
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(sorted_params.encode()).hexdigest()

    @staticmethod
    def get(key: str) -> Optional[Any]:
        """
        Retrieve value from cache using raw Redis to avoid serialization issues.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            # Use raw Redis client to bypass django-redis serialization
            redis_client = get_redis_connection("default")

            # Add prefix if configured
            cache_prefix = getattr(settings, "CACHE_KEY_PREFIX", "paycore")
            full_key = f":{cache_prefix}:{key}:1" if not key.startswith(":") else key

            cached_json = redis_client.get(full_key)

            if cached_json is not None:
                logger.info(f"Cache HIT: {key}")
                # Deserialize from JSON
                value = json.loads(cached_json)
                logger.info(f"Cache GET - Retrieved value type: {type(value)}")
                logger.info(f"Cache GET - Retrieved value: {str(value)[:200]}")
                return value

            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache GET error for key '{key}': {e}")
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    def set(key: str, value: Any, ttl: int = 300) -> bool:
        """
        Store value in cache using raw Redis to avoid serialization issues.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (default: 300 seconds / 5 minutes)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare value for caching by converting Django models to dicts
            prepared_value = CacheManager._prepare_for_cache(value)

            # Serialize to JSON
            json_value = json.dumps(prepared_value, cls=DjangoJSONEncoder)

            # Use raw Redis client to bypass django-redis serialization
            redis_client = get_redis_connection("default")

            # Key already has prefix from build_key(), just use it directly
            redis_client.setex(key, ttl, json_value)

            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache SET error for key '{key}': {e}")
            return False

    @staticmethod
    def delete(key: str) -> bool:
        """
        Delete a specific key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            cache.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache DELETE error for key '{key}': {e}")
            return False

    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Pattern to match (e.g., 'user:*', 'wallets:123:*')

        Returns:
            Number of keys deleted
        """
        try:
            # Get Redis connection from Django cache

            redis_conn = get_redis_connection("default")

            # Find all keys matching the pattern
            keys = redis_conn.keys(pattern)

            if not keys:
                logger.debug(f"No keys found for pattern: {pattern}")
                return 0

            # Delete all matching keys
            deleted_count = redis_conn.delete(*keys)
            logger.info(
                f"Cache INVALIDATE: {deleted_count} keys deleted for pattern '{pattern}'"
            )
            return deleted_count

        except ImportError:
            logger.warning(
                "django-redis not installed, using fallback pattern deletion"
            )
            # Fallback: only delete exact key
            cache.delete(pattern.replace("*", ""))
            return 1
        except Exception as e:
            logger.error(f"Cache DELETE_PATTERN error for pattern '{pattern}': {e}")
            return 0

    @staticmethod
    def clear_all() -> bool:
        """
        Clear all cache entries.

        Returns:
            True if successful, False otherwise
        """
        try:
            cache.clear()
            logger.warning("Cache CLEAR: All cache entries cleared")
            return True
        except Exception as e:
            logger.error(f"Cache CLEAR error: {e}")
            return False

    @staticmethod
    def build_key(
        key_template: str,
        context: dict,
        hash_params: Optional[List[str]] = None,
    ) -> str:
        """
        Build cache key from template and context.

        Args:
            key_template: Template with placeholders (e.g., 'user:{{user_id}}:profile')
            context: Dictionary with values to replace placeholders
            hash_params: List of parameter names to hash (e.g., ['filters', 'options'])

        Returns:
            Fully resolved cache key

        Examples:
            >>> CacheManager.build_key('user:{{user_id}}:profile', {'user_id': 123})
            'user:123:profile'

            >>> CacheManager.build_key(
            ...     'loans:products:{{currency}}:{{filters}}',
            ...     {'currency': 'NGN', 'filters': {'active': True}},
            ...     hash_params=['filters']
            ... )
            'loans:products:NGN:a1b2c3d4'
        """
        resolved_key = key_template

        # Replace placeholders
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in resolved_key:
                # Check if this parameter should be hashed
                if hash_params and key in hash_params:
                    if isinstance(value, (dict, list)):
                        hashed_value = CacheManager._hash_params({key: value})
                        resolved_key = resolved_key.replace(placeholder, hashed_value)
                    else:
                        resolved_key = resolved_key.replace(placeholder, str(value))
                else:
                    resolved_key = resolved_key.replace(placeholder, str(value))

        # Add cache prefix if configured
        cache_prefix = getattr(settings, "CACHE_KEY_PREFIX", "paycore")
        return f"{cache_prefix}:{resolved_key}"

    @staticmethod
    def get_or_set(
        key: str,
        callback: callable,
        ttl: int = 300,
        *args,
        **kwargs,
    ) -> Any:
        """
        Get value from cache or compute and cache it.

        Args:
            key: Cache key
            callback: Function to call if cache miss
            ttl: Time-to-live in seconds
            *args: Arguments to pass to callback
            **kwargs: Keyword arguments to pass to callback

        Returns:
            Cached or computed value
        """
        # Try to get from cache
        cached_value = CacheManager.get(key)
        if cached_value is not None:
            return cached_value

        # Cache miss - compute value
        computed_value = callback(*args, **kwargs)

        # Cache the result
        CacheManager.set(key, computed_value, ttl)

        return computed_value
