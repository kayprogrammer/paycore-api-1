# PayCore Cache System

A sophisticated Redis-based caching mechanism for Django with decorator-based API.

## Features

- **Template-based cache keys** with placeholder syntax
- **Automatic parameter hashing** for complex objects
- **Pattern-based invalidation** with wildcard support
- **Async and sync function support**
- **Debug mode** for development
- **Context-aware** caching (works with Django Ninja, DRF, etc.)

## Installation

The cache system is already configured. Ensure Redis is running and `django-redis` is installed:

```bash
pip install django-redis hiredis
```

## Configuration

In your `settings.py`:

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
        },
        "KEY_PREFIX": "paycore",
        "TIMEOUT": 300,
    }
}

CACHE_KEY_PREFIX = "paycore"
```

## Quick Start

### 1. Basic Caching

```python
from apps.common.cache import cacheable

@cacheable(
    key='user:{{user_id}}:profile',
    ttl=600  # 10 minutes
)
async def get_user_profile(user_id: int):
    user = await User.objects.select_related('kyc_verification').aget(id=user_id)
    return user
```

**Generated cache key**: `paycore:user:123:profile`

### 2. Caching with Filters (hash complex params)

```python
@cacheable(
    key='loans:products:{{currency_code}}:{{filters}}',
    hash_params=['filters'],  # Hash the filters parameter
    ttl=1800,  # 30 minutes
    debug=True
)
async def get_loan_products(currency_code: str, filters: dict = None):
    query = LoanProduct.objects.filter(currency__code=currency_code)

    if filters:
        if filters.get('is_active'):
            query = query.filter(is_active=True)
        if filters.get('max_amount'):
            query = query.filter(max_amount__lte=filters['max_amount'])

    return await query.select_related('currency').all()
```

**Generated key**: `paycore:loans:products:NGN:a1b2c3d4` (where `a1b2c3d4` is hash of filters)

### 3. Cache Invalidation

```python
from apps.common.cache import invalidate_cache

@invalidate_cache(
    patterns=[
        'user:{{user_id}}:profile',
        'wallets:{{user_id}}:*',  # Wildcard pattern
    ]
)
async def update_user_profile(user_id: int, data: dict):
    user = await User.objects.aget(id=user_id)
    for key, value in data.items():
        setattr(user, key, value)
    await user.asave()
    return user
```

### 4. Manual Cache Operations

```python
from apps.common.cache import CacheManager

# Get from cache
value = CacheManager.get('user:123:profile')

# Set cache with TTL
CacheManager.set('user:123:profile', user_data, ttl=600)

# Delete specific key
CacheManager.delete('user:123:profile')

# Delete by pattern
CacheManager.delete_pattern('user:123:*')

# Get or compute
def fetch_user():
    return User.objects.get(id=123)

user = CacheManager.get_or_set('user:123:profile', fetch_user, ttl=600)
```

## Real-World Examples

### Example 1: Loan Products

```python
from apps.common.cache import cacheable, invalidate_cache

# Cache loan products list
@cacheable(
    key='loans:products:{{currency_code}}:{{filters}}',
    hash_params=['filters'],
    ttl=1800  # 30 minutes - products don't change often
)
async def get_loan_products(currency_code: str, filters: dict = None):
    query = LoanProduct.objects.filter(currency__code=currency_code, is_active=True)

    if filters:
        if filters.get('min_amount'):
            query = query.filter(min_amount__gte=filters['min_amount'])
        if filters.get('max_tenor'):
            query = query.filter(max_tenor__lte=filters['max_tenor'])

    products = await query.select_related('currency').all()
    return list(products)


# Invalidate when creating/updating products
@invalidate_cache(patterns=['loans:products:*'])
async def create_loan_product(data: dict):
    product = await LoanProduct.objects.acreate(**data)
    return product


@invalidate_cache(patterns=['loans:products:*'])
async def update_loan_product(product_id: str, data: dict):
    product = await LoanProduct.objects.aget(id=product_id)
    for key, value in data.items():
        setattr(product, key, value)
    await product.asave()
    return product
