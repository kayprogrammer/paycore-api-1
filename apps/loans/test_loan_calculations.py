"""
Unit tests for Loan Calculation Logic (apps/loans/services/loan_manager.py)

Tests interest calculations, fees, installments, and repayment schedules.
These are UNIT tests - testing business logic directly, not API endpoints.
"""

import pytest
from decimal import Decimal

from apps.loans.services.loan_manager import LoanManager
from apps.loans.models import RepaymentFrequency
from apps.common.exceptions import RequestError, BodyValidationError, ErrorCode


@pytest.mark.unit
@pytest.mark.loan
class TestLoanAmountValidation:
    """Test loan amount validation logic."""

    @pytest.mark.django_db(transaction=True)
    async def test_amount_below_minimum_rejected(self, loan_product):
        """Test that amounts below minimum are rejected."""
        with pytest.raises(RequestError) as exc_info:
            await LoanManager.calculate_loan(
                product=loan_product,
                amount=Decimal("1000"),  # Below min (10000)
                tenure_months=6,
                repayment_frequency=RepaymentFrequency.MONTHLY,
            )

        assert exc_info.value.err_code == ErrorCode.LOAN_AMOUNT_BELOW_MIN

    @pytest.mark.django_db(transaction=True)
    async def test_amount_above_maximum_rejected(self, loan_product):
        """Test that amounts above maximum are rejected."""
        with pytest.raises(RequestError) as exc_info:
            await LoanManager.calculate_loan(
                product=loan_product,
                amount=Decimal("1000000"),  # Above max (500000)
                tenure_months=6,
                repayment_frequency=RepaymentFrequency.MONTHLY,
            )

        assert exc_info.value.err_code == ErrorCode.LOAN_AMOUNT_ABOVE_MAX

    @pytest.mark.django_db(transaction=True)
    async def test_amount_at_minimum_accepted(self, loan_product):
        """Test that amount exactly at minimum is accepted."""
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=loan_product.min_amount,  # Exactly at min
            tenure_months=6,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        assert result is not None
        assert result["requested_amount"] == loan_product.min_amount

    @pytest.mark.django_db(transaction=True)
    async def test_amount_at_maximum_accepted(self, loan_product):
        """Test that amount exactly at maximum is accepted."""
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=loan_product.max_amount,  # Exactly at max
            tenure_months=6,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        assert result is not None
        assert result["requested_amount"] == loan_product.max_amount


@pytest.mark.unit
@pytest.mark.loan
class TestLoanTenureValidation:
    """Test loan tenure validation logic."""

    @pytest.mark.django_db(transaction=True)
    async def test_tenure_below_minimum_rejected(self, loan_product):
        """Test that tenure below minimum is rejected."""
        with pytest.raises(RequestError) as exc_info:
            await LoanManager.calculate_loan(
                product=loan_product,
                amount=Decimal("50000"),
                tenure_months=1,  # Below min (3)
                repayment_frequency=RepaymentFrequency.MONTHLY,
            )

        assert exc_info.value.err_code == ErrorCode.LOAN_TENURE_INVALID

    @pytest.mark.django_db(transaction=True)
    async def test_tenure_above_maximum_rejected(self, loan_product):
        """Test that tenure above maximum is rejected."""
        with pytest.raises(RequestError) as exc_info:
            await LoanManager.calculate_loan(
                product=loan_product,
                amount=Decimal("50000"),
                tenure_months=24,  # Above max (12)
                repayment_frequency=RepaymentFrequency.MONTHLY,
            )

        assert exc_info.value.err_code == ErrorCode.LOAN_TENURE_INVALID

    @pytest.mark.django_db(transaction=True)
    async def test_tenure_within_range_accepted(self, loan_product):
        """Test that tenure within range is accepted."""
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=Decimal("50000"),
            tenure_months=6,  # Within range (3-12)
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        assert result is not None
        assert result["tenure_months"] == 6


@pytest.mark.unit
@pytest.mark.loan
class TestInterestCalculation:
    """Test interest calculation logic."""

    @pytest.mark.django_db(transaction=True)
    async def test_simple_interest_formula(self, loan_product):
        """Test that simple interest is calculated correctly.

        Formula: Total Interest = Principal × Rate × Time / 12
        """
        amount = Decimal("100000")
        rate = loan_product.min_interest_rate  # 15%
        tenure = 12  # months

        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=amount,
            tenure_months=tenure,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        # Calculate expected interest
        # Annual interest = 100000 * 0.15 = 15000
        # Total interest for 12 months = (15000 * 12) / 12 = 15000
        expected_annual_interest = amount * (rate / Decimal("100"))
        expected_total_interest = (expected_annual_interest * tenure) / Decimal("12")

        assert result["total_interest"] == expected_total_interest

    @pytest.mark.django_db(transaction=True)
    async def test_interest_for_6_months(self, loan_product):
        """Test interest calculation for 6-month loan."""
        amount = Decimal("100000")
        rate = Decimal("15")  # 15% annual
        tenure = 6

        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=amount,
            tenure_months=tenure,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        # Expected: (100000 * 0.15 * 6) / 12 = 7500
        expected_interest = Decimal("7500")

        assert result["total_interest"] == expected_interest

    @pytest.mark.django_db(transaction=True)
    async def test_interest_for_3_months(self, loan_product):
        """Test interest calculation for 3-month loan."""
        amount = Decimal("50000")
        rate = Decimal("15")
        tenure = 3

        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=amount,
            tenure_months=tenure,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        # Expected: (50000 * 0.15 * 3) / 12 = 1875
        expected_interest = Decimal("1875")

        assert result["total_interest"] == expected_interest


