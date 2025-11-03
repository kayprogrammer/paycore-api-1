from ninja import ModelSchema, FilterSchema
from pydantic import Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from apps.common.schemas import (
    BaseSchema,
    PaginatedResponseDataSchema,
    ResponseSchema,
    UserDataSchema,
)
from apps.support.models import (
    SupportTicket,
    TicketMessage,
    TicketAttachment,
    FAQ,
    CannedResponse,
    TicketCategory,
)


# ============================================================================
# Ticket Schemas
# ============================================================================


class CreateTicketSchema(BaseSchema):
    subject: str = Field(..., min_length=5, max_length=255)
    category: TicketCategory
    priority: str = Field(default="medium")
    description: str = Field(..., min_length=10)
    related_transaction_id: Optional[UUID] = None
    related_wallet_id: Optional[UUID] = None
    related_loan_id: Optional[UUID] = None
    related_investment_id: Optional[UUID] = None


class UpdateTicketSchema(BaseSchema):
    subject: Optional[str] = Field(None, min_length=5, max_length=255)
    priority: Optional[str] = None
    category: Optional[str] = None


class TicketSchema(BaseSchema):
    ticket_id: UUID
    ticket_number: str
    subject: str
    category: str
    priority: str
    status: str
    description: str
    user_email: str = Field(
        ..., description="Email of the customer", alias="user.email"
    )
    assigned_to_email: Optional[str] = Field(
        None,
        description="Email of the agent assigned to the ticket",
        alias="assigned_to.email",
    )
    first_response_at: Optional[datetime]
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    satisfaction_rating: Optional[int]
    is_open: bool
    created_at: datetime
    updated_at: datetime


class TicketListSchema(BaseSchema):
    ticket_id: UUID
    ticket_number: str
    subject: str
    category: str
    priority: str
    status: str
    is_open: bool
    created_at: datetime


class TicketDataResponseSchema(ResponseSchema):
    data: TicketSchema


class TicketListDataResponseSchema(PaginatedResponseDataSchema):
    data: List[TicketListSchema] = Field(..., alias="items")


class TicketListResponseSchema(ResponseSchema):
    data: TicketListDataResponseSchema


# ============================================================================
# Message Schemas
# ============================================================================


class CreateMessageSchema(BaseSchema):
    message: str = Field(..., min_length=1)


class MessageSchema(BaseSchema):
    message_id: UUID
    sender_email: str = Field(
        ..., description="Email of the sender", alias="sender.email"
    )
    message: str
    is_from_customer: bool
    is_read: bool
    created_at: datetime


class MessageDataResponseSchema(ResponseSchema):
    data: MessageSchema


class MessageListDataResponseSchema(PaginatedResponseDataSchema):
    data: List[MessageSchema] = Field(..., alias="items")


class MessageListResponseSchema(ResponseSchema):
    data: MessageListDataResponseSchema


# ============================================================================
# FAQ Schemas
# ============================================================================
class FAQFilterSchema(FilterSchema):
    category: Optional[TicketCategory] = None
    search: Optional[str] = Field(
        None,
        example="fees payment",
        q=[
            "question__icontains",
            "answer__icontains",
        ],
    )


class FAQSchema(ModelSchema):
    class Meta:
        model = FAQ
        exclude = ["id", "created_at", "updated_at", "deleted_at"]


class FAQListSchema(BaseSchema):
    faq_id: UUID
    question: str
    answer: str
    category: str
    view_count: int
    helpfulness_score: float
    created_at: datetime
    updated_at: datetime


class FAQDataResponseSchema(ResponseSchema):
    data: FAQSchema


class FAQListDataResponseSchema(ResponseSchema):
    data: List[FAQListSchema]


# ============================================================================
# Action Schemas
# ============================================================================


class RateTicketSchema(BaseSchema):
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = Field(None, max_length=1000)


class AssignTicketSchema(BaseSchema):
    agent_user_id: UUID


class CloseTicketSchema(BaseSchema):
    resolution_notes: Optional[str] = None


class TicketStatsSchema(BaseSchema):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    avg_response_time_minutes: float
    avg_resolution_time_hours: float
    satisfaction_average: float


class TicketStatsDataResponseSchema(ResponseSchema):
    data: TicketStatsSchema