```

### Example 2: User Wallet Summary

```python
# Cache wallet summary (short TTL - frequently updated)
@cacheable(
    key='wallets:summary:{{user_id}}',
    ttl=120  # 2 minutes
)
async def get_wallet_summary(user_id: int):
    wallets = await Wallet.objects.filter(
        user_id=user_id,
        status='active'
    ).select_related('currency').all()

    primary_wallet = next((w for w in wallets if w.is_primary), None)

    return {
        'total_wallets': len(wallets),
        'total_balance_usd': sum(w.balance * w.currency.exchange_rate_usd for w in wallets),
        'wallets': [
            {
                'id': str(w.id),
                'currency': w.currency.code,
                'balance': float(w.balance),
                'is_primary': w.is_primary,
            }
            for w in wallets
        ],
        'primary_wallet_id': str(primary_wallet.id) if primary_wallet else None,
    }


# Invalidate on transaction creation
@invalidate_cache(
    patterns=[
        'wallets:summary:{{user_id}}',
        'wallets:{{wallet_id}}:balance',
        'transactions:{{user_id}}:recent',
    ]
)
async def create_transaction(user_id: int, wallet_id: str, data: dict):
    transaction = await Transaction.objects.acreate(user_id=user_id, **data)

    # Update wallet balance
    wallet = await Wallet.objects.aget(id=wallet_id)
    wallet.balance += transaction.amount
    await wallet.asave()

    return transaction
```

### Example 3: Investment Products

```python
# Cache investment products by currency and type
@cacheable(
    key='investments:products:{{currency_code}}:{{product_type}}',
    ttl=3600  # 1 hour
)
async def get_investment_products(currency_code: str, product_type: str = None):
    query = InvestmentProduct.objects.filter(
        currency__code=currency_code,
        is_active=True
    )

    if product_type:
        query = query.filter(product_type=product_type)

    products = await query.select_related('currency').all()
    return list(products)


# Invalidate on update
@invalidate_cache(patterns=['investments:products:*'])
async def update_investment_product(product_id: str, data: dict):
    product = await InvestmentProduct.objects.aget(id=product_id)
    for key, value in data.items():
        setattr(product, key, value)
    await product.asave()
    return product
```

### Example 4: Support FAQs

```python
# Cache FAQs by category
@cacheable(
    key='support:faqs:{{category}}',
    ttl=3600  # 1 hour - FAQs rarely change
)
async def get_faqs_by_category(category: str):
    faqs = await FAQ.objects.filter(
        category=category,
        is_active=True
    ).order_by('order').all()

    return [
        {
            'id': str(faq.id),
            'question': faq.question,
            'answer': faq.answer,
            'category': faq.category,
        }
        for faq in faqs
    ]


# Cache all FAQs
@cacheable(key='support:faqs:all', ttl=3600)
async def get_all_faqs():
    faqs = await FAQ.objects.filter(is_active=True).order_by('category', 'order').all()
    return [
        {
            'id': str(faq.id),
            'question': faq.question,
            'answer': faq.answer,
            'category': faq.category,
        }
        for faq in faqs
    ]


# Invalidate on create/update
@invalidate_cache(patterns=['support:faqs:*'])
async def create_or_update_faq(faq_id: str = None, data: dict = None):
    if faq_id:
        faq = await FAQ.objects.aget(id=faq_id)
        for key, value in data.items():
            setattr(faq, key, value)
        await faq.asave()
    else:
        faq = await FAQ.objects.acreate(**data)
    return faq
```

### Example 5: Bill Providers

```python
# Cache bill providers by category and country
@cacheable(
    key='bills:providers:{{category}}:{{country_code}}',
    ttl=7200  # 2 hours - providers rarely change
)
async def get_bill_providers(category: str = None, country_code: str = None):
    query = BillProvider.objects.filter(is_active=True)

    if category:
        query = query.filter(category=category)
    if country_code:
        query = query.filter(country__code=country_code)

    providers = await query.select_related('country').all()
    return [
        {
            'id': str(p.id),
            'name': p.name,
            'category': p.category,
            'country': p.country.code,
            'logo_url': p.logo_url,
        }
        for p in providers
    ]


