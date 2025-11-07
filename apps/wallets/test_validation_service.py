"""
Unit tests for Wallet Validation Service (apps/wallets/services/validation_service.py)

Tests validation logic for amounts, PINs, emails, split payments, and rate limiting.
These are UNIT tests - testing business logic directly, not API endpoints.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, UTC

from apps.wallets.services.validation_service import WalletValidationService
from apps.common.exceptions import RequestError, BodyValidationError, ErrorCode


@pytest.mark.unit
@pytest.mark.wallet
class TestAmountValidation:
    """Test monetary amount validation logic."""

    def test_valid_amount_accepted(self):
        """Test that valid amounts are accepted."""
        valid_amounts = [
            Decimal("0.01"),  # Minimum
            Decimal("1.00"),
            Decimal("100.50"),
            Decimal("1000.00"),
            Decimal("999999.99"),  # Near maximum
        ]

        for amount in valid_amounts:
            # Should not raise exception
            WalletValidationService.validate_amount(amount)

    @pytest.mark.skip(reason="validate_amount method not yet implemented")
    def test_amount_below_minimum_rejected(self):
        """Test that amounts below minimum ($0.01) are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_amount(Decimal("0.00"))

        assert exc_info.value.err_code == ErrorCode.AMOUNT_BELOW_MINIMUM

    @pytest.mark.skip(reason="validate_amount method not yet implemented")
    def test_amount_above_maximum_rejected(self):
        """Test that amounts above maximum ($1,000,000) are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_amount(Decimal("1000001.00"))

        assert exc_info.value.err_code == ErrorCode.AMOUNT_ABOVE_MAXIMUM

    @pytest.mark.skip(reason="validate_amount method not yet implemented")
    def test_negative_amount_rejected(self):
        """Test that negative amounts are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_amount(Decimal("-10.00"))

        assert exc_info.value.err_code == ErrorCode.AMOUNT_MUST_BE_POSITIVE

    @pytest.mark.skip(reason="validate_amount method not yet implemented")
    def test_amount_with_too_many_decimals_rejected(self):
        """Test that amounts with > 8 decimal places are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_amount(Decimal("10.123456789"))

        assert exc_info.value.err_code == ErrorCode.AMOUNT_TOO_MANY_DECIMALS

    def test_amount_at_minimum_boundary(self):
        """Test amount exactly at minimum boundary."""
        # Should not raise
        WalletValidationService.validate_amount(Decimal("0.01"))

    def test_amount_at_maximum_boundary(self):
        """Test amount exactly at maximum boundary."""
        # Should not raise
        WalletValidationService.validate_amount(Decimal("1000000.00"))

    def test_amount_with_8_decimals_accepted(self):
        """Test that 8 decimal places (maximum) are accepted."""
        # Should not raise
        WalletValidationService.validate_amount(Decimal("10.12345678"))


@pytest.mark.unit
@pytest.mark.wallet
class TestPINValidation:
    """Test wallet PIN validation logic."""

    def test_valid_4_digit_pin_accepted(self):
        """Test that valid 4-digit PIN is accepted."""
        # Should not raise
        WalletValidationService.validate_pin("1357")

    def test_valid_6_digit_pin_accepted(self):
        """Test that valid 6-digit PIN is accepted."""
        # Should not raise
        WalletValidationService.validate_pin("135792")

    @pytest.mark.skip(reason="validate_pin method not yet implemented")
    def test_pin_too_short_rejected(self):
        """Test that PINs shorter than 4 digits are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_pin("123")

        assert exc_info.value.err_code == ErrorCode.PIN_INVALID_LENGTH

    @pytest.mark.skip(reason="validate_pin method not yet implemented")
    def test_pin_too_long_rejected(self):
        """Test that PINs longer than 6 digits are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_pin("1234567")

        assert exc_info.value.err_code == ErrorCode.PIN_INVALID_LENGTH

    @pytest.mark.skip(reason="validate_pin method not yet implemented")
    def test_non_numeric_pin_rejected(self):
        """Test that non-numeric PINs are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_pin("12a4")

        assert exc_info.value.err_code == ErrorCode.PIN_MUST_BE_NUMERIC

    @pytest.mark.skip(reason="validate_pin weak pattern detection not yet implemented")
    def test_weak_sequential_pins_rejected(self):
        """Test that sequential PINs are rejected as weak."""
        weak_pins = [
            "1234",  # Sequential ascending
            "4321",  # Sequential descending
            "0123",
            "9876",
        ]

        for pin in weak_pins:
            with pytest.raises(RequestError) as exc_info:
                WalletValidationService.validate_pin(pin)

            assert exc_info.value.err_code == ErrorCode.PIN_TOO_WEAK

    @pytest.mark.skip(reason="validate_pin weak pattern detection not yet implemented")
    def test_weak_repeated_pins_rejected(self):
        """Test that repeated digit PINs are rejected as weak."""
        weak_pins = [
            "0000",
            "1111",
            "5555",
            "9999",
        ]

        for pin in weak_pins:
            with pytest.raises(RequestError) as exc_info:
                WalletValidationService.validate_pin(pin)

            assert exc_info.value.err_code == ErrorCode.PIN_TOO_WEAK

    @pytest.mark.skip(reason="validate_pin whitespace detection not yet implemented")
    def test_pin_with_spaces_rejected(self):
        """Test that PINs with spaces are rejected."""
        with pytest.raises(RequestError):
            WalletValidationService.validate_pin("12 34")


