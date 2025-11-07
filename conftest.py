"""
Pytest configuration and shared fixtures for PayCore API tests.

This file contains:
- Test database configuration
- Shared fixtures for models
- Factory functions for creating test data
- Mock utilities for external services
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, AsyncMock, patch
from django.conf import settings
from django.contrib.auth import get_user_model

# Import models
from apps.accounts.models import User
from apps.wallets.models import Wallet, Currency
from apps.transactions.models import Transaction, TransactionType, TransactionStatus
from apps.loans.models import LoanProduct, LoanApplication
from apps.compliance.models import KYCVerification, KYCStatus, KYCLevel
from apps.cards.models import Card, CardStatus, CardType

User = get_user_model()


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom settings."""
    settings.DEBUG = False
    settings.CELERY_TASK_ALWAYS_EAGER = True  # Run Celery tasks synchronously in tests
    settings.CELERY_TASK_EAGER_PROPAGATES = True


# ============================================================================
# USER FIXTURES
# ============================================================================


@pytest.fixture
def base_user():
    """Create a basic unverified user."""
    return User.objects.create_user(
        first_name="Test",
        last_name="User",
        email="testuser@example.com",
        password="TestPassword123!",
        is_email_verified=False,
    )


@pytest.fixture
async def verified_user(request):
    """Create a verified user with unique email for each test."""
    import time

    unique_email = f"verified{int(time.time() * 1000000)}@example.com"

    user = await User.objects.acreate(
        first_name="Verified",
        last_name="User",
        email=unique_email,
        is_email_verified=True,
    )
    user.set_password("TestPassword123!")
    await user.asave()
    return user


@pytest.fixture
def kyc_approved_user():
    """Create a KYC-approved user with verified email."""
    user = User.objects.create_user(
        first_name="KYC",
        last_name="Approved",
        email="kycapproved@example.com",
        password="TestPassword123!",
        is_email_verified=True,
    )
    # Create KYC verification
    KYCVerification.objects.create(
        user=user,
        tier=KYCLevel.TIER_2,
        status=KYCStatus.APPROVED,
        first_name="KYC",
        last_name="Approved",
        country="NG",
    )
    return user


@pytest.fixture
def admin_user():
    """Create an admin user."""
    return User.objects.create_superuser(
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
        password="AdminPassword123!",
    )


# ============================================================================
# CURRENCY & WALLET FIXTURES
# ============================================================================


@pytest.fixture
async def ngn_currency():
    """Create or get NGN currency."""
    currency, _ = await Currency.objects.aget_or_create(
        code="NGN",
        defaults={
            "name": "Nigerian Naira",
            "symbol": "₦",
            "is_active": True,
        },
    )
    return currency


@pytest.fixture
async def usd_currency():
    """Create or get USD currency."""
    currency, _ = await Currency.objects.aget_or_create(
        code="USD",
        defaults={
            "name": "US Dollar",
            "symbol": "$",
            "is_active": True,
        },
    )
    return currency


@pytest.fixture
async def user_wallet(verified_user, ngn_currency):
    """Create a wallet for verified user with NGN currency."""
    from apps.wallets.services.wallet_manager import WalletManager

    wallet = await Wallet.objects.acreate(
        user=verified_user,
        currency=ngn_currency,
        account_number=await WalletManager.generate_account_number(),
        balance=Decimal("1000.00"),
        available_balance=Decimal("1000.00"),
        name="Main Wallet",
        is_default=True,
    )
    return wallet


@pytest.fixture
async def funded_wallet(verified_user, ngn_currency):
    """Create a well-funded wallet for testing transactions."""
    from apps.wallets.services.wallet_manager import WalletManager

    wallet = await Wallet.objects.acreate(
        user=verified_user,
        currency=ngn_currency,
        account_number=await WalletManager.generate_account_number(),
        balance=Decimal("100000.00"),  # 100k NGN
        available_balance=Decimal("100000.00"),
        name="Funded Wallet",
        is_default=True,
    )
    return wallet