# Invalidate on provider changes
@invalidate_cache(patterns=['bills:providers:*'])
async def update_bill_provider(provider_id: str, data: dict):
    provider = await BillProvider.objects.aget(id=provider_id)
    for key, value in data.items():
        setattr(provider, key, value)
    await provider.asave()
    return provider
```

### Example 6: Currency Exchange Rates

```python
# Cache all exchange rates
@cacheable(key='currencies:rates:all', ttl=1800)  # 30 minutes
async def get_all_exchange_rates():
    currencies = await Currency.objects.filter(is_active=True).all()
    return {
        currency.code: {
            'name': currency.name,
            'symbol': currency.symbol,
            'exchange_rate_usd': float(currency.exchange_rate_usd),
            'is_crypto': currency.is_crypto,
        }
        for currency in currencies
    }


# Invalidate on rate updates
@invalidate_cache(
    patterns=[
        'currencies:rates:*',
        'wallets:summary:*',  # Also invalidate wallet summaries (they use rates)
    ]
)
async def update_exchange_rates(rates: dict):
    for code, rate in rates.items():
        currency = await Currency.objects.filter(code=code).afirst()
        if currency:
            currency.exchange_rate_usd = rate
            await currency.asave()
    return rates
```

### Example 7: User Transaction History

```python
# Cache recent transactions
@cacheable(
    key='transactions:{{user_id}}:recent:{{limit}}',
    ttl=60  # 1 minute - transactions change frequently
)
async def get_recent_transactions(user_id: int, limit: int = 10):
    transactions = await Transaction.objects.filter(
        user_id=user_id
    ).order_by('-created_at')[:limit].select_related('wallet', 'wallet__currency').all()

    return [
        {
            'id': str(t.id),
            'amount': float(t.amount),
            'currency': t.wallet.currency.code,
            'type': t.transaction_type,
            'status': t.status,
            'created_at': t.created_at.isoformat(),
        }
        for t in transactions
    ]


# Invalidate on new transaction
@invalidate_cache(
    patterns=[
        'transactions:{{user_id}}:recent:*',
        'wallets:summary:{{user_id}}',
    ]
)
async def record_transaction(user_id: int, transaction_data: dict):
    transaction = await Transaction.objects.acreate(user_id=user_id, **transaction_data)
    return transaction
```

### Example 8: Dashboard Statistics (Aggregations)

```python
# Cache expensive aggregations
@cacheable(
    key='admin:stats:daily:{{date}}',
    ttl=600  # 10 minutes
)
async def get_daily_stats(date: str):
    from django.db.models import Sum, Count
    from datetime import datetime

    target_date = datetime.fromisoformat(date).date()

    # Expensive aggregations
    transaction_stats = await Transaction.objects.filter(
        created_at__date=target_date
    ).aggregate(
        total_amount=Sum('amount'),
        total_count=Count('id')
    )

    user_stats = await User.objects.filter(
        date_joined__date=target_date
    ).aggregate(
        new_users=Count('id')
    )

    return {
        'date': date,
        'transactions': {
            'total_amount': float(transaction_stats['total_amount'] or 0),
            'count': transaction_stats['total_count'],
        },
        'users': {
            'new_users': user_stats['new_users'],
        }
    }