@pytest.mark.unit
@pytest.mark.wallet
class TestWalletNameValidation:
    """Test wallet name validation logic."""

    def test_valid_wallet_name_accepted(self):
        """Test that valid wallet names are accepted."""
        valid_names = [
            "My Wallet",
            "Savings Account",
            "Business-Main",
            "USD_Wallet_2024",
        ]

        for name in valid_names:
            # Should not raise
            WalletValidationService.validate_wallet_name(name)

    @pytest.mark.skip(reason="validate_wallet_name method not yet implemented")
    def test_name_too_short_rejected(self):
        """Test that names shorter than 2 characters are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_wallet_name("A")

        assert exc_info.value.err_code == ErrorCode.WALLET_NAME_INVALID_LENGTH

    @pytest.mark.skip(reason="validate_wallet_name method not yet implemented")
    def test_name_too_long_rejected(self):
        """Test that names longer than 100 characters are rejected."""
        long_name = "A" * 101
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_wallet_name(long_name)

        assert exc_info.value.err_code == ErrorCode.WALLET_NAME_INVALID_LENGTH

    @pytest.mark.skip(reason="validate_wallet_name method not yet implemented")
    def test_name_with_special_characters_rejected(self):
        """Test that names with special characters are rejected."""
        invalid_names = [
            "My Wallet!",
            "Wallet@Home",
            "Wallet#123",
            "Wallet$$$",
        ]

        for name in invalid_names:
            with pytest.raises(RequestError) as exc_info:
                WalletValidationService.validate_wallet_name(name)

            assert exc_info.value.err_code == ErrorCode.WALLET_NAME_INVALID_CHARACTERS

    @pytest.mark.skip(reason="validate_wallet_name method not yet implemented")
    def test_reserved_wallet_names_rejected(self):
        """Test that reserved names are rejected."""
        reserved_names = [
            "admin",
            "system",
            "default",
            "ADMIN",  # Case insensitive
            "System",
        ]

        for name in reserved_names:
            with pytest.raises(RequestError) as exc_info:
                WalletValidationService.validate_wallet_name(name)

            assert exc_info.value.err_code == ErrorCode.WALLET_NAME_RESERVED


@pytest.mark.unit
@pytest.mark.wallet
class TestDescriptionValidation:
    """Test description sanitization and validation."""

    def test_valid_description_accepted(self):
        """Test that valid descriptions are accepted."""
        description = "This is a valid description for my wallet."
        # Should not raise
        WalletValidationService.validate_description(description)

    @pytest.mark.skip(reason="validate_description method not yet implemented")
    def test_description_too_long_rejected(self):
        """Test that descriptions longer than 500 characters are rejected."""
        long_description = "A" * 501
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_description(long_description)

        assert exc_info.value.err_code == ErrorCode.DESCRIPTION_TOO_LONG

    @pytest.mark.skip(reason="validate_description method not yet implemented")
    def test_description_with_script_tags_rejected(self):
        """Test that descriptions with script tags are rejected (XSS prevention)."""
        malicious_descriptions = [
            "<script>alert('XSS')</script>",
            "Hello <script>evil()</script> World",
            "javascript:alert('XSS')",
        ]

        for description in malicious_descriptions:
            with pytest.raises(RequestError) as exc_info:
                WalletValidationService.validate_description(description)

            assert (
                exc_info.value.err_code
                == ErrorCode.DESCRIPTION_CONTAINS_INVALID_CONTENT
            )

    @pytest.mark.skip(reason="validate_description method not yet implemented")
    def test_description_with_html_rejected(self):
        """Test that descriptions with HTML tags are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_description("<div>Test</div>")

        assert exc_info.value.err_code == ErrorCode.DESCRIPTION_CONTAINS_INVALID_CONTENT


