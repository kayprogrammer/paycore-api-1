"""
Unit tests for Wallet Operations (apps/wallets/services/wallet_operations.py)

Tests balance operations (credit, debit, hold, release) and spending limits.
These are UNIT tests - testing business logic directly, not API endpoints.
"""

import pytest
from decimal import Decimal

from apps.wallets.services.wallet_operations import WalletOperations
from apps.wallets.models import Wallet, WalletStatus
from apps.common.exceptions import RequestError, ErrorCode


@pytest.mark.unit
@pytest.mark.wallet
class TestCreditOperation:
    """Test wallet credit (deposit) operations."""

    @pytest.mark.django_db(transaction=True)
    async def test_credit_increases_balance(self, user_wallet):
        """Test that credit operation increases wallet balance."""
        initial_balance = user_wallet.balance
        credit_amount = Decimal("100.00")

        await WalletOperations.update_balance(
            wallet=user_wallet,
            amount=credit_amount,
            operation="credit",
            reference="TEST-CREDIT-001",
        )

        await user_wallet.arefresh_from_db()
        assert user_wallet.balance == initial_balance + credit_amount

    @pytest.mark.django_db(transaction=True)
    async def test_credit_increases_available_balance(self, user_wallet):
        """Test that credit increases available balance."""
        initial_available = user_wallet.available_balance
        credit_amount = Decimal("100.00")

        await WalletOperations.update_balance(
            wallet=user_wallet,
            amount=credit_amount,
            operation="credit",
            reference="TEST-CREDIT-002",
        )

        await user_wallet.arefresh_from_db()
        assert user_wallet.available_balance == initial_available + credit_amount

    @pytest.mark.django_db(transaction=True)
    async def test_credit_does_not_affect_pending_balance(self, user_wallet):
        """Test that credit does not change pending balance."""
        initial_pending = user_wallet.pending_balance

        await WalletOperations.update_balance(
            wallet=user_wallet,
            amount=Decimal("100.00"),
            operation="credit",
            reference="Test credit",
        )

        await user_wallet.arefresh_from_db()
        assert user_wallet.pending_balance == initial_pending


@pytest.mark.unit
@pytest.mark.wallet
class TestDebitOperation:
    """Test wallet debit (withdrawal) operations."""

    @pytest.mark.django_db(transaction=True)
    async def test_debit_decreases_balance(self, funded_wallet):
        """Test that debit operation decreases wallet balance."""
        initial_balance = funded_wallet.balance
        debit_amount = Decimal("50.00")

        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=debit_amount,
            operation="debit",
            reference="Test debit",
        )

        await funded_wallet.arefresh_from_db()
        assert funded_wallet.balance == initial_balance - debit_amount

    @pytest.mark.django_db(transaction=True)
    async def test_debit_decreases_available_balance(self, funded_wallet):
        """Test that debit decreases available balance."""
        initial_available = funded_wallet.available_balance
        debit_amount = Decimal("50.00")

        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=debit_amount,
            operation="debit",
            reference="Test debit",
        )

        await funded_wallet.arefresh_from_db()
        assert funded_wallet.available_balance == initial_available - debit_amount

    @pytest.mark.django_db(transaction=True)
    async def test_debit_updates_daily_spent(self, funded_wallet):
        """Test that debit updates daily_spent counter."""
        initial_daily_spent = funded_wallet.daily_spent
        debit_amount = Decimal("50.00")

        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=debit_amount,
            operation="debit",
            reference="Test debit",
        )

        await funded_wallet.arefresh_from_db()
        assert funded_wallet.daily_spent == initial_daily_spent + debit_amount

    @pytest.mark.django_db(transaction=True)
    async def test_debit_updates_monthly_spent(self, funded_wallet):
        """Test that debit updates monthly_spent counter."""
        initial_monthly_spent = funded_wallet.monthly_spent
        debit_amount = Decimal("50.00")

        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=debit_amount,
            operation="debit",
            reference="Test debit",
        )

        await funded_wallet.arefresh_from_db()
        assert funded_wallet.monthly_spent == initial_monthly_spent + debit_amount

    @pytest.mark.django_db(transaction=True)
    async def test_debit_insufficient_balance_rejected(self, funded_wallet):
        """Test that debit with insufficient balance is rejected."""
        # Try to debit more than available
        excessive_amount = funded_wallet.available_balance + Decimal("100.00")

        with pytest.raises(RequestError) as exc_info:
            await WalletOperations.update_balance(
                wallet=funded_wallet,
                amount=excessive_amount,
                operation="debit",
                reference="Test excessive debit",
            )

        assert exc_info.value.err_code == ErrorCode.VALIDATION_ERROR
        assert "Insufficient" in exc_info.value.err_msg

    @pytest.mark.django_db(transaction=True)
    async def test_debit_exactly_available_balance_accepted(self, funded_wallet):
        """Test that debit of exactly available balance is accepted."""
        exact_amount = funded_wallet.available_balance

        # Should not raise
        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=exact_amount,
            operation="debit",
            reference="Test exact debit",
        )

        await funded_wallet.arefresh_from_db()
        assert funded_wallet.available_balance == Decimal("0.00")


