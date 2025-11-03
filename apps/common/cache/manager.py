import json
import hashlib
import logging
from typing import Any, Optional, List
from django.core.cache import cache
from django.conf import settings
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Centralized cache management for Redis operations.
    Handles get, set, delete, and pattern-based invalidation.
    """

    @staticmethod
    def _serialize_value(value: Any) -> str:
        """Serialize Python objects to JSON string."""
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            logger.warning(f"Serialization error: {e}, storing as string")
            return str(value)

    @staticmethod
    def _deserialize_value(value: str) -> Any:
        """Deserialize JSON string back to Python object."""
        try:
            return json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return value

    @staticmethod
    def _hash_params(params: dict) -> str:
        """Create a consistent hash from parameters."""
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(sorted_params.encode()).hexdigest()

    @staticmethod
    def get(key: str) -> Optional[Any]:
        """
        Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            value = cache.get(key)
            if value is not None:
                logger.debug(f"Cache HIT: {key}")
                return CacheManager._deserialize_value(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache GET error for key '{key}': {e}")
            return None

    @staticmethod
    def set(key: str, value: Any, ttl: int = 300) -> bool:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (default: 300 seconds / 5 minutes)

        Returns:
            True if successful, False otherwise
        """
        try:
            serialized_value = CacheManager._serialize_value(value)
            cache.set(key, serialized_value, timeout=ttl)
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
            logger.info(f"Cache INVALIDATE: {deleted_count} keys deleted for pattern '{pattern}'")
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