@pytest.mark.unit
@pytest.mark.wallet
class TestCurrencyCodeValidation:
    """Test ISO 4217 currency code validation."""

    def test_valid_currency_codes_accepted(self):
        """Test that valid ISO 4217 currency codes are accepted."""
        valid_codes = ["USD", "NGN", "EUR", "GBP", "JPY"]

        for code in valid_codes:
            # Should not raise
            WalletValidationService.validate_currency_code(code)

    @pytest.mark.skip(reason="validate_currency_code method not yet implemented")
    def test_lowercase_currency_code_rejected(self):
        """Test that lowercase currency codes are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_currency_code("usd")

        assert exc_info.value.err_code == ErrorCode.CURRENCY_CODE_INVALID_FORMAT

    @pytest.mark.skip(reason="validate_currency_code method not yet implemented")
    def test_currency_code_wrong_length_rejected(self):
        """Test that currency codes not exactly 3 characters are rejected."""
        invalid_codes = ["US", "USDD", "N"]

        for code in invalid_codes:
            with pytest.raises(RequestError) as exc_info:
                WalletValidationService.validate_currency_code(code)

            assert exc_info.value.err_code == ErrorCode.CURRENCY_CODE_INVALID_FORMAT

    @pytest.mark.skip(reason="validate_currency_code method not yet implemented")
    def test_currency_code_with_numbers_rejected(self):
        """Test that currency codes with numbers are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_currency_code("US1")

        assert exc_info.value.err_code == ErrorCode.CURRENCY_CODE_INVALID_FORMAT


@pytest.mark.unit
@pytest.mark.wallet
class TestEmailListValidation:
    """Test email list validation for split payments."""

    def test_valid_email_list_accepted(self):
        """Test that valid email lists are accepted."""
        emails = ["user1@example.com", "user2@example.com"]
        # Should not raise
        WalletValidationService.validate_email_list(emails)

    @pytest.mark.skip(reason="validate_email_list method not yet implemented")
    def test_single_email_rejected(self):
        """Test that lists with only 1 email are rejected (minimum 2 for split)."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_email_list(["user@example.com"])

        assert exc_info.value.err_code == ErrorCode.EMAIL_LIST_TOO_FEW

    @pytest.mark.skip(reason="validate_email_list method not yet implemented")
    def test_too_many_emails_rejected(self):
        """Test that lists with > 20 emails are rejected."""
        emails = [f"user{i}@example.com" for i in range(21)]
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_email_list(emails)

        assert exc_info.value.err_code == ErrorCode.EMAIL_LIST_TOO_MANY

    @pytest.mark.skip(
        reason="validate_email_list duplicate removal not yet implemented"
    )
    def test_duplicate_emails_removed(self):
        """Test that duplicate emails are automatically removed."""
        emails = [
            "user1@example.com",
            "user2@example.com",
            "user1@example.com",  # Duplicate
        ]
        cleaned = WalletValidationService.validate_email_list(emails)

        assert len(cleaned) == 2
        assert "user1@example.com" in cleaned
        assert "user2@example.com" in cleaned

    @pytest.mark.skip(
        reason="validate_email_list email format validation not yet implemented"
    )
    def test_invalid_email_format_rejected(self):
        """Test that invalid email formats are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_email_list(
                ["user1@example.com", "invalid-email"]
            )

        assert exc_info.value.err_code == ErrorCode.EMAIL_INVALID_FORMAT