@pytest.mark.unit
@pytest.mark.wallet
class TestHoldOperation:
    """Test fund hold operations."""

    @pytest.mark.django_db(transaction=True)
    async def test_hold_moves_to_pending_balance(self, funded_wallet):
        """Test that hold moves funds from available to pending."""
        initial_available = funded_wallet.available_balance
        initial_pending = funded_wallet.pending_balance
        hold_amount = Decimal("100.00")

        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=hold_amount,
            operation="hold",
            reference="Test hold",
        )

        await funded_wallet.arefresh_from_db()
        assert funded_wallet.available_balance == initial_available - hold_amount
        assert funded_wallet.pending_balance == initial_pending + hold_amount

    @pytest.mark.django_db(transaction=True)
    async def test_hold_does_not_change_total_balance(self, funded_wallet):
        """Test that hold does not change total balance."""
        initial_balance = funded_wallet.balance
        hold_amount = Decimal("100.00")

        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=hold_amount,
            operation="hold",
            reference="Test hold",
        )

        await funded_wallet.arefresh_from_db()
        assert funded_wallet.balance == initial_balance

    @pytest.mark.django_db(transaction=True)
    async def test_hold_insufficient_available_balance_rejected(self, funded_wallet):
        """Test that hold with insufficient available balance is rejected."""
        excessive_amount = funded_wallet.available_balance + Decimal("100.00")

        with pytest.raises(RequestError) as exc_info:
            await WalletOperations.update_balance(
                wallet=funded_wallet,
                amount=excessive_amount,
                operation="hold",
                reference="Test excessive hold",
            )

        assert exc_info.value.err_code == ErrorCode.VALIDATION_ERROR
        assert "Insufficient" in exc_info.value.err_msg


@pytest.mark.unit
@pytest.mark.wallet
class TestReleaseOperation:
    """Test fund release operations."""

    @pytest.mark.django_db(transaction=True)
    async def test_release_moves_to_available_balance(self, funded_wallet):
        """Test that release moves funds from pending to available."""
        # First create a hold
        hold_amount = Decimal("100.00")
        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=hold_amount,
            operation="hold",
            reference="Test hold",
        )
        await funded_wallet.arefresh_from_db()

        initial_available = funded_wallet.available_balance
        initial_pending = funded_wallet.pending_balance

        # Now release the hold
        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=hold_amount,
            operation="release",
            reference="Test release",
        )

        await funded_wallet.arefresh_from_db()
        assert funded_wallet.available_balance == initial_available + hold_amount
        assert funded_wallet.pending_balance == initial_pending - hold_amount

    @pytest.mark.django_db(transaction=True)
    async def test_release_does_not_change_total_balance(self, funded_wallet):
        """Test that release does not change total balance."""
        # First create a hold
        hold_amount = Decimal("100.00")
        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=hold_amount,
            operation="hold",
            reference="Test hold",
        )
        await funded_wallet.arefresh_from_db()

        initial_balance = funded_wallet.balance

        # Release the hold
        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=hold_amount,
            operation="release",
            reference="Test release",
        )

        await funded_wallet.arefresh_from_db()
        assert funded_wallet.balance == initial_balance

    @pytest.mark.django_db(transaction=True)
    async def test_release_more_than_pending_rejected(self, funded_wallet):
        """Test that releasing more than pending balance is rejected."""
        # Create small hold
        hold_amount = Decimal("50.00")
        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=hold_amount,
            operation="hold",
            reference="Test hold",
        )
        await funded_wallet.arefresh_from_db()

        # Try to release more than held
        excessive_amount = hold_amount + Decimal("100.00")

        with pytest.raises(RequestError) as exc_info:
            await WalletOperations.update_balance(
                wallet=funded_wallet,
                amount=excessive_amount,
                operation="release",
                reference="Test excessive release",
            )

        assert exc_info.value.err_code == ErrorCode.VALIDATION_ERROR
        assert "Insufficient" in exc_info.value.err_msg


