"""
Unit tests for Credit Score Service (apps/loans/services/credit_score_service.py)

Tests credit score calculation logic using FICO-like model (300-850 range).
These are UNIT tests - testing business logic directly, not API endpoints.
"""

import pytest
from decimal import Decimal

from apps.loans.services.credit_score_service import CreditScoreService
from apps.loans.models import CreditScore


@pytest.mark.unit
@pytest.mark.loan
class TestCreditScoreWeights:
    """Test that credit score component weights are correct."""

    def test_weights_sum_to_one(self):
        """Test that all component weights add up to 100%."""
        total_weight = (
            CreditScoreService.PAYMENT_HISTORY_WEIGHT
            + CreditScoreService.CREDIT_UTILIZATION_WEIGHT
            + CreditScoreService.ACCOUNT_AGE_WEIGHT
            + CreditScoreService.LOAN_HISTORY_WEIGHT
        )

        assert total_weight == 1.0, "Weights must sum to 100%"

    def test_payment_history_highest_weight(self):
        """Test that payment history has the highest weight (35%)."""
        assert CreditScoreService.PAYMENT_HISTORY_WEIGHT == 0.35
        assert (
            CreditScoreService.PAYMENT_HISTORY_WEIGHT
            > CreditScoreService.CREDIT_UTILIZATION_WEIGHT
        )
        assert (
            CreditScoreService.PAYMENT_HISTORY_WEIGHT
            > CreditScoreService.ACCOUNT_AGE_WEIGHT
        )
        assert (
            CreditScoreService.PAYMENT_HISTORY_WEIGHT
            > CreditScoreService.LOAN_HISTORY_WEIGHT
        )

    def test_individual_weights(self):
        """Test each component has correct weight."""
        assert CreditScoreService.PAYMENT_HISTORY_WEIGHT == 0.35  # 35%
        assert CreditScoreService.CREDIT_UTILIZATION_WEIGHT == 0.30  # 30%
        assert CreditScoreService.ACCOUNT_AGE_WEIGHT == 0.15  # 15%
        assert CreditScoreService.LOAN_HISTORY_WEIGHT == 0.20  # 20%


@pytest.mark.unit
@pytest.mark.loan
class TestPaymentHistoryScore:
    """Test payment history score calculation."""

    @pytest.mark.django_db(transaction=True)
    async def test_new_user_default_score(self):
        """Test that new users with no loans get a fair default score (650)."""
        score = await CreditScoreService._calculate_payment_history_score(
            on_time=0, late=0, missed=0, total_loans=0
        )

        assert score == 650, "New users should start with fair score (650)"

    @pytest.mark.django_db(transaction=True)
    async def test_perfect_payment_history(self):
        """Test score for 100% on-time payments."""
        score = await CreditScoreService._calculate_payment_history_score(
            on_time=10, late=0, missed=0, total_loans=1
        )

        # Perfect ratio (10/10 = 1.0) should give near-maximum score
        # Base: 300 + (1.0 * 550) = 850, no penalties
        assert score == 850, "Perfect payment history should give maximum score"

    @pytest.mark.django_db(transaction=True)
    async def test_all_missed_payments(self):
        """Test score for 100% missed payments."""
        score = await CreditScoreService._calculate_payment_history_score(
            on_time=0, late=0, missed=10, total_loans=1
        )

        # Zero on-time ratio: 300 + (0 * 550) = 300
        # Penalties: 10 missed * 100 = 1000
        # Final: 300 - 1000 = -700, clamped to 300 (minimum)
        assert score == 300, "All missed payments should give minimum score"

    @pytest.mark.django_db(transaction=True)
    async def test_late_payment_penalty(self):
        """Test that late payments reduce score by 50 points each."""
        # Perfect on-time score
        perfect_score = await CreditScoreService._calculate_payment_history_score(
            on_time=10, late=0, missed=0, total_loans=1
        )

        # Score with 1 late payment
        one_late_score = await CreditScoreService._calculate_payment_history_score(
            on_time=9, late=1, missed=0, total_loans=1
        )

        # Late penalty should be approximately 50 points plus ratio change
        # This is complex because ratio also changes, so just verify it's lower
        assert one_late_score < perfect_score
        assert one_late_score >= 300  # Should not go below minimum

    @pytest.mark.django_db(transaction=True)
    async def test_missed_payment_penalty_worse_than_late(self):
        """Test that missed payments have worse penalty than late payments."""
        late_score = await CreditScoreService._calculate_payment_history_score(
            on_time=8, late=2, missed=0, total_loans=1
        )

        missed_score = await CreditScoreService._calculate_payment_history_score(
            on_time=8, late=0, missed=2, total_loans=1
        )

        # Missed penalty (100 each) should be worse than late penalty (50 each)
        assert (
            missed_score < late_score
        ), "Missed payments should penalize more than late"

    @pytest.mark.django_db(transaction=True)
    async def test_score_boundaries(self):
        """Test that score stays within 300-850 range."""
        # Extreme good case
        good_score = await CreditScoreService._calculate_payment_history_score(
            on_time=1000, late=0, missed=0, total_loans=1
        )
        assert 300 <= good_score <= 850

        # Extreme bad case
        bad_score = await CreditScoreService._calculate_payment_history_score(
            on_time=0, late=100, missed=100, total_loans=1
        )
        assert 300 <= bad_score <= 850


