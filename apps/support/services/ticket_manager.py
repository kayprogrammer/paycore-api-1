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
from django.db.models import Count, Avg, Q
from datetime import timedelta


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
        tickets = SupportTicket.objects.filter(user=user)

        total = await tickets.acount()
        open_count = await tickets.filter(
            status__in=[
                TicketStatus.OPEN,
                TicketStatus.IN_PROGRESS,
                TicketStatus.WAITING_AGENT,
            ]
        ).acount()
        resolved = await tickets.filter(status=TicketStatus.RESOLVED).acount()
        closed = await tickets.filter(status=TicketStatus.CLOSED).acount()

        # Calculate averages
        response_times = []
        resolution_times = []
        ratings = []

        async for ticket in tickets:
            if ticket.first_response_at:
                response_delta = ticket.first_response_at - ticket.created_at
                response_times.append(response_delta.total_seconds() / 60)

            if ticket.resolved_at:
                resolution_delta = ticket.resolved_at - ticket.created_at
                resolution_times.append(resolution_delta.total_seconds() / 3600)

            if ticket.satisfaction_rating:
                ratings.append(ticket.satisfaction_rating)

        avg_response = (
            sum(response_times) / len(response_times) if response_times else 0
        )
        avg_resolution = (
            sum(resolution_times) / len(resolution_times) if resolution_times else 0
        )
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        return {
            "total_tickets": total,
            "open_tickets": open_count,
            "in_progress_tickets": await tickets.filter(
                status=TicketStatus.IN_PROGRESS
            ).acount(),
            "resolved_tickets": resolved,
            "closed_tickets": closed,
            "avg_response_time_minutes": round(avg_response, 2),
            "avg_resolution_time_hours": round(avg_resolution, 2),
            "satisfaction_average": round(avg_rating, 2),
        }