@pytest.mark.unit
@pytest.mark.wallet
class TestSpendingLimits:
    """Test daily and monthly spending limit enforcement."""

    @pytest.mark.django_db(transaction=True)
    async def test_debit_within_daily_limit_accepted(self, funded_wallet):
        """Test that debit within daily limit is accepted."""
        # Set daily limit
        funded_wallet.daily_limit = Decimal("1000.00")
        funded_wallet.daily_spent = Decimal("500.00")
        await funded_wallet.asave()

        debit_amount = Decimal("200.00")  # Within remaining limit

        # Should not raise
        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=debit_amount,
            operation="debit",
            reference="Test debit",
        )

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.skip(
        reason="Spending limit validation not yet implemented in update_balance"
    )
    async def test_debit_exceeds_daily_limit_rejected(self, funded_wallet):
        """Test that debit exceeding daily limit is rejected."""
        # Set daily limit
        funded_wallet.daily_limit = Decimal("1000.00")
        funded_wallet.daily_spent = Decimal("900.00")
        await funded_wallet.asave()

        debit_amount = Decimal("200.00")  # Exceeds remaining limit

        with pytest.raises(RequestError) as exc_info:
            await WalletOperations.update_balance(
                wallet=funded_wallet,
                amount=debit_amount,
                operation="debit",
                reference="Test debit",
            )

        assert exc_info.value.err_code == ErrorCode.DAILY_LIMIT_EXCEEDED

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.skip(
        reason="Spending limit validation not yet implemented in update_balance"
    )
    async def test_debit_exceeds_monthly_limit_rejected(self, funded_wallet):
        """Test that debit exceeding monthly limit is rejected."""
        # Set monthly limit
        funded_wallet.monthly_limit = Decimal("5000.00")
        funded_wallet.monthly_spent = Decimal("4900.00")
        await funded_wallet.asave()

        debit_amount = Decimal("200.00")  # Exceeds remaining limit

        with pytest.raises(RequestError) as exc_info:
            await WalletOperations.update_balance(
                wallet=funded_wallet,
                amount=debit_amount,
                operation="debit",
                reference="Test debit",
            )

        assert exc_info.value.err_code == ErrorCode.MONTHLY_LIMIT_EXCEEDED


@pytest.mark.unit
@pytest.mark.wallet
class TestWalletStatus:
    """Test wallet status restrictions on operations."""

    @pytest.mark.django_db(transaction=True)
    async def test_debit_from_inactive_wallet_rejected(self, funded_wallet):
        """Test that debit from inactive wallet is rejected."""
        funded_wallet.status = WalletStatus.INACTIVE
        await funded_wallet.asave()

        with pytest.raises(RequestError) as exc_info:
            await WalletOperations.update_balance(
                wallet=funded_wallet,
                amount=Decimal("50.00"),
                operation="debit",
                reference="Test debit",
            )

        assert exc_info.value.err_code == ErrorCode.VALIDATION_ERROR
        assert "not active" in exc_info.value.err_msg.lower()

    @pytest.mark.django_db(transaction=True)
    async def test_debit_from_frozen_wallet_rejected(self, funded_wallet):
        """Test that debit from frozen wallet is rejected."""
        funded_wallet.status = WalletStatus.FROZEN
        await funded_wallet.asave()

        with pytest.raises(RequestError) as exc_info:
            await WalletOperations.update_balance(
                wallet=funded_wallet,
                amount=Decimal("50.00"),
                operation="debit",
                reference="Test debit",
            )

        assert exc_info.value.err_code == ErrorCode.VALIDATION_ERROR
        assert "not active" in exc_info.value.err_msg.lower()

    @pytest.mark.django_db(transaction=True)
    async def test_credit_to_active_wallet_accepted(self, user_wallet):
        """Test that credit to active wallet is accepted."""
        user_wallet.status = WalletStatus.ACTIVE
        await user_wallet.asave()

        # Should not raise
        await WalletOperations.update_balance(
            wallet=user_wallet,
            amount=Decimal("100.00"),
            operation="credit",
            reference="Test credit",
        )


