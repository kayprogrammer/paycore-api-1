"""
Real-world examples of cache usage in PayCore API.

Copy these examples to your actual views/services and customize as needed.
"""

from apps.common.cache import cacheable, invalidate_cache, CacheManager


# ============================================================
# EXAMPLE 1: Loan Products with Caching
# ============================================================


@cacheable(
    key="loans:products:{{currency_code}}:{{filters}}",
    hash_params=["filters"],
    ttl=1800,  # 30 minutes - loan products don't change often
    debug=True,
)
async def get_loan_products_cached(currency_code: str, filters: dict = None):
    """
    Get loan products with caching.
    Cache is invalidated when products are created/updated.
    """
    from apps.loans.models import LoanProduct

    query = LoanProduct.objects.filter(currency__code=currency_code)

    if filters:
        if filters.get("is_active") is not None:
            query = query.filter(is_active=filters["is_active"])
        if filters.get("min_amount"):
            query = query.filter(min_amount__gte=filters["min_amount"])
        if filters.get("max_amount"):
            query = query.filter(max_amount__lte=filters["max_amount"])

    products = await query.select_related("currency").all()
    return list(products)


@invalidate_cache(
    patterns=[
        "loans:products:*",  # Invalidate all loan product caches
    ],
    debug=True,
)
async def create_loan_product(data: dict):
    """Create loan product and invalidate related caches."""
    from apps.loans.models import LoanProduct

    product = await LoanProduct.objects.acreate(**data)
    return product


# ============================================================
# EXAMPLE 2: Investment Products
# ============================================================


@cacheable(
    key="investments:products:{{currency_code}}:{{product_type}}",
    ttl=3600,  # 1 hour
)
async def get_investment_products_cached(currency_code: str, product_type: str = None):
    """Get investment products with caching."""
    from apps.investments.models import InvestmentProduct

    query = InvestmentProduct.objects.filter(
        currency__code=currency_code, is_active=True
    )

    if product_type:
        query = query.filter(product_type=product_type)

    products = await query.select_related("currency").all()
    return list(products)


@invalidate_cache(
    patterns=[
        "investments:products:*",
    ]
)
async def update_investment_product(product_id: str, data: dict):
    """Update investment product and clear caches."""
    from apps.investments.models import InvestmentProduct

    product = await InvestmentProduct.objects.aget(id=product_id)
    for key, value in data.items():
        setattr(product, key, value)
    await product.asave()
    return product


# ============================================================
# EXAMPLE 3: User Wallet Summary
# ============================================================


@cacheable(
    key="wallets:summary:{{user_id}}",
    ttl=120,  # 2 minutes - wallets change frequently
)
async def get_user_wallet_summary(user_id: int):
    """
    Get user's wallet summary with caching.
    Short TTL because wallets are frequently updated.
    """
    from apps.wallets.models import Wallet
    from decimal import Decimal

    wallets = (
        await Wallet.objects.filter(user_id=user_id, status="active")
        .select_related("currency")
        .all()
    )

    primary_wallet = next((w for w in wallets if w.is_primary), None)

    return {
        "total_wallets": len(wallets),
        "total_balance_usd": sum(
            w.balance * w.currency.exchange_rate_usd for w in wallets
        ),
        "wallets": [
            {
                "id": str(w.id),
                "currency": w.currency.code,
                "balance": float(w.balance),
                "is_primary": w.is_primary,
            }
            for w in wallets
        ],
        "primary_wallet_id": str(primary_wallet.id) if primary_wallet else None,
    }


@invalidate_cache(
    patterns=[
        "wallets:summary:{{user_id}}",
        "wallets:{{user_id}}:list",
        "transactions:{{user_id}}:recent:*",
    ]
)
async def process_transaction(user_id: int, transaction_data: dict):
    """Process transaction and invalidate wallet caches."""
    from apps.transactions.models import Transaction
    from apps.wallets.models import Wallet

    # Create transaction
    transaction = await Transaction.objects.acreate(**transaction_data)

    # Update wallet balance
    wallet = await Wallet.objects.aget(id=transaction_data["wallet_id"])
    wallet.balance += transaction.amount
    await wallet.asave()

    return transaction


# ============================================================
# EXAMPLE 4: Support FAQs
# ============================================================


@cacheable(
    key="support:faqs:{{category}}",
    ttl=3600,  # 1 hour - FAQs rarely change
)
async def get_faqs_by_category(category: str):
    """Get FAQs by category with caching."""
    from apps.support.models import FAQ

    faqs = (
        await FAQ.objects.filter(category=category, is_active=True)
        .order_by("order")
        .all()
    )

    return [
        {
            "id": str(faq.id),
            "question": faq.question,
            "answer": faq.answer,
            "category": faq.category,
        }
        for faq in faqs
    ]


@cacheable(
    key="support:faqs:all",
    ttl=3600,
)
async def get_all_faqs():
    """Get all active FAQs with caching."""
    from apps.support.models import FAQ

    faqs = await FAQ.objects.filter(is_active=True).order_by("category", "order").all()

    return [
        {
            "id": str(faq.id),
            "question": faq.question,
            "answer": faq.answer,
            "category": faq.category,
        }
        for faq in faqs
    ]