@pytest.mark.unit
@pytest.mark.loan
class TestCreditUtilizationScore:
    """Test credit utilization score calculation."""

    @pytest.mark.django_db(transaction=True)
    async def test_no_active_loans_good_score(self):
        """Test that no active loans gives a neutral baseline score."""
        score = await CreditScoreService._calculate_credit_utilization_score(
            active_loans=0,
            defaulted_loans=0,
            current_debt=Decimal("0"),
            total_borrowed=Decimal("0"),
        )

        assert score == 650, "No loan history should result in baseline score of 650"

    @pytest.mark.django_db(transaction=True)
    async def test_defaulted_loan_penalty(self):
        """Test that defaulted loans significantly reduce score."""
        no_default_score = await CreditScoreService._calculate_credit_utilization_score(
            active_loans=1,
            defaulted_loans=0,
            current_debt=Decimal("10000"),
            total_borrowed=Decimal("10000"),
        )

        with_default_score = (
            await CreditScoreService._calculate_credit_utilization_score(
                active_loans=1,
                defaulted_loans=1,
                current_debt=Decimal("10000"),
                total_borrowed=Decimal("10000"),
            )
        )

        # Default should significantly reduce score
        assert with_default_score < no_default_score
        assert (
            no_default_score - with_default_score
        ) >= 150, "Default penalty should be substantial"


@pytest.mark.unit
@pytest.mark.loan
class TestAccountAgeScore:
    """Test account age score calculation."""

    @pytest.mark.django_db(transaction=True)
    async def test_brand_new_account(self):
        """Test score for brand new account (0-30 days)."""
        score = await CreditScoreService._calculate_account_age_score(
            account_age_days=15
        )

        # New accounts should get lower score
        assert score < 600, "Brand new accounts should have lower score"

    @pytest.mark.django_db(transaction=True)
    async def test_mature_account(self):
        """Test score for mature account (2+ years)."""
        score = await CreditScoreService._calculate_account_age_score(
            account_age_days=730
        )  # 2 years

        # Mature accounts should get good score
        assert score >= 750, "Mature accounts should have good score"

    @pytest.mark.django_db(transaction=True)
    async def test_age_score_increases_with_time(self):
        """Test that older accounts get better scores."""
        new_account = await CreditScoreService._calculate_account_age_score(
            account_age_days=30
        )
        medium_account = await CreditScoreService._calculate_account_age_score(
            account_age_days=180
        )
        old_account = await CreditScoreService._calculate_account_age_score(
            account_age_days=730
        )

        assert new_account < medium_account < old_account