@pytest.mark.unit
@pytest.mark.loan
class TestProcessingFeeCalculation:
    """Test processing fee calculation logic."""

    @pytest.mark.django_db(transaction=True)
    async def test_processing_fee_percentage_vs_fixed(self, loan_product):
        """Test that processing fee uses max of percentage or fixed amount."""
        # Loan product has: 2% percentage, 500 fixed
        # For 100000: 2% = 2000 (higher than 500, so use 2000)
        large_amount = Decimal("100000")
        result_large = await LoanManager.calculate_loan(
            product=loan_product,
            amount=large_amount,
            tenure_months=6,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        expected_percentage_fee = large_amount * Decimal("2") / Decimal("100")  # 2000
        expected_fixed_fee = Decimal("500")
        expected_fee = max(expected_percentage_fee, expected_fixed_fee)

        assert result_large["processing_fee"] == expected_fee

    @pytest.mark.django_db(transaction=True)
    async def test_processing_fee_fixed_minimum(self, loan_product):
        """Test that fixed fee is used when percentage is less."""
        # For small amount, fixed fee should be used
        small_amount = Decimal("10000")  # Min amount
        result_small = await LoanManager.calculate_loan(
            product=loan_product,
            amount=small_amount,
            tenure_months=6,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        # 2% of 10000 = 200 (less than fixed 500)
        expected_fee = Decimal("500")  # Should use fixed

        assert result_small["processing_fee"] == expected_fee


@pytest.mark.unit
@pytest.mark.loan
class TestTotalRepayableCalculation:
    """Test total repayable amount calculation."""

    @pytest.mark.django_db(transaction=True)
    async def test_total_repayable_equals_principal_plus_interest(self, loan_product):
        """Test that total repayable = principal + interest."""
        amount = Decimal("100000")
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=amount,
            tenure_months=12,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        expected_total = amount + result["total_interest"]

        assert result["total_repayable"] == expected_total

    @pytest.mark.django_db(transaction=True)
    async def test_processing_fee_not_included_in_repayable(self, loan_product):
        """Test that processing fee is separate from total repayable."""
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=Decimal("100000"),
            tenure_months=6,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        # Total repayable should NOT include processing fee
        # It's only principal + interest
        assert (
            result["total_repayable"]
            == result["requested_amount"] + result["total_interest"]
        )


@pytest.mark.unit
@pytest.mark.loan
class TestInstallmentCalculation:
    """Test installment number and amount calculations."""

    @pytest.mark.django_db(transaction=True)
    def test_monthly_repayment_installments(self, loan_product):
        """Test installment calculation for monthly frequency."""
        tenure = 6
        frequency = RepaymentFrequency.MONTHLY

        installments = LoanManager._calculate_installments(tenure, frequency)

        assert installments == 6  # 6 months = 6 monthly installments

    @pytest.mark.django_db(transaction=True)
    def test_weekly_repayment_installments(self, loan_product):
        """Test installment calculation for weekly frequency."""
        tenure = 6
        frequency = RepaymentFrequency.WEEKLY

        installments = LoanManager._calculate_installments(tenure, frequency)

        # 6 months * 4 weeks = 24 installments
        assert installments == 24

    @pytest.mark.django_db(transaction=True)
    def test_biweekly_repayment_installments(self, loan_product):
        """Test installment calculation for bi-weekly frequency."""
        tenure = 6
        frequency = RepaymentFrequency.BIWEEKLY

        installments = LoanManager._calculate_installments(tenure, frequency)

        # 6 months * 2 = 12 installments
        assert installments == 12

    @pytest.mark.django_db(transaction=True)
    def test_quarterly_repayment_installments(self, loan_product):
        """Test installment calculation for quarterly frequency."""
        tenure = 12
        frequency = RepaymentFrequency.QUARTERLY

        installments = LoanManager._calculate_installments(tenure, frequency)

        # 12 months / 3 = 4 installments
        assert installments == 4

    @pytest.mark.django_db(transaction=True)
    def test_daily_repayment_installments(self, loan_product):
        """Test installment calculation for daily frequency."""
        tenure = 1
        frequency = RepaymentFrequency.DAILY

        installments = LoanManager._calculate_installments(tenure, frequency)

        # 1 month * 30 days = 30 installments
        assert installments == 30

    @pytest.mark.django_db(transaction=True)
    async def test_installment_amount_calculation(self, loan_product):
        """Test that installment amount = total repayable / number of installments."""
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=Decimal("120000"),
            tenure_months=12,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        expected_installment = (
            result["total_repayable"] / result["number_of_installments"]
        )

        assert result["installment_amount"] == expected_installment

    @pytest.mark.django_db(transaction=True)
    async def test_monthly_repayment_amount(self, loan_product):
        """Test monthly repayment calculation."""
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=Decimal("120000"),
            tenure_months=12,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        expected_monthly = result["total_repayable"] / Decimal("12")

        assert result["monthly_repayment"] == expected_monthly


@pytest.mark.unit
@pytest.mark.loan
class TestLoanCalculationEdgeCases:
    """Test edge cases in loan calculations."""

    @pytest.mark.django_db(transaction=True)
    async def test_minimum_loan_minimum_tenure(self, loan_product):
        """Test calculation for minimum possible loan."""
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=loan_product.min_amount,
            tenure_months=loan_product.min_tenure_months,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        assert result is not None
        assert result["requested_amount"] == loan_product.min_amount
        assert result["tenure_months"] == loan_product.min_tenure_months

    @pytest.mark.django_db(transaction=True)
    async def test_maximum_loan_maximum_tenure(self, loan_product):
        """Test calculation for maximum possible loan."""
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=loan_product.max_amount,
            tenure_months=loan_product.max_tenure_months,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        assert result is not None
        assert result["requested_amount"] == loan_product.max_amount
        assert result["tenure_months"] == loan_product.max_tenure_months

    @pytest.mark.django_db(transaction=True)
    async def test_decimal_precision_maintained(self, loan_product):
        """Test that decimal precision is maintained in calculations."""
        result = await LoanManager.calculate_loan(
            product=loan_product,
            amount=Decimal("123456.78"),
            tenure_months=6,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        # Verify all amounts are Decimal type (not float)
        assert isinstance(result["requested_amount"], Decimal)
        assert isinstance(result["total_interest"], Decimal)
        assert isinstance(result["total_repayable"], Decimal)
        assert isinstance(result["processing_fee"], Decimal)
        assert isinstance(result["installment_amount"], Decimal)


@pytest.mark.unit
@pytest.mark.loan
class TestRepaymentFrequencyValidation:
    """Test repayment frequency validation."""

    @pytest.mark.django_db(transaction=True)
    async def test_invalid_frequency_rejected(self, loan_product):
        """Test that invalid repayment frequency is rejected."""
        with pytest.raises(BodyValidationError):
            await LoanManager.calculate_loan(
                product=loan_product,
                amount=Decimal("50000"),
                tenure_months=6,
                repayment_frequency="INVALID_FREQUENCY",
            )


@pytest.mark.unit
@pytest.mark.loan
class TestLoanCalculationConsistency:
    """Test consistency of loan calculations."""

    @pytest.mark.django_db(transaction=True)
    async def test_same_inputs_same_outputs(self, loan_product):
        """Test that same inputs produce same outputs."""
        params = {
            "product": loan_product,
            "amount": Decimal("100000"),
            "tenure_months": 6,
            "repayment_frequency": RepaymentFrequency.MONTHLY,
        }

        result1 = await LoanManager.calculate_loan(**params)
        result2 = await LoanManager.calculate_loan(**params)

        assert result1["total_interest"] == result2["total_interest"]
        assert result1["processing_fee"] == result2["processing_fee"]
        assert result1["total_repayable"] == result2["total_repayable"]
        assert result1["installment_amount"] == result2["installment_amount"]

    @pytest.mark.django_db(transaction=True)
    async def test_doubling_amount_doubles_interest(self, loan_product):
        """Test that doubling amount (approximately) doubles interest."""
        amount1 = Decimal("50000")
        amount2 = Decimal("100000")

        result1 = await LoanManager.calculate_loan(
            product=loan_product,
            amount=amount1,
            tenure_months=6,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        result2 = await LoanManager.calculate_loan(
            product=loan_product,
            amount=amount2,
            tenure_months=6,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        # Interest should be proportional to principal
        ratio = result2["total_interest"] / result1["total_interest"]
        expected_ratio = amount2 / amount1

        assert abs(ratio - expected_ratio) < Decimal(
            "0.01"
        )  # Allow small rounding difference

    @pytest.mark.django_db(transaction=True)
    async def test_doubling_tenure_doubles_interest(self, loan_product):
        """Test that doubling tenure (approximately) doubles interest."""
        tenure1 = 6
        tenure2 = 12

        result1 = await LoanManager.calculate_loan(
            product=loan_product,
            amount=Decimal("100000"),
            tenure_months=tenure1,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        result2 = await LoanManager.calculate_loan(
            product=loan_product,
            amount=Decimal("100000"),
            tenure_months=tenure2,
            repayment_frequency=RepaymentFrequency.MONTHLY,
        )

        # Interest should be proportional to time
        ratio = result2["total_interest"] / result1["total_interest"]
        expected_ratio = Decimal(tenure2) / Decimal(tenure1)

        assert abs(ratio - expected_ratio) < Decimal("0.01")