```

## Cache Key Best Practices

### Good Patterns

✅ **Hierarchical structure**: `resource:id:subresource`
```python
key='user:{{user_id}}:profile'
key='wallet:{{wallet_id}}:transactions'
key='loans:{{user_id}}:applications'
```

✅ **Wildcard invalidation**: `resource:id:*`
```python
patterns=['user:{{user_id}}:*']     # Clear all user caches
patterns=['wallet:{{wallet_id}}:*'] # Clear all wallet caches
```

✅ **Include context**: Separate by user/tenant
```python
key='wallets:{{user_id}}:summary'
key='transactions:{{user_id}}:recent'
```

### Avoid

❌ Flat keys without hierarchy
```python
key='user_profile_{{user_id}}'  # Hard to manage
```

❌ Missing context (cache collision risk)
```python
key='profile'  # Collides across all users!
```

## TTL Guidelines

| Data Type | Suggested TTL | Example |
|-----------|---------------|---------|
| Static data | 1-24 hours | Loan products, currencies, FAQs |
| User-specific | 5-15 minutes | User profile, wallet summary |
| Frequently updated | 1-5 minutes | Transaction history, balances |
| Real-time | 30-60 seconds | Exchange rates, notifications |

## Debug Mode

Enable debug logging to see cache operations:

```python
@cacheable(
    key='user:{{user_id}}:profile',
    ttl=600,
    debug=True  # Enable debug logging
)
async def get_user_profile(user_id: int):
    return profile
```

**Debug output**:
```
[Cache Debug] Function: get_user_profile
[Cache Debug] Key Template: user:{{user_id}}:profile
[Cache Debug] Resolved Key: paycore:user:123:profile
[Cache Debug] Context: {'user_id': 123}
[Cache Debug] MISS for paycore:user:123:profile
[Cache Debug] Cached result for paycore:user:123:profile (TTL: 600s)
```

## Monitoring Cache

### Using Redis CLI

```bash
# Access Redis
docker-compose exec redis redis-cli

# List all PayCore cache keys
KEYS paycore:*

# Get specific value
GET paycore:user:123:profile

# Check TTL remaining
TTL paycore:user:123:profile

# Count keys by pattern
KEYS paycore:wallets:*

# Delete keys
DEL paycore:user:123:profile
```

### Using Python

```python
from django_redis import get_redis_connection

redis_conn = get_redis_connection("default")

# Count keys by pattern
user_cache_count = len(redis_conn.keys('paycore:user:*'))

# Get memory usage
memory_info = redis_conn.info('memory')
print(f"Used memory: {memory_info['used_memory_human']}")
```

## Testing

```python
from apps.common.cache import CacheManager
import pytest

@pytest.mark.asyncio
async def test_get_user_profile_caching():
    # Clear cache before test
    CacheManager.delete('paycore:user:123:profile')

    # First call - cache miss, queries database
    result1 = await get_user_profile(user_id=123)

    # Second call - cache hit, no database query
    result2 = await get_user_profile(user_id=123)

    assert result1 == result2

    # Verify cached
    cached = CacheManager.get('paycore:user:123:profile')
    assert cached is not None
```

## Performance Tips

1. **Cache expensive queries** - Database joins, aggregations, external API calls
2. **Use appropriate TTLs** - Balance freshness vs performance
3. **Invalidate precisely** - Use specific patterns instead of wildcards when possible
4. **Monitor hit rates** - Check if caching is effective
5. **Avoid over-caching** - Only cache expensive operations

## Common Pitfalls

1. **Forgetting to invalidate** - Always add `@invalidate_cache` to mutations
2. **Cache stampede** - Multiple simultaneous requests on cache miss
3. **Stale data** - TTL too long for frequently updated data
4. **Over-caching** - Caching everything wastes memory

## Architecture

```
apps/common/cache/
├── __init__.py          # Public exports (cacheable, invalidate_cache, CacheManager)
├── manager.py           # CacheManager class (low-level operations)
├── decorators.py        # @cacheable and @invalidate_cache decorators
├── examples.py          # Real-world usage examples
└── README.md            # This documentation
```

## Further Reading

- [Django Cache Framework](https://docs.djangoproject.com/en/5.1/topics/cache/)
- [django-redis Documentation](https://github.com/jazzband/django-redis)
- [Redis Documentation](https://redis.io/docs/)