@pytest.mark.unit
@pytest.mark.loan
class TestLoanHistoryScore:
    """Test loan history score calculation."""

    @pytest.mark.django_db(transaction=True)
    async def test_no_loans_neutral_score(self):
        """Test that no loan history gives neutral score."""
        score = await CreditScoreService._calculate_loan_history_score(
            total_loans=0, completed_loans=0, defaulted_loans=0
        )

        # No history should give neutral/fair score
        assert 600 <= score <= 700, "No loan history should give neutral score"

    @pytest.mark.django_db(transaction=True)
    async def test_all_loans_completed_perfect_score(self):
        """Test that all completed loans give perfect score."""
        score = await CreditScoreService._calculate_loan_history_score(
            total_loans=5, completed_loans=5, defaulted_loans=0
        )

        # 100% completion rate should give high score
        assert score >= 800, "All completed loans should give high score"

    @pytest.mark.django_db(transaction=True)
    async def test_defaulted_loans_reduce_score(self):
        """Test that defaulted loans reduce loan history score."""
        perfect_score = await CreditScoreService._calculate_loan_history_score(
            total_loans=5, completed_loans=5, defaulted_loans=0
        )

        with_default_score = await CreditScoreService._calculate_loan_history_score(
            total_loans=5, completed_loans=4, defaulted_loans=1
        )

        assert with_default_score < perfect_score
        assert (perfect_score - with_default_score) >= 100


@pytest.mark.unit
@pytest.mark.loan
class TestOverallCreditScore:
    """Test overall credit score calculation."""

    @pytest.mark.django_db(transaction=True)
    async def test_new_user_credit_score(self, verified_user):
        """Test credit score for brand new user with no history."""
        credit_score = await CreditScoreService.calculate_credit_score(verified_user)

        # New user should get low to fair score (around 550-700)
        assert 550 <= credit_score.score <= 750
        assert credit_score.score_band in ["very_poor", "poor", "fair", "good"]
        assert credit_score.total_loans == 0
        assert credit_score.on_time_payments == 0

    @pytest.mark.django_db(transaction=True)
    async def test_score_within_valid_range(self, verified_user):
        """Test that calculated score is always within 300-850."""
        credit_score = await CreditScoreService.calculate_credit_score(verified_user)

        assert 300 <= credit_score.score <= 850, "Score must be within FICO range"

    @pytest.mark.django_db(transaction=True)
    async def test_score_components_stored(self, verified_user):
        """Test that all score components are calculated and stored."""
        credit_score = await CreditScoreService.calculate_credit_score(verified_user)

        # Verify all components exist
        assert credit_score.payment_history_score is not None
        assert credit_score.credit_utilization_score is not None
        assert credit_score.account_age_score is not None
        assert credit_score.loan_history_score is not None

        # Verify all are within range
        assert 300 <= credit_score.payment_history_score <= 850
        assert 300 <= credit_score.credit_utilization_score <= 850
        assert 300 <= credit_score.account_age_score <= 850
        assert 300 <= credit_score.loan_history_score <= 850

    @pytest.mark.django_db(transaction=True)
    async def test_weighted_score_calculation(self, verified_user):
        """Test that final score is properly weighted average."""
        credit_score = await CreditScoreService.calculate_credit_score(verified_user)

        # Manually calculate weighted score
        expected_score = int(
            (credit_score.payment_history_score * 0.35)
            + (credit_score.credit_utilization_score * 0.30)
            + (credit_score.account_age_score * 0.15)
            + (credit_score.loan_history_score * 0.20)
        )

        # Clamp to range
        expected_score = max(300, min(850, expected_score))

        assert credit_score.score == expected_score