@pytest.mark.unit
@pytest.mark.wallet
class TestWalletSummary:
    """Test wallet summary calculations."""

    @pytest.mark.django_db(transaction=True)
    async def test_wallet_summary_aggregates_by_currency(
        self, verified_user, ngn_currency, usd_currency
    ):
        """Test that wallet summary aggregates balances by currency."""
        # Create NGN wallet
        from apps.wallets.services.wallet_manager import WalletManager

        ngn_wallet = await Wallet.objects.acreate(
            user=verified_user,
            currency=ngn_currency,
            account_number=await WalletManager.generate_account_number(),
            balance=Decimal("1000.00"),
            available_balance=Decimal("900.00"),
            pending_balance=Decimal("100.00"),
            name="NGN Wallet",
        )

        # Create USD wallet
        usd_wallet = await Wallet.objects.acreate(
            user=verified_user,
            currency=usd_currency,
            account_number=await WalletManager.generate_account_number(),
            balance=Decimal("500.00"),
            available_balance=Decimal("450.00"),
            pending_balance=Decimal("50.00"),
            name="USD Wallet",
        )

        summary = await WalletOperations.get_wallet_summary(verified_user)

        # Should have 2 currency groups in total_balances
        assert len(summary["total_balances"]) == 2
        assert summary["wallet_count"] == 2

        # Check NGN summary
        ngn_summary = summary["total_balances"]["NGN"]
        assert ngn_summary["total_balance"] == Decimal("1000.00")
        assert ngn_summary["total_available"] == Decimal("900.00")
        assert ngn_summary["total_pending"] == Decimal("100.00")
        assert ngn_summary["wallet_count"] == 1

        # Check USD summary
        usd_summary = summary["total_balances"]["USD"]
        assert usd_summary["total_balance"] == Decimal("500.00")
        assert usd_summary["total_available"] == Decimal("450.00")
        assert usd_summary["total_pending"] == Decimal("50.00")
        assert usd_summary["wallet_count"] == 1

    @pytest.mark.django_db(transaction=True)
    async def test_wallet_summary_combines_multiple_wallets_same_currency(
        self, verified_user, ngn_currency
    ):
        """Test that summary combines multiple wallets of same currency."""
        from apps.wallets.services.wallet_manager import WalletManager
        from apps.wallets.models import WalletType

        # Create two NGN wallets with different types to avoid unique constraint violation
        wallet1 = await Wallet.objects.acreate(
            user=verified_user,
            currency=ngn_currency,
            account_number=await WalletManager.generate_account_number(),
            balance=Decimal("1000.00"),
            available_balance=Decimal("900.00"),
            pending_balance=Decimal("100.00"),
            name="NGN Wallet 1",
            wallet_type=WalletType.MAIN,
            is_default=False,
        )

        wallet2 = await Wallet.objects.acreate(
            user=verified_user,
            currency=ngn_currency,
            account_number=await WalletManager.generate_account_number(),
            balance=Decimal("500.00"),
            available_balance=Decimal("450.00"),
            pending_balance=Decimal("50.00"),
            name="NGN Wallet 2",
            wallet_type=WalletType.SAVINGS,
            is_default=False,
        )

        summary = await WalletOperations.get_wallet_summary(verified_user)

        # Should have only 1 currency group (NGN)
        assert len(summary["total_balances"]) == 1
        assert summary["wallet_count"] == 2

        ngn_summary = summary["total_balances"]["NGN"]
        assert ngn_summary["total_balance"] == Decimal("1500.00")
        assert ngn_summary["total_available"] == Decimal("1350.00")
        assert ngn_summary["total_pending"] == Decimal("150.00")
        assert ngn_summary["wallet_count"] == 2


@pytest.mark.unit
@pytest.mark.wallet
class TestBalanceConsistency:
    """Test balance relationship consistency."""

    @pytest.mark.django_db(transaction=True)
    async def test_balance_equals_available_plus_pending(self, funded_wallet):
        """Test that balance = available_balance + pending_balance."""
        # Create a hold to split balance
        hold_amount = Decimal("200.00")
        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=hold_amount,
            operation="hold",
            reference="Test hold",
        )

        await funded_wallet.arefresh_from_db()

        # Verify relationship
        assert funded_wallet.balance == (
            funded_wallet.available_balance + funded_wallet.pending_balance
        )

    @pytest.mark.django_db(transaction=True)
    async def test_multiple_operations_maintain_consistency(self, funded_wallet):
        """Test that multiple operations maintain balance consistency."""
        # Perform multiple operations
        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=Decimal("100.00"),
            operation="credit",
            reference="Credit 1",
        )

        await funded_wallet.arefresh_from_db()

        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=Decimal("50.00"),
            operation="hold",
            reference="Hold 1",
        )

        await funded_wallet.arefresh_from_db()

        await WalletOperations.update_balance(
            wallet=funded_wallet,
            amount=Decimal("25.00"),
            operation="debit",
            reference="Debit 1",
        )

        await funded_wallet.arefresh_from_db()

        # Verify consistency after all operations
        assert funded_wallet.balance == (
            funded_wallet.available_balance + funded_wallet.pending_balance
        )