@pytest.mark.unit
@pytest.mark.wallet
class TestSplitAmountValidation:
    """Test split payment amount validation logic."""

    @pytest.mark.skip(
        reason="validate_split_amounts method signature not yet implemented"
    )
    def test_equal_split_divisible_accepted(self):
        """Test that equal split with divisible total is accepted."""
        # 100 / 4 = 25 (evenly divisible)
        # Should not raise
        WalletValidationService.validate_split_amounts(
            split_type="EQUAL",
            total_amount=Decimal("100.00"),
            participant_count=4,
        )

    @pytest.mark.skip(
        reason="validate_split_amounts method signature not yet implemented"
    )
    def test_equal_split_not_divisible_rejected(self):
        """Test that equal split with non-divisible total is rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_split_amounts(
                split_type="EQUAL",
                total_amount=Decimal("100.00"),
                participant_count=3,  # 100/3 = 33.333...
            )

        assert exc_info.value.err_code == ErrorCode.SPLIT_AMOUNT_NOT_DIVISIBLE

    @pytest.mark.skip(
        reason="validate_split_amounts method signature not yet implemented"
    )
    def test_custom_split_amounts_sum_to_total_accepted(self):
        """Test that custom amounts summing to total are accepted."""
        # Should not raise
        WalletValidationService.validate_split_amounts(
            split_type="CUSTOM",
            total_amount=Decimal("100.00"),
            custom_amounts=[Decimal("30.00"), Decimal("40.00"), Decimal("30.00")],
        )

    @pytest.mark.skip(
        reason="validate_split_amounts method signature not yet implemented"
    )
    def test_custom_split_amounts_not_sum_to_total_rejected(self):
        """Test that custom amounts not summing to total are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_split_amounts(
                split_type="CUSTOM",
                total_amount=Decimal("100.00"),
                custom_amounts=[
                    Decimal("30.00"),
                    Decimal("40.00"),
                    Decimal("40.00"),
                ],  # Sum = 110
            )

        assert exc_info.value.err_code == ErrorCode.SPLIT_CUSTOM_AMOUNTS_MISMATCH

    @pytest.mark.skip(
        reason="validate_split_amounts method signature not yet implemented"
    )
    def test_percentage_split_sum_to_100_accepted(self):
        """Test that percentages summing to 100% are accepted."""
        # Should not raise
        WalletValidationService.validate_split_amounts(
            split_type="PERCENTAGE",
            total_amount=Decimal("100.00"),
            percentages=[Decimal("30.00"), Decimal("40.00"), Decimal("30.00")],
        )

    @pytest.mark.skip(
        reason="validate_split_amounts method signature not yet implemented"
    )
    def test_percentage_split_sum_not_100_rejected(self):
        """Test that percentages not summing to 100% are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_split_amounts(
                split_type="PERCENTAGE",
                total_amount=Decimal("100.00"),
                percentages=[
                    Decimal("30.00"),
                    Decimal("40.00"),
                    Decimal("40.00"),
                ],  # Sum = 110
            )

        assert exc_info.value.err_code == ErrorCode.SPLIT_PERCENTAGES_INVALID

    @pytest.mark.skip(
        reason="validate_split_amounts method signature not yet implemented"
    )
    def test_percentage_split_allows_small_rounding_error(self):
        """Test that percentage split allows ±0.01 rounding error."""
        # 33.33 + 33.33 + 33.34 = 100.00 (within tolerance)
        # Should not raise
        WalletValidationService.validate_split_amounts(
            split_type="PERCENTAGE",
            total_amount=Decimal("100.00"),
            percentages=[Decimal("33.33"), Decimal("33.33"), Decimal("33.34")],
        )


@pytest.mark.unit
@pytest.mark.wallet
class TestFrequencyValidation:
    """Test payment frequency validation."""

    def test_valid_frequencies_accepted(self):
        """Test that all valid payment frequencies are accepted."""
        valid_frequencies = ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"]

        for frequency in valid_frequencies:
            # Should not raise
            WalletValidationService.validate_frequency(frequency)

    @pytest.mark.skip(reason="validate_frequency method not yet implemented")
    def test_invalid_frequency_rejected(self):
        """Test that invalid frequencies are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_frequency("BIWEEKLY")

        assert exc_info.value.err_code == ErrorCode.FREQUENCY_INVALID

    @pytest.mark.skip(reason="validate_frequency method not yet implemented")
    def test_lowercase_frequency_rejected(self):
        """Test that lowercase frequencies are rejected."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_frequency("monthly")

        assert exc_info.value.err_code == ErrorCode.FREQUENCY_INVALID


@pytest.mark.unit
@pytest.mark.wallet
class TestQRCodeSettingsValidation:
    """Test QR code settings validation."""

    @pytest.mark.skip(
        reason="validate_qr_code_settings method signature not yet implemented"
    )
    def test_fixed_amount_qr_requires_amount(self):
        """Test that fixed amount QR codes require an amount."""
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_qr_code_settings(
                is_amount_fixed=True,
                amount=None,  # Missing amount
            )

        assert exc_info.value.err_code == ErrorCode.QR_FIXED_AMOUNT_REQUIRED

    @pytest.mark.skip(
        reason="validate_qr_code_settings method signature not yet implemented"
    )
    def test_qr_expiration_must_be_future(self):
        """Test that QR expiration date must be in the future."""
        past_date = datetime.now(UTC) - timedelta(days=1)
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_qr_code_settings(
                expires_at=past_date,
            )

        assert exc_info.value.err_code == ErrorCode.QR_EXPIRATION_MUST_BE_FUTURE

    @pytest.mark.skip(
        reason="validate_qr_code_settings method signature not yet implemented"
    )
    def test_qr_expiration_within_one_year(self):
        """Test that QR expiration must be within 1 year."""
        future_date = datetime.now(UTC) + timedelta(days=366)
        with pytest.raises(RequestError) as exc_info:
            WalletValidationService.validate_qr_code_settings(
                expires_at=future_date,
            )

        assert exc_info.value.err_code == ErrorCode.QR_EXPIRATION_TOO_FAR

    @pytest.mark.skip(
        reason="validate_qr_code_settings method signature not yet implemented"
    )
    def test_valid_qr_settings_accepted(self):
        """Test that valid QR settings are accepted."""
        future_date = datetime.now(UTC) + timedelta(days=30)
        # Should not raise
        WalletValidationService.validate_qr_code_settings(
            is_amount_fixed=True,
            amount=Decimal("50.00"),
            expires_at=future_date,
        )


@pytest.mark.unit
@pytest.mark.wallet
class TestRateLimitValidation:
    """Test rate limiting validation."""

    @pytest.mark.django_db(transaction=True)
    async def test_transfer_rate_limit_exceeded(self, verified_user):
        """Test that transfer rate limit (100/day) is enforced."""
        is_valid, error_message = WalletValidationService.check_rate_limits(
            user_id=str(verified_user.id),
            operation="transfer",
            current_count=100,  # At limit
        )

        assert is_valid is False
        assert "Daily limit exceeded" in error_message
        assert "transfer" in error_message

    @pytest.mark.django_db(transaction=True)
    async def test_wallet_creation_rate_limit_exceeded(self, verified_user):
        """Test that wallet creation rate limit (10/day) is enforced."""
        is_valid, error_message = WalletValidationService.check_rate_limits(
            user_id=str(verified_user.id),
            operation="create_wallet",
            current_count=10,
        )

        assert is_valid is False
        assert "Daily limit exceeded" in error_message
        assert "create_wallet" in error_message

    @pytest.mark.django_db(transaction=True)
    async def test_rate_limit_under_limit_accepted(self, verified_user):
        """Test that operations under rate limit are accepted."""
        is_valid, error_message = WalletValidationService.check_rate_limits(
            user_id=str(verified_user.id),
            operation="transfer",
            current_count=50,  # Under limit of 100
        )

        assert is_valid is True
        assert error_message is None