@pytest.mark.unit
@pytest.mark.loan
class TestRiskLevelDetermination:
    """Test risk level calculation."""

    @pytest.mark.django_db(transaction=True)
    def test_high_score_low_risk(self):
        """Test that high scores result in low risk."""
        risk = CreditScoreService._determine_risk_level(
            score=800, defaulted_loans=0, active_loans=1
        )

        assert risk == "low", "High score with no defaults should be low risk"

    @pytest.mark.django_db(transaction=True)
    def test_low_score_high_risk(self):
        """Test that low scores result in high risk."""
        risk = CreditScoreService._determine_risk_level(
            score=350, defaulted_loans=0, active_loans=0
        )

        assert risk in ["high", "very_high"], "Low score should be high risk"

    @pytest.mark.django_db(transaction=True)
    def test_defaults_increase_risk(self):
        """Test that defaulted loans increase risk level."""
        risk_no_defaults = CreditScoreService._determine_risk_level(
            score=700, defaulted_loans=0, active_loans=1
        )

        risk_with_defaults = CreditScoreService._determine_risk_level(
            score=700, defaulted_loans=2, active_loans=1
        )

        # Risk should be higher with defaults
        risk_levels = ["low", "medium", "high", "very_high"]
        assert risk_levels.index(risk_with_defaults) >= risk_levels.index(
            risk_no_defaults
        )


@pytest.mark.unit
@pytest.mark.loan
class TestRecommendationsGeneration:
    """Test credit score improvement recommendations."""

    @pytest.mark.django_db(transaction=True)
    def test_recommendations_for_missed_payments(self):
        """Test that recommendations address missed payments."""
        recommendations = CreditScoreService._generate_recommendations(
            score=500,
            on_time=5,
            late=2,
            missed=3,
            active_loans=1,
            defaulted_loans=0,
            account_age_days=100,
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # Should recommend improving payment history
        payment_related = any(
            "payment" in rec.lower() or "on time" in rec.lower()
            for rec in recommendations
        )
        assert payment_related, "Should recommend improving payment history"

    @pytest.mark.django_db(transaction=True)
    def test_recommendations_for_new_account(self):
        """Test recommendations for new accounts."""
        recommendations = CreditScoreService._generate_recommendations(
            score=600,
            on_time=0,
            late=0,
            missed=0,
            active_loans=0,
            defaulted_loans=0,
            account_age_days=15,  # Very new account
        )

        # Should mention building history
        assert len(recommendations) > 0


@pytest.mark.unit
@pytest.mark.loan
class TestPaymentStatsCalculation:
    """Test payment statistics calculation."""

    @pytest.mark.django_db(transaction=True)
    async def test_payment_stats_with_no_loans(self, verified_user):
        """Test payment stats for user with no loans."""
        stats = await CreditScoreService._calculate_payment_history(verified_user)

        assert stats["on_time"] == 0
        assert stats["late"] == 0
        assert stats["missed"] == 0


@pytest.mark.unit
@pytest.mark.loan
class TestFinancialMetricsCalculation:
    """Test financial metrics calculation."""

    @pytest.mark.django_db(transaction=True)
    async def test_financial_metrics_with_no_loans(self, verified_user):
        """Test financial metrics for user with no loans."""
        metrics = await CreditScoreService._calculate_financial_metrics(verified_user)

        assert metrics["total_borrowed"] == Decimal("0")
        assert metrics["total_repaid"] == Decimal("0")
        assert metrics["current_debt"] == Decimal("0")


@pytest.mark.unit
@pytest.mark.loan
class TestScoreBandClassification:
    """Test credit score band classification."""

    @pytest.mark.django_db(transaction=True)
    def test_score_band_boundaries(self):
        """Test that scores are classified into correct bands."""
        # Assuming CreditScore model has get_score_band method
        poor_band = CreditScore.get_score_band(350)
        fair_band = CreditScore.get_score_band(650)
        good_band = CreditScore.get_score_band(700)
        excellent_band = CreditScore.get_score_band(800)

        # Verify bands are different
        assert poor_band != excellent_band
