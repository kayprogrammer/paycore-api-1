from django.utils import timezone
from typing import Optional

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.exceptions import NotFoundError, RequestError, ErrorCode
from apps.support.models import (
    SupportTicket,
    TicketMessage,
    TicketStatus,
)
from apps.support.schemas import CreateTicketSchema, CreateMessageSchema
from apps.common.schemas import PaginationQuerySchema
from apps.common.paginators import Paginator
from django.db.models import Count, Avg, Q, F, ExpressionWrapper, DurationField
from django.db.models.functions import Extract


class TicketManager:
    """Service for managing support tickets"""

    @staticmethod
    @aatomic
    async def create_ticket(user: User, data: CreateTicketSchema) -> SupportTicket:
        ticket = await SupportTicket.objects.acreate(user=user, **data.model_dump())
        await TicketMessage.objects.acreate(
            ticket=ticket,
            sender=user,
            message=data.description,
            is_from_customer=True,
        )
        return ticket

    @staticmethod
    async def get_ticket(user: User, ticket_id) -> SupportTicket:
        ticket = await SupportTicket.objects.select_related(
            "user", "assigned_to"
        ).aget_or_none(ticket_id=ticket_id, user=user)

        if not ticket:
            raise NotFoundError("Ticket not found")
        return ticket

    @staticmethod
    async def list_tickets(
        user: User,
        status: Optional[str] = None,
        page_params: PaginationQuerySchema = None,
    ):
        queryset = SupportTicket.objects.filter(user=user).select_related(
            "user", "assigned_to"
        )

        if status:
            queryset = queryset.filter(status=status)
        return await Paginator.paginate_queryset(
            queryset.order_by("-created_at"), page_params.page, page_params.limit
        )

    @staticmethod
    @aatomic
    async def add_message(
        user: User, ticket_id, data: CreateMessageSchema
    ) -> TicketMessage:
        ticket = await TicketManager.get_ticket(user, ticket_id)
        if ticket.status == TicketStatus.CLOSED:
            ticket.status = TicketStatus.REOPENED
            ticket.reopened_at = timezone.now()
            await ticket.asave(update_fields=["status", "reopened_at", "updated_at"])

        message = await TicketMessage.objects.acreate(
            ticket=ticket,
            sender=user,
            message=data.message,
            is_from_customer=True,
        )

        # Update ticket status to waiting on agent
        if ticket.status == TicketStatus.WAITING_CUSTOMER:
            ticket.status = TicketStatus.WAITING_AGENT
            await ticket.asave(update_fields=["status", "updated_at"])
        return message

    @staticmethod
    async def get_messages(user: User, ticket_id, page_params: PaginationQuerySchema):
        ticket = await TicketManager.get_ticket(user, ticket_id)
        messages = ticket.messages.filter(is_internal=False).select_related("sender")
        return await Paginator.paginate_queryset(
            messages.order_by("created_at"), page_params.page, page_params.limit
        )

    @staticmethod
    @aatomic
    async def close_ticket(user: User, ticket_id):
        ticket = await TicketManager.get_ticket(user, ticket_id)

        if ticket.status == TicketStatus.CLOSED:
            raise RequestError(ErrorCode.INVALID_ENTRY, "Ticket is already closed")

        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = timezone.now()
        await ticket.asave(update_fields=["status", "closed_at", "updated_at"])
        return ticket

    @staticmethod
    @aatomic
    async def rate_ticket(user: User, ticket_id, rating: int, feedback: str = ""):
        ticket = await TicketManager.get_ticket(user, ticket_id)

        if ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            raise RequestError(
                ErrorCode.NOT_ALLOWED, "Can only rate resolved or closed tickets"
            )

        ticket.satisfaction_rating = rating
        ticket.feedback = feedback
        await ticket.asave(
            update_fields=["satisfaction_rating", "feedback", "updated_at"]
        )
        return ticket

    @staticmethod
    async def get_ticket_stats(user: User) -> dict:
        stats = await SupportTicket.objects.filter(user=user).aaggregate(
            total_tickets=Count("id"),
            open_tickets=Count(
                "id",
                filter=Q(
                    status__in=[
                        TicketStatus.OPEN,
                        TicketStatus.IN_PROGRESS,
                        TicketStatus.WAITING_AGENT,
                    ]
                ),
            ),
            in_progress_tickets=Count("id", filter=Q(status=TicketStatus.IN_PROGRESS)),
            resolved_tickets=Count("id", filter=Q(status=TicketStatus.RESOLVED)),
            closed_tickets=Count("id", filter=Q(status=TicketStatus.CLOSED)),
            # Average response time in minutes
            avg_response_minutes=Avg(
                ExpressionWrapper(
                    Extract(F("first_response_at") - F("created_at"), "epoch") / 60,
                    output_field=DurationField(),
                ),
                filter=Q(first_response_at__isnull=False),
            ),
            # Average resolution time in hours
            avg_resolution_hours=Avg(
                ExpressionWrapper(
                    Extract(F("resolved_at") - F("created_at"), "epoch") / 3600,
                    output_field=DurationField(),
                ),
                filter=Q(resolved_at__isnull=False),
            ),
            # Average satisfaction rating
            satisfaction_average=Avg(
                "satisfaction_rating", filter=Q(satisfaction_rating__isnull=False)
            ),
        )

        return {
            "total_tickets": stats["total_tickets"] or 0,
            "open_tickets": stats["open_tickets"] or 0,
            "in_progress_tickets": stats["in_progress_tickets"] or 0,
            "resolved_tickets": stats["resolved_tickets"] or 0,
            "closed_tickets": stats["closed_tickets"] or 0,
            "avg_response_time_minutes": round(stats["avg_response_minutes"] or 0, 2),
            "avg_resolution_time_hours": round(stats["avg_resolution_hours"] or 0, 2),
            "satisfaction_average": round(stats["satisfaction_average"] or 0, 2),
        }
