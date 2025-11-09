from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid
import secrets
import string

from apps.accounts.models import User
from apps.common.models import BaseModel
from apps.wallets.models import Wallet


class TransactionType(models.TextChoices):
    TRANSFER = "transfer", "Transfer"
    DEPOSIT = "deposit", "Deposit"
    WITHDRAWAL = "withdrawal", "Withdrawal"
    PAYMENT = "payment", "Payment"
    REFUND = "refund", "Refund"
    FEE = "fee", "Fee"
    HOLD = "hold", "Hold"
    RELEASE = "release", "Release"
    SPLIT_PAYMENT = "split_payment", "Split Payment"
    RECURRING_PAYMENT = "recurring_payment", "Recurring Payment"
    QR_PAYMENT = "qr_payment", "QR Payment"
    VIRTUAL_CARD = "virtual_card", "Virtual Card"
    ADJUSTMENT = "adjustment", "Adjustment"

    # Card transaction types
    CARD_PURCHASE = "card_purchase", "Card Purchase"
    CARD_WITHDRAWAL = "card_withdrawal", "Card ATM Withdrawal"
    CARD_REFUND = "card_refund", "Card Refund"
    CARD_REVERSAL = "card_reversal", "Card Reversal"
    CARD_FUND = "card_fund", "Card Funding"

    # Bill payment type
    BILL_PAYMENT = "bill_payment", "Bill Payment"

    # Loan transaction types
    LOAN_PAYMENT = "loan_payment", "Loan Payment"
    LOAN_REPAYMENT = "loan_repayment", "Loan Repayment"
    LOAN_FEE = "loan_fee", "Loan Fee"
    LOAN_INTEREST = "loan_interest", "Loan Interest"
    LOAN_PENALTY = "loan_penalty", "Loan Penalty"
    LOAN_DISBURSEMENT = "loan_disbursement", "Loan Disbursement"

    # Investment transaction types
    INVESTMENT = "investment", "Investment"
    INVESTMENT_REPAYMENT = "investment_repayment", "Investment Repayment"
    INVESTMENT_FEE = "investment_fee", "Investment Fee"
    INVESTMENT_INTEREST = "investment_interest", "Investment Interest"
    INVESTMENT_PENALTY = "investment_penalty", "Investment Penalty"
    INVESTMENT_PAYOUT = "investment_payout", "Investment Payout"


class TransactionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    REVERSED = "reversed", "Reversed"
    EXPIRED = "expired", "Expired"


class TransactionDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"
    INTERNAL = "internal", "Internal"


