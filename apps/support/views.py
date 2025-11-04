from ninja import Router, Query
from typing import Optional
from uuid import UUID

from apps.common.cache import cacheable, invalidate_cache
from apps.common.responses import CustomResponse
from apps.common.schemas import PaginationQuerySchema
from apps.support.schemas import (
    CreateTicketSchema,
    CreateMessageSchema,
    TicketDataResponseSchema,
    MessageDataResponseSchema,
    MessageListResponseSchema,
    FAQListDataResponseSchema,
    RateTicketSchema,
    TicketListResponseSchema,
    TicketStatsDataResponseSchema,
    FAQFilterSchema,
)
from apps.support.services.ticket_manager import TicketManager
from apps.support.models import FAQ, TicketStatus
from asgiref.sync import sync_to_async

support_router = Router(tags=["Support (9)"])


# ==================== TICKETS ====================


@support_router.post(
    "/tickets/create",
    summary="Create support ticket",
    response={201: TicketDataResponseSchema},
)
@invalidate_cache(patterns=["tickets:list:{{user_id}}:*"])
async def create_ticket(request, data: CreateTicketSchema):
    """Create a new support ticket"""
    user = request.auth
    ticket = await TicketManager.create_ticket(user, data)
    return CustomResponse.success("Ticket created successfully", ticket, 201)


@support_router.get(
    "/tickets/list",
    summary="List my tickets",
    response={200: TicketListResponseSchema},
)
@cacheable(key="tickets:list:{{user_id}}", ttl=60)
async def list_tickets(
    request,
    status: Optional[TicketStatus] = None,
    page_params: PaginationQuerySchema = Query(...),
):
    user = request.auth
    paginated_tickets_data = await TicketManager.list_tickets(user, status, page_params)
    return CustomResponse.success(
        "Tickets retrieved successfully", paginated_tickets_data
    )


@support_router.get(
    "/tickets/{ticket_id}",
    summary="Get ticket details",
    response={200: TicketDataResponseSchema},
)
@cacheable(key="tickets:detail:{{ticket_id}}:{{user_id}}", ttl=60)
async def get_ticket(request, ticket_id: UUID):
    user = request.auth
    ticket = await TicketManager.get_ticket(user, ticket_id)
    return CustomResponse.success("Ticket retrieved successfully", ticket)


@support_router.post(
    "/tickets/{ticket_id}/close",
    summary="Close ticket",
    response={200: TicketDataResponseSchema},
)
@invalidate_cache(
    patterns=["tickets:detail:{{ticket_id}}:*", "tickets:list:{{user_id}}:*"]
)
async def close_ticket(request, ticket_id: UUID):
    user = request.auth
    ticket = await TicketManager.close_ticket(user, ticket_id)
    return CustomResponse.success("Ticket closed successfully", ticket)


@support_router.post(
    "/tickets/{ticket_id}/rate",
    summary="Rate ticket",
    response={200: TicketDataResponseSchema},
)
async def rate_ticket(request, ticket_id: UUID, data: RateTicketSchema):
    user = request.auth
    ticket = await TicketManager.rate_ticket(
        user, ticket_id, data.rating, data.feedback or ""
    )
    return CustomResponse.success("Ticket rated successfully", ticket)


# ==================== MESSAGES ====================
@support_router.post(
    "/tickets/{ticket_id}/messages",
    summary="Add message to ticket",
    response={201: MessageDataResponseSchema},
)
async def add_message(request, ticket_id: UUID, data: CreateMessageSchema):
    user = request.auth
    message = await TicketManager.add_message(user, ticket_id, data)
    return CustomResponse.success("Message added successfully", message, 201)


@support_router.get(
    "/tickets/{ticket_id}/messages",
    summary="Get ticket messages",
    response={200: MessageListResponseSchema},
)
async def get_messages(
    request, ticket_id: UUID, page_params: PaginationQuerySchema = Query(...)
):
    """Get all messages for a ticket"""
    user = request.auth
    paginated_messages_data = await TicketManager.get_messages(
        user, ticket_id, page_params
    )
    return CustomResponse.success(
        "Messages retrieved successfully", paginated_messages_data
    )


# ==================== STATS ====================


@support_router.get(
    "/tickets/stats/data",
    summary="Get my ticket statistics",
    response={200: TicketStatsDataResponseSchema},
)
async def get_ticket_stats(request):
    user = request.auth
    stats = await TicketManager.get_ticket_stats(user)
    return CustomResponse.success("Statistics retrieved successfully", stats)


# ==================== FAQ ====================
@support_router.get(
    "/faq/list",
    summary="List FAQs",
    response={200: FAQListDataResponseSchema},
)
@cacheable(
    key="faq:list:{{user_id}}",
    ttl=60 * 5,
)
async def list_faqs(request, filters: FAQFilterSchema = Query(...)):
    queryset = filters.filter(FAQ.objects.filter(is_published=True))
    faqs = await sync_to_async(list)(queryset.order_by("order", "-created_at"))
    return CustomResponse.success("FAQs retrieved successfully", faqs)
