import uuid
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel
from apps.accounts.models import User


class TicketCategory(models.TextChoices):
    ACCOUNT = "account", "Account Issues"
    WALLET = "wallet", "Wallet & Balance"
    TRANSACTION = "transaction", "Transaction Issues"
    CARD = "card", "Card Services"
    LOAN = "loan", "Loan Services"
    INVESTMENT = "investment", "Investment Services"
    BILL_PAYMENT = "bill_payment", "Bill Payments"
    PAYMENT = "payment", "Payments"
    KYC = "kyc", "KYC/Verification"
    SECURITY = "security", "Security & Privacy"
    TECHNICAL = "technical", "Technical Issues"
    FEEDBACK = "feedback", "Feedback & Suggestions"
    OTHER = "other", "Other"


class TicketPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    WAITING_CUSTOMER = "waiting_customer", "Waiting on Customer"
    WAITING_AGENT = "waiting_agent", "Waiting on Agent"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"
    REOPENED = "reopened", "Reopened"


class SupportTicket(BaseModel):
    ticket_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    ticket_number = models.CharField(
        max_length=20, unique=True, editable=False, db_index=True
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="support_tickets"
    )
    subject = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=TicketCategory.choices)
    priority = models.CharField(
        max_length=10, choices=TicketPriority.choices, default=TicketPriority.MEDIUM
    )
    status = models.CharField(
        max_length=20, choices=TicketStatus.choices, default=TicketStatus.OPEN
    )

    description = models.TextField()

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    related_transaction_id = models.UUIDField(null=True, blank=True)
    related_wallet_id = models.UUIDField(null=True, blank=True)
    related_loan_id = models.UUIDField(null=True, blank=True)
    related_investment_id = models.UUIDField(null=True, blank=True)

    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    reopened_at = models.DateTimeField(null=True, blank=True)

    satisfaction_rating = models.PositiveIntegerField(
        null=True, blank=True, help_text="Customer satisfaction rating 1-5"
    )
    feedback = models.TextField(blank=True)

    tags = models.JSONField(default=list, blank=True)
    internal_notes = models.TextField(
        blank=True, help_text="Internal notes (not visible to customer)"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["category", "status"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"Ticket #{self.ticket_number} - {self.subject}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            year = timezone.now().year
            count = SupportTicket.objects.filter(
                ticket_number__startswith=f"{year}-"
            ).count()
            self.ticket_number = f"{year}-{count + 1:06d}"
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status in [
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING_CUSTOMER,
            TicketStatus.WAITING_AGENT,
            TicketStatus.REOPENED,
        ]

    @property
    def response_time(self):
        if self.first_response_at:
            return self.first_response_at - self.created_at
        return None

    @property
    def resolution_time(self):
        if self.resolved_at:
            return self.resolved_at - self.created_at
        return None


class TicketMessage(BaseModel):
    message_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ticket_messages"
    )
    message = models.TextField()
    is_internal = models.BooleanField(
        default=False, help_text="Internal note (not visible to customer)"
    )
    is_from_customer = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
            models.Index(fields=["is_read", "is_from_customer"]),
        ]

    def __str__(self):
        return f"Message on {self.ticket.ticket_number}"


class TicketAttachment(BaseModel):
    attachment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="attachments"
    )
    message = models.ForeignKey(
        TicketMessage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)

    file = models.FileField(upload_to="support/attachments/%Y/%m/%d/")
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=100)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Attachment: {self.file_name}"


class FAQ(BaseModel):
    faq_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=20, choices=TicketCategory.choices)

    order = models.PositiveIntegerField(default=0, help_text="Display order")
    is_published = models.BooleanField(default=True)

    view_count = models.PositiveIntegerField(default=0)
    helpful_count = models.PositiveIntegerField(default=0)
    not_helpful_count = models.PositiveIntegerField(default=0)

    tags = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["order", "-created_at"]
        indexes = [
            models.Index(fields=["category", "is_published"]),
            models.Index(fields=["is_published", "order"]),
        ]

    def __str__(self):
        return self.question

    @property
    def helpfulness_score(self):
        total = self.helpful_count + self.not_helpful_count
        if total == 0:
            return 0
        return (self.helpful_count / total) * 100


class CannedResponse(BaseModel):
    """Pre-written responses for common issues"""

    response_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=TicketCategory.choices)
    is_active = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_responses"
    )

    class Meta:
        ordering = ["-usage_count", "title"]

    def __str__(self):
        return self.title


class TicketEscalation(BaseModel):
    """Ticket escalation tracking"""

    escalation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="escalations"
    )

    escalated_from = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="escalations_made"
    )
    escalated_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="escalations_received"
    )

    reason = models.TextField()
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Escalation for {self.ticket.ticket_number}"