class Transaction(BaseModel):
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING,
    )
    direction = models.CharField(
        max_length=20,
        choices=TransactionDirection.choices,
        default=TransactionDirection.INTERNAL,
    )

    # Amount and Currency
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    fee_amount = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    net_amount = models.DecimalField(max_digits=20, decimal_places=8)  # amount - fee

    from_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="sent_transactions",
        null=True,
        blank=True,
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="received_transactions",
        null=True,
        blank=True,
    )

    # Wallet References (will be set via foreign keys)
    from_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        related_name="transactions_debit",
        null=True,
        blank=True,
    )
    to_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        related_name="transactions_credit",
        null=True,
        blank=True,
    )

    description = models.CharField(max_length=500, blank=True, null=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    external_reference = models.CharField(max_length=100, blank=True, null=True)

    # Related Objects (for tracking source transactions)
    split_payment_id = models.UUIDField(null=True, blank=True)
    recurring_payment_id = models.UUIDField(null=True, blank=True)
    qr_code_id = models.UUIDField(null=True, blank=True)
    virtual_card_id = models.UUIDField(null=True, blank=True)
    virtual_account_id = models.UUIDField(
        null=True, blank=True, help_text="Virtual account used for this deposit"
    )

    # External deposit details (for virtual account deposits)
    sender_account_number = models.CharField(max_length=50, null=True, blank=True)
    sender_account_name = models.CharField(max_length=100, null=True, blank=True)
    sender_bank_name = models.CharField(max_length=100, null=True, blank=True)

    # Card transaction details (for card purchases, ATM withdrawals, etc.)
    card = models.ForeignKey(
        "cards.Card",
        on_delete=models.SET_NULL,
        related_name="transactions",
        null=True,
        blank=True,
        help_text="Card used for this transaction (if applicable)",
    )
    merchant_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Merchant name for card transactions",
    )
    merchant_category = models.CharField(
        max_length=100, null=True, blank=True, help_text="Merchant category code (MCC)"
    )
    transaction_location = models.JSONField(
        default=dict,
        blank=True,
        help_text="Transaction location (city, country, coordinates)",
    )

    # Balances (for auditing)
    from_balance_before = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    from_balance_after = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    to_balance_before = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    to_balance_after = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )

    # Timestamps
    initiated_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    failure_reason = models.CharField(max_length=500, blank=True, null=True)

    # Security and Compliance
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, null=True)
    device_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["from_user", "created_at"]),
            models.Index(fields=["to_user", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["transaction_type", "created_at"]),
            models.Index(fields=["from_wallet"]),
            models.Index(fields=["to_wallet"]),
            models.Index(fields=["reference"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} ({self.status})"

    @staticmethod
    def generate_reference():
        """Generate a standard 28-character reference starting with PYC"""
        # PYC + 25 random uppercase letters and digits = 28 characters
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(secrets.choice(chars) for _ in range(25))
        return f"PYC{random_part}"

    def save(self, *args, **kwargs):
        """Override save to auto-generate reference if not provided"""
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)

    @property
    def currency_code(self):
        """Get currency code from wallet (requires additional query)"""
        # This would need to be populated when fetching transactions
        return getattr(self, "_currency_code", "USD")

    def is_successful(self):
        return self.status == TransactionStatus.COMPLETED

    def is_pending(self):
        return self.status in [TransactionStatus.PENDING, TransactionStatus.PROCESSING]

    def is_failed(self):
        return self.status in [
            TransactionStatus.FAILED,
            TransactionStatus.CANCELLED,
            TransactionStatus.EXPIRED,
        ]

    def complete_transaction(self):
        self.status = TransactionStatus.COMPLETED
        self.completed_at = timezone.now()
        if not self.processed_at:
            self.processed_at = timezone.now()

    def fail_transaction(self, reason: str = None):
        self.status = TransactionStatus.FAILED
        self.failed_at = timezone.now()
        if reason:
            self.failure_reason = reason

    def reverse_transaction(self):
        self.status = TransactionStatus.REVERSED


class TransactionFee(BaseModel):
    """Track transaction fees separately for detailed reporting"""

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="fees"
    )
    fee_type = models.CharField(
        max_length=50
    )  # 'processing', 'service', 'exchange', etc.
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    percentage = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True
    )
    description = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"{self.fee_type} fee: {self.amount}"


class TransactionHold(BaseModel):
    """Track funds held for pending transactions"""

    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="hold"
    )
    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="holds", null=True
    )
    amount_held = models.DecimalField(max_digits=20, decimal_places=8)
    released_amount = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Hold: {self.amount_held} ({self.transaction.transaction_id})"

    @property
    def remaining_hold(self):
        return self.amount_held - self.released_amount

    def is_expired(self):
        return self.expires_at and timezone.now() > self.expires_at

    def release_hold(self, amount: Decimal = None):
        """Release hold partially or fully"""
        if amount is None:
            amount = self.remaining_hold

        if amount > self.remaining_hold:
            raise ValueError("Cannot release more than remaining hold amount")

        self.released_amount += amount
        if self.released_amount >= self.amount_held:
            self.released_at = timezone.now()


class DisputeStatus(models.TextChoices):
    OPENED = "opened", "Opened"
    INVESTIGATING = "investigating", "Investigating"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class DisputeType(models.TextChoices):
    UNAUTHORIZED = "unauthorized", "Unauthorized Transaction"
    DUPLICATE = "duplicate", "Duplicate Charge"
    NOT_RECEIVED = "not_received", "Services/Goods Not Received"
    DEFECTIVE = "defective", "Defective Product/Service"
    REFUND_NOT_PROCESSED = "refund_not_processed", "Refund Not Processed"
    OTHER = "other", "Other"


class TransactionDispute(BaseModel):
    """Handle transaction disputes and chargebacks"""

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="disputes"
    )
    dispute_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=20, choices=DisputeStatus.choices, default=DisputeStatus.OPENED
    )
    dispute_type = models.CharField(max_length=30, choices=DisputeType.choices)
    reason = models.TextField()
    disputed_amount = models.DecimalField(max_digits=20, decimal_places=8)
    initiated_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="initiated_disputes"
    )

    resolution_notes = models.TextField(blank=True, null=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_disputes",
    )
    evidence = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Dispute {self.dispute_id} - {self.dispute_type} ({self.status})"


class TransactionLog(BaseModel):
    """Audit log for transaction state changes"""

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="logs"
    )
    previous_status = models.CharField(max_length=20, blank=True, null=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    reason = models.CharField(max_length=200, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.transaction.transaction_id}: {self.previous_status} → {self.new_status}"