# ============================================================================
# LOAN FIXTURES
# ============================================================================


@pytest.fixture
async def loan_product(ngn_currency):
    """Create a standard loan product."""
    from apps.loans.models import LoanProductType, RepaymentFrequency

    return await LoanProduct.objects.acreate(
        name="Personal Loan",
        description="Standard personal loan",
        product_type=LoanProductType.PERSONAL,
        currency=ngn_currency,
        min_amount=Decimal("10000.00"),
        max_amount=Decimal("500000.00"),
        min_interest_rate=Decimal("15.00"),  # 15% annual
        max_interest_rate=Decimal("20.00"),  # 20% annual
        min_tenure_months=3,
        max_tenure_months=12,
        processing_fee_percentage=Decimal("2.00"),
        processing_fee_fixed=Decimal("500.00"),
        min_credit_score=500,
        allowed_repayment_frequencies=[
            RepaymentFrequency.MONTHLY,
            RepaymentFrequency.WEEKLY,
            RepaymentFrequency.BIWEEKLY,
        ],
        is_active=True,
    )


# ============================================================================
# TRANSACTION FIXTURES
# ============================================================================


@pytest.fixture
def sample_transaction(verified_user, user_wallet):
    """Create a sample completed transaction."""
    return Transaction.objects.create(
        user=verified_user,
        wallet=user_wallet,
        amount=Decimal("500.00"),
        type=TransactionType.CREDIT,
        status=TransactionStatus.COMPLETED,
        description="Test transaction",
        reference=f"TXN-{datetime.now().timestamp()}",
    )


# ============================================================================
# MOCK UTILITIES
# ============================================================================


@pytest.fixture
def mock_email_send():
    """Mock email sending to prevent actual email dispatch during tests."""
    with patch(
        "apps.accounts.emails.EmailUtil.send_otp", new_callable=AsyncMock
    ) as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_celery_task():
    """Mock Celery task execution."""
    with patch("celery.app.task.Task.apply_async") as mock:
        mock.return_value = Mock(id="test-task-id")
        yield mock


@pytest.fixture
def mock_google_auth():
    """Mock Google OAuth token validation."""
    with patch("apps.accounts.auth.Authentication.validate_google_token") as mock:
        mock.return_value = (
            {
                "email": "google@example.com",
                "name": "Google User",
                "picture": "https://example.com/pic.jpg",
            },
            None,
            None,
        )
        yield mock


@pytest.fixture
def mock_payment_provider():
    """Mock external payment provider responses."""
    with patch("apps.wallets.providers.base.WalletProvider.create_wallet") as mock:
        mock.return_value = {
            "success": True,
            "account_number": "1234567890",
            "account_name": "Test User",
        }
        yield mock


# ============================================================================
# TIME UTILITIES
# ============================================================================


@pytest.fixture
def freeze_time():
    """Freeze time for testing time-sensitive logic."""

    def _freeze(frozen_time=None):
        if frozen_time is None:
            frozen_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

        with patch("django.utils.timezone.now", return_value=frozen_time):
            yield frozen_time

    return _freeze


# ============================================================================
# DECIMAL HELPERS
# ============================================================================


@pytest.fixture
def decimal_helper():
    """Helper functions for decimal comparisons in tests."""

    class DecimalHelper:
        @staticmethod
        def approx_equal(a: Decimal, b: Decimal, precision: int = 2) -> bool:
            """Check if two decimals are approximately equal."""
            return abs(a - b) < Decimal(10) ** -precision

        @staticmethod
        def to_decimal(value: float | int | str) -> Decimal:
            """Safely convert to Decimal."""
            return Decimal(str(value))

    return DecimalHelper()


# ============================================================================
# DATABASE HELPERS
# ============================================================================


@pytest.fixture
def db_cleanup():
    """Clean up database after each test."""
    yield
    # Cleanup happens after test
    Transaction.objects.all().delete()
    Wallet.objects.all().delete()
    LoanApplication.objects.all().delete()
    KYCVerification.objects.all().delete()
    User.objects.all().delete()