@invalidate_cache(
    patterns=[
        "support:faqs:*",  # Clear all FAQ caches
    ]
)
async def create_or_update_faq(faq_id: str = None, data: dict = None):
    """Create or update FAQ and clear caches."""
    from apps.support.models import FAQ

    if faq_id:
        faq = await FAQ.objects.aget(id=faq_id)
        for key, value in data.items():
            setattr(faq, key, value)
        await faq.asave()
    else:
        faq = await FAQ.objects.acreate(**data)

    return faq


# ============================================================
# EXAMPLE 5: Bill Providers
# ============================================================


@cacheable(
    key="bills:providers:{{category}}:{{country_code}}",
    ttl=7200,  # 2 hours - providers rarely change
)
async def get_bill_providers(category: str = None, country_code: str = None):
    """Get bill providers with caching."""
    from apps.bills.models import BillProvider

    query = BillProvider.objects.filter(is_active=True)

    if category:
        query = query.filter(category=category)
    if country_code:
        query = query.filter(country__code=country_code)

    providers = await query.select_related("country").all()

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "category": p.category,
            "country": p.country.code,
            "logo_url": p.logo_url,
        }
        for p in providers
    ]


# ============================================================
# EXAMPLE 6: Manual Cache Management
# ============================================================


async def get_user_recent_transactions(user_id: int, limit: int = 10):
    """
    Example of manual cache management for more control.
    """
    from apps.transactions.models import Transaction

    cache_key = f"transactions:user:{user_id}:recent:{limit}"

    # Try to get from cache
    cached_data = CacheManager.get(cache_key)
    if cached_data is not None:
        return cached_data

    # Cache miss - fetch from database
    transactions = (
        await Transaction.objects.filter(user_id=user_id)
        .order_by("-created_at")[:limit]
        .all()
    )

    data = [
        {
            "id": str(t.id),
            "amount": float(t.amount),
            "type": t.transaction_type,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
        }
        for t in transactions
    ]

    # Cache for 1 minute
    CacheManager.set(cache_key, data, ttl=60)

    return data


async def invalidate_user_transaction_caches(user_id: int):
    """Manually invalidate all transaction caches for a user."""
    CacheManager.delete_pattern(f"paycore:transactions:user:{user_id}:*")


# ============================================================
# EXAMPLE 7: Conditional Caching
# ============================================================


async def get_wallet_balance(user_id: int, wallet_id: str, force_refresh: bool = False):
    """
    Example with conditional caching.
    Use force_refresh=True to bypass cache.
    """
    from apps.wallets.models import Wallet

    cache_key = f"wallet:{wallet_id}:balance"

    # Force refresh bypasses cache
    if force_refresh:
        CacheManager.delete(cache_key)

    # Try cache first
    cached_balance = CacheManager.get(cache_key)
    if cached_balance is not None:
        return cached_balance

    # Fetch from database
    wallet = await Wallet.objects.aget(id=wallet_id, user_id=user_id)
    balance = float(wallet.balance)

    # Cache for 30 seconds
    CacheManager.set(cache_key, balance, ttl=30)

    return balance


# ============================================================
# EXAMPLE 8: Aggregated Data Caching
# ============================================================


@cacheable(
    key="admin:dashboard:stats:{{date}}",
    ttl=600,  # 10 minutes
)
async def get_dashboard_stats(date: str):
    """Cache expensive aggregation queries."""
    from apps.transactions.models import Transaction
    from apps.accounts.models import User
    from django.db.models import Sum, Count
    from datetime import datetime

    target_date = datetime.fromisoformat(date).date()

    # Expensive aggregations
    transaction_stats = await Transaction.objects.filter(
        created_at__date=target_date
    ).aggregate(total_amount=Sum("amount"), total_count=Count("id"))

    user_stats = await User.objects.filter(date_joined__date=target_date).aggregate(
        new_users=Count("id")
    )

    return {
        "date": date,
        "transactions": {
            "total_amount": float(transaction_stats["total_amount"] or 0),
            "count": transaction_stats["total_count"],
        },
        "users": {
            "new_users": user_stats["new_users"],
        },
    }


# ============================================================
# EXAMPLE 9: Currency Exchange Rates
# ============================================================


@cacheable(
    key="currencies:rates:all",
    ttl=1800,  # 30 minutes - rates don't change that often
)
async def get_all_exchange_rates():
    """Cache all currency exchange rates."""
    from apps.wallets.models import Currency

    currencies = await Currency.objects.filter(is_active=True).all()

    return {
        currency.code: {
            "name": currency.name,
            "symbol": currency.symbol,
            "exchange_rate_usd": float(currency.exchange_rate_usd),
            "is_crypto": currency.is_crypto,
        }
        for currency in currencies
    }


@invalidate_cache(
    patterns=[
        "currencies:rates:*",
        "wallets:summary:*",  # Also invalidate wallet summaries
    ]
)
async def update_exchange_rates(rates: dict):
    """Update exchange rates and invalidate related caches."""
    from apps.wallets.models import Currency

    for code, rate in rates.items():
        currency = await Currency.objects.filter(code=code).afirst()
        if currency:
            currency.exchange_rate_usd = rate
            await currency.asave()

    return rates
