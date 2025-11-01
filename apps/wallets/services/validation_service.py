from decimal import Decimal
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from typing import List, Dict, Any, Optional, Tuple
import re, uuid


class WalletValidationService:
    """Service for comprehensive wallet validation and error handling"""

    # Validation constants
    MIN_WALLET_NAME_LENGTH = 2
    MAX_WALLET_NAME_LENGTH = 100
    MIN_DESCRIPTION_LENGTH = 0
    MAX_DESCRIPTION_LENGTH = 500
    MIN_TRANSFER_AMOUNT = Decimal("0.01")
    MAX_TRANSFER_AMOUNT = Decimal("1000000.00")
    MIN_PIN_LENGTH = 4
    MAX_PIN_LENGTH = 6
    MAX_DAILY_TRANSFERS = 100
    MAX_PARTICIPANTS_SPLIT = 20
    MIN_PARTICIPANTS_SPLIT = 2

    @staticmethod
    def validate_wallet_name(name: str) -> Tuple[bool, Optional[str]]:
        """Validate wallet name"""

        if not name or not name.strip():
            return False, "Wallet name is required"

        name = name.strip()

        if len(name) < WalletValidationService.MIN_WALLET_NAME_LENGTH:
            return (
                False,
                f"Wallet name must be at least {WalletValidationService.MIN_WALLET_NAME_LENGTH} characters",
            )

        if len(name) > WalletValidationService.MAX_WALLET_NAME_LENGTH:
            return (
                False,
                f"Wallet name cannot exceed {WalletValidationService.MAX_WALLET_NAME_LENGTH} characters",
            )

        # Check for invalid characters
        if not re.match(r"^[a-zA-Z0-9\s\-_.,()]+$", name):
            return False, "Wallet name contains invalid characters"

        # Check for common reserved names
        reserved_names = ["admin", "system", "test", "null", "undefined"]
        if name.lower() in reserved_names:
            return False, "This wallet name is reserved"

        return True, None

    @staticmethod
    def validate_description(description: str) -> Tuple[bool, Optional[str]]:
        """Validate description field"""

        if description is None:
            return True, None

        if len(description) > WalletValidationService.MAX_DESCRIPTION_LENGTH:
            return (
                False,
                f"Description cannot exceed {WalletValidationService.MAX_DESCRIPTION_LENGTH} characters",
            )

        # Check for potentially harmful content
        dangerous_patterns = ["<script", "javascript:", "data:", "vbscript:"]
        description_lower = description.lower()
        for pattern in dangerous_patterns:
            if pattern in description_lower:
                return False, "Description contains potentially harmful content"

        return True, None

    @staticmethod
    def validate_amount(
        amount: Decimal, context: str = "transaction"
    ) -> Tuple[bool, Optional[str]]:
        """Validate monetary amounts"""

        if amount is None:
            return False, f"{context.capitalize()} amount is required"

        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except (TypeError, ValueError):
                return False, f"Invalid {context} amount format"

        if amount <= 0:
            return False, f"{context.capitalize()} amount must be positive"

        if amount < WalletValidationService.MIN_TRANSFER_AMOUNT:
            return (
                False,
                f"Minimum {context} amount is {WalletValidationService.MIN_TRANSFER_AMOUNT}",
            )

        if amount > WalletValidationService.MAX_TRANSFER_AMOUNT:
            return (
                False,
                f"Maximum {context} amount is {WalletValidationService.MAX_TRANSFER_AMOUNT}",
            )

        # Check decimal places (max 8)
        if amount.as_tuple().exponent < -8:
            return (
                False,
                f"{context.capitalize()} amount has too many decimal places (max 8)",
            )

        return True, None

    @staticmethod
    def validate_pin(pin: str) -> Tuple[bool, Optional[str]]:
        """Validate PIN format"""

        if not pin:
            return False, "PIN is required"

        if not isinstance(pin, str):
            return False, "PIN must be a string"

        if len(pin) < WalletValidationService.MIN_PIN_LENGTH:
            return (
                False,
                f"PIN must be at least {WalletValidationService.MIN_PIN_LENGTH} digits",
            )

        if len(pin) > WalletValidationService.MAX_PIN_LENGTH:
            return (
                False,
                f"PIN cannot exceed {WalletValidationService.MAX_PIN_LENGTH} digits",
            )

        if not pin.isdigit():
            return False, "PIN must contain only digits"

        # Check for weak PINs
        weak_pins = [
            "0000",
            "1111",
            "2222",
            "3333",
            "4444",
            "5555",
            "6666",
            "7777",
            "8888",
            "9999",
            "1234",
            "4321",
            "0123",
        ]
        if pin in weak_pins:
            return False, "PIN is too weak, please choose a different combination"

        # Check for sequential numbers
        if len(pin) == 4 and (
            pin == "".join(str(i) for i in range(int(pin[0]), int(pin[0]) + 4))
            or pin == "".join(str(i) for i in range(int(pin[0]), int(pin[0]) - 4, -1))
        ):
            return False, "PIN cannot be sequential numbers"

        return True, None

    @staticmethod
    def validate_currency_code(currency_code: str) -> Tuple[bool, Optional[str]]:
        """Validate currency code format"""

        if not currency_code:
            return False, "Currency code is required"

        if not isinstance(currency_code, str):
            return False, "Currency code must be a string"

        currency_code = currency_code.upper()

        # Standard ISO 4217 format
        if not re.match(r"^[A-Z]{3}$", currency_code):
            return False, "Currency code must be 3 uppercase letters"

        return True, None

    @staticmethod
    def validate_wallet_id(wallet_id: str) -> Tuple[bool, Optional[str]]:
        """Validate wallet ID format"""

        if not wallet_id:
            return False, "Wallet ID is required"

        try:
            uuid.UUID(wallet_id)
            return True, None
        except ValueError:
            return False, "Invalid wallet ID format"

    @staticmethod
    def validate_email_list(emails: List[str]) -> Tuple[bool, Optional[str], List[str]]:
        """Validate list of email addresses"""

        if not emails:
            return False, "Email list cannot be empty", []

        if len(emails) < WalletValidationService.MIN_PARTICIPANTS_SPLIT:
            return (
                False,
                f"Minimum {WalletValidationService.MIN_PARTICIPANTS_SPLIT} participants required",
                [],
            )

        if len(emails) > WalletValidationService.MAX_PARTICIPANTS_SPLIT:
            return (
                False,
                f"Maximum {WalletValidationService.MAX_PARTICIPANTS_SPLIT} participants allowed",
                [],
            )

        valid_emails = []
        invalid_emails = []

        for email in emails:
            if not email or not email.strip():
                continue

            email = email.strip().lower()

            try:
                validate_email(email)
                if email not in valid_emails:  # Remove duplicates
                    valid_emails.append(email)
            except DjangoValidationError:
                invalid_emails.append(email)

        if invalid_emails:
            return (
                False,
                f"Invalid email addresses: {', '.join(invalid_emails)}",
                valid_emails,
            )

        if len(valid_emails) < WalletValidationService.MIN_PARTICIPANTS_SPLIT:
            return (
                False,
                f"Need at least {WalletValidationService.MIN_PARTICIPANTS_SPLIT} valid participants",
                valid_emails,
            )

        return True, None, valid_emails

    @staticmethod
    def validate_split_amounts(
        total_amount: Decimal,
        split_type: str,
        participants_count: int,
        custom_amounts: List[Decimal] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate split payment amounts"""

        from apps.wallets.models import SplitPaymentType

        if split_type == SplitPaymentType.EQUAL:
            # Check if amount can be split evenly
            if total_amount % participants_count != 0:
                # This is okay, we'll handle rounding
                pass
            return True, None

        elif split_type == SplitPaymentType.CUSTOM:
            if not custom_amounts:
                return False, "Custom amounts required for custom split"

            if len(custom_amounts) != participants_count:
                return False, "Number of custom amounts must match participants count"

            # Validate each amount
            for i, amount in enumerate(custom_amounts):
                valid, error = WalletValidationService.validate_amount(
                    amount, f"participant {i+1}"
                )
                if not valid:
                    return False, error

            # Check if amounts sum to total
            if sum(custom_amounts) != total_amount:
                return False, "Sum of custom amounts must equal total amount"

        elif split_type == SplitPaymentType.PERCENTAGE:
            if not custom_amounts:
                return False, "Percentages required for percentage split"

            if len(custom_amounts) != participants_count:
                return False, "Number of percentages must match participants count"

            # Validate percentages
            for i, percentage in enumerate(custom_amounts):
                if percentage <= 0 or percentage > 100:
                    return (
                        False,
                        f"Participant {i+1} percentage must be between 0 and 100",
                    )

            # Check if percentages sum to 100
            if abs(sum(custom_amounts) - 100) > 0.01:  # Allow small rounding errors
                return False, "Percentages must sum to 100"

        else:
            return (
                False,
                "Invalid split type. Must be 'equal', 'custom', or 'percentage'",
            )

        return True, None

    @staticmethod
    def validate_frequency(frequency: str) -> Tuple[bool, Optional[str]]:
        """Validate recurring payment frequency"""

        from apps.wallets.models import PaymentFrequency

        valid_frequencies = [choice[0] for choice in PaymentFrequency.choices]

        if not frequency:
            return False, "Frequency is required"

        if frequency not in valid_frequencies:
            return (
                False,
                f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}",
            )

        return True, None

    @staticmethod
    def validate_device_id(device_id: str) -> Tuple[bool, Optional[str]]:
        """Validate device ID format"""

        if not device_id:
            return False, "Device ID is required"

        if len(device_id) < 10 or len(device_id) > 100:
            return False, "Device ID must be between 10 and 100 characters"

        # Allow alphanumeric, hyphens, and underscores
        if not re.match(r"^[a-zA-Z0-9\-_]+$", device_id):
            return False, "Device ID contains invalid characters"

        return True, None

    @staticmethod
    def validate_qr_code_settings(
        amount: Optional[Decimal],
        is_amount_fixed: bool,
        is_single_use: bool,
        expires_at: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        """Validate QR code creation settings"""

        if is_amount_fixed and not amount:
            return False, "Amount is required when amount is fixed"

        if amount:
            valid, error = WalletValidationService.validate_amount(amount, "QR code")
            if not valid:
                return False, error

        if expires_at:
            try:
                from datetime import datetime
                from django.utils import timezone

                # Parse the datetime
                exp_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

                # Check if it's in the future
                if exp_date <= timezone.now():
                    return False, "Expiration date must be in the future"

                # Check if it's not too far in the future (max 1 year)
                max_future = timezone.now() + timezone.timedelta(days=365)
                if exp_date > max_future:
                    return (
                        False,
                        "Expiration date cannot be more than 1 year in the future",
                    )

            except (ValueError, TypeError):
                return False, "Invalid expiration date format"

        return True, None

    @staticmethod
    def validate_virtual_card_settings(
        nickname: Optional[str], spending_limit: Optional[Decimal]
    ) -> Tuple[bool, Optional[str]]:
        """Validate virtual card settings"""

        if nickname:
            if len(nickname) > 50:
                return False, "Card nickname cannot exceed 50 characters"

            if not re.match(r"^[a-zA-Z0-9\s\-_.,()]+$", nickname):
                return False, "Card nickname contains invalid characters"

        if spending_limit:
            valid, error = WalletValidationService.validate_amount(
                spending_limit, "spending limit"
            )
            if not valid:
                return False, error

            # Additional check for reasonable spending limits
            if spending_limit > Decimal("50000.00"):
                return False, "Spending limit cannot exceed $50,000"

        return True, None

    @staticmethod
    def sanitize_input(input_str: str) -> str:
        """Sanitize user input to prevent injection attacks"""

        if not input_str:
            return ""

        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\';\\]', "", input_str)

        # Trim whitespace
        sanitized = sanitized.strip()

        # Limit length
        if len(sanitized) > 1000:
            sanitized = sanitized[:1000]

        return sanitized

    @staticmethod
    def validate_batch_operation(
        operation_type: str, items: List[Dict[str, Any]], max_batch_size: int = 50
    ) -> Tuple[bool, Optional[str]]:
        """Validate batch operations"""

        if not items:
            return False, f"No items provided for {operation_type}"

        if len(items) > max_batch_size:
            return False, f"Batch size cannot exceed {max_batch_size} items"

        # Validate each item has required fields
        required_fields = {
            "transfer": ["to_wallet_id", "amount"],
            "update_wallet": ["wallet_id"],
            "create_qr": ["wallet_id"],
        }

        if operation_type in required_fields:
            for i, item in enumerate(items):
                for field in required_fields[operation_type]:
                    if field not in item or item[field] is None:
                        return False, f"Item {i+1} missing required field: {field}"

        return True, None

    @staticmethod
    def check_rate_limits(
        user_id: str, operation: str, current_count: int
    ) -> Tuple[bool, Optional[str]]:
        """Check rate limits for operations"""

        limits = {
            "transfer": 100,  # per day
            "create_wallet": 10,  # per day
            "create_virtual_card": 5,  # per day
            "create_qr": 50,  # per day
            "split_payment": 20,  # per day
        }

        if operation in limits and current_count >= limits[operation]:
            return (
                False,
                f"Daily limit exceeded for {operation} ({limits[operation]} per day)",
            )

        return True, None

    @staticmethod
    def comprehensive_validation(
        operation: str, data: Dict[str, Any], user_context: Dict[str, Any] = None
    ) -> Tuple[bool, List[str]]:
        """Perform comprehensive validation for any wallet operation"""

        errors = []

        try:
            if operation == "create_wallet":
                # Validate wallet creation
                if "name" in data:
                    valid, error = WalletValidationService.validate_wallet_name(
                        data["name"]
                    )
                    if not valid:
                        errors.append(error)

                if "description" in data:
                    valid, error = WalletValidationService.validate_description(
                        data["description"]
                    )
                    if not valid:
                        errors.append(error)

                if "currency_code" in data:
                    valid, error = WalletValidationService.validate_currency_code(
                        data["currency_code"]
                    )
                    if not valid:
                        errors.append(error)

            elif operation == "transfer":
                # Validate transfer
                if "amount" in data:
                    valid, error = WalletValidationService.validate_amount(
                        data["amount"]
                    )
                    if not valid:
                        errors.append(error)

                if "to_wallet_id" in data:
                    valid, error = WalletValidationService.validate_wallet_id(
                        data["to_wallet_id"]
                    )
                    if not valid:
                        errors.append(error)

                if "pin" in data and data["pin"]:
                    valid, error = WalletValidationService.validate_pin(data["pin"])
                    if not valid:
                        errors.append(error)

            elif operation == "create_split_payment":
                # Validate split payment
                if "participants" in data:
                    valid, error, _ = WalletValidationService.validate_email_list(
                        data["participants"]
                    )
                    if not valid:
                        errors.append(error)

                if "total_amount" in data:
                    valid, error = WalletValidationService.validate_amount(
                        data["total_amount"]
                    )
                    if not valid:
                        errors.append(error)

            # Add more operation validations as needed

        except Exception as e:
            errors.append(f"Validation error: {str(e)}")

        return len(errors) == 0, errors
