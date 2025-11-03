from uuid import UUID
from ninja import Query, Router

from apps.cards.services import CardManager, CardOperations
from apps.cards.schemas import (
    CardTransactionListResponseSchema,
    CreateCardSchema,
    UpdateCardSchema,
    FundCardSchema,
    CardControlsSchema,
    CreateCardDataResponseSchema,
    CardDataResponseSchema,
    CardListDataResponseSchema,
    FundCardDataResponseSchema,
)
from apps.common.responses import CustomResponse
from apps.common.schemas import PaginationQuerySchema, ResponseSchema
from apps.common.cache import cacheable, invalidate_cache

card_router = Router(tags=["Cards (12)"])


# =============== CARD MANAGEMENT ENDPOINTS ===============
@card_router.post(
    "/create",
    summary="Create a new card",
    description="""
        Create a new virtual or physical card linked to a wallet.

        Card Types:
        - `virtual`: Digital card for online transactions
        - `physical`: Physical card for ATM/POS (coming soon)

        Card Brands:
        - `visa`: Visa card
        - `mastercard`: Mastercard
        - `verve`: Verve (NGN only)

        Note: Cards are created in INACTIVE status. You must activate them before use.
    """,
    response={201: CreateCardDataResponseSchema},
)
@invalidate_cache(patterns=["cards:list:{{user_id}}:*"])
async def create_card(request, data: CreateCardSchema):
    card = await CardManager.create_card(request.auth, data)
    return CustomResponse.success(
        message="Card created successfully", data=card, status_code=201
    )


@card_router.get(
    "/list",
    summary="List user cards",
    description="""
        Get all cards for the authenticated user.

        **Query Parameters:**
        - `status`: Filter by card status (active, inactive, frozen, blocked, expired)
        - `card_type`: Filter by card type (virtual, physical)
    """,
    response={200: CardListDataResponseSchema},
)
@cacheable(key="cards:list:{{user_id}}", ttl=60)
async def list_cards(request, status: str = None, card_type: str = None):
    cards = await CardManager.get_user_cards(
        request.auth, status=status, card_type=card_type
    )
    return CustomResponse.success(message="Cards retrieved successfully", data=cards)


@card_router.get(
    "/card/{card_id}",
    summary="Get card details",
    description="""
        Get detailed information about a specific card.

        **Security:** Sensitive information (full card number, CVV) is NOT returned.
        Only the masked card number is shown.
    """,
    response={200: CardDataResponseSchema},
)
@cacheable(key="cards:detail:{{card_id}}:{{user_id}}", ttl=60)
async def get_card(request, card_id: UUID):
    card = await CardManager.get_card(request.auth, card_id)
    return CustomResponse.success(
        message="Card details retrieved successfully", data=card
    )


@card_router.patch(
    "/card/{card_id}",
    summary="Update card settings",
    description="""
        Update card settings such as:
        - Nickname
        - Spending limits
        - Transaction controls (online, ATM, international)
        - Billing address
    """,
    response={200: CardDataResponseSchema},
)
@invalidate_cache(patterns=["cards:detail:{{card_id}}:*", "cards:list:{{user_id}}:*"])
async def update_card(request, card_id: UUID, data: UpdateCardSchema):
    card = await CardManager.update_card(request.auth, card_id, data)
    return CustomResponse.success(message="Card updated successfully", data=card)


# =============== CARD OPERATIONS ===============
@card_router.post(
    "/card/{card_id}/fund",
    summary="Fund card from wallet",
    description="""
        Fund a card from its linked wallet.

        **Process:**
        1. Validates card and wallet
        2. Checks wallet has sufficient balance
        3. Verifies PIN if required
        4. Creates funding transaction

        **Note:** Money remains in wallet but is allocated for card usage.
    """,
    response={200: FundCardDataResponseSchema},
)
async def fund_card(request, card_id: UUID, data: FundCardSchema):
    result = await CardOperations.fund_card(
        user=request.auth,
        card_id=card_id,
        amount=data.amount,
        pin=str(data.pin) if data.pin else None,
        description=data.description,
    )

    return CustomResponse.success(message=result["message"], data=result)


@card_router.post(
    "/card/{card_id}/freeze",
    summary="Freeze card",
    description="""
        Temporarily freeze a card to prevent transactions.

        **Use cases:**
        - Suspected fraud
        - Lost card (before blocking permanently)
        - Temporary travel hold

        **Note:** Frozen cards can be unfrozen. Blocked cards cannot.
    """,
    response={200: CardDataResponseSchema},
)
@invalidate_cache(patterns=["cards:detail:{{card_id}}:*", "cards:list:{{user_id}}:*"])
async def freeze_card(request, card_id: UUID):
    card = await CardManager.freeze_card(request.auth, card_id)
    return CustomResponse.success(message="Card frozen successfully", data=card)


@card_router.post(
    "/card/{card_id}/unfreeze",
    summary="Unfreeze card",
    description="""
        Unfreeze a previously frozen card to allow transactions again.
    """,
    response={200: CardDataResponseSchema},
)
@invalidate_cache(patterns=["cards:detail:{{card_id}}:*", "cards:list:{{user_id}}:*"])
async def unfreeze_card(request, card_id: UUID):
    card = await CardManager.unfreeze_card(request.auth, card_id)
    return CustomResponse.success(message="Card unfrozen successfully", data=card)


@card_router.post(
    "/card/{card_id}/block",
    summary="Block card permanently",
    description="""
        Permanently block a card.

        **Warning:** This action cannot be undone. Blocked cards cannot be unblocked.

        **Use cases:**
        - Card is stolen
        - Card is compromised
        - User wants to terminate card

        **Recommendation:** Use freeze instead if you might want to reactivate later.
    """,
    response={200: CardDataResponseSchema},
)
@invalidate_cache(patterns=["cards:detail:{{card_id}}:*", "cards:list:{{user_id}}:*"])
async def block_card(request, card_id: UUID):
    card = await CardManager.block_card(request.auth, card_id)
    return CustomResponse.success(message="Card blocked permanently", data=card)


@card_router.post(
    "/card/{card_id}/activate",
    summary="Activate card",
    description="""
        Activate an inactive card to allow transactions.

        **Note:** New cards are created in INACTIVE status and must be activated.
    """,
    response={200: CardDataResponseSchema},
)
@invalidate_cache(patterns=["cards:detail:{{card_id}}:*", "cards:list:{{user_id}}:*"])
async def activate_card(request, card_id: UUID):
    card = await CardManager.activate_card(request.auth, card_id)
    return CustomResponse.success(message="Card activated successfully", data=card)


@card_router.patch(
    "/card/{card_id}/controls",
    summary="Update card transaction controls",
    description="""
        Update card transaction controls:
        - Allow/disallow online transactions
        - Allow/disallow ATM withdrawals
        - Allow/disallow international transactions
    """,
    response={200: CardDataResponseSchema},
)
async def update_card_controls(request, card_id: UUID, data: CardControlsSchema):
    update_data = UpdateCardSchema(**data.model_dump())
    card = await CardManager.update_card(request.auth, card_id, update_data)
    return CustomResponse.success(
        message="Card controls updated successfully", data=card
    )


@card_router.get(
    "/card/{card_id}/transactions",
    summary="Get card transactions",
    description="""
        Get transaction history for a specific card.

        **Includes:**
        - Card purchases
        - ATM withdrawals
        - Card funding
        - Refunds and reversals
    """,
    response={200: CardTransactionListResponseSchema},
)
@cacheable(key="cards:transactions:{{card_id}}:{{user_id}}", ttl=30)
async def get_card_transactions(
    request, card_id: UUID, page_params: PaginationQuerySchema = Query(...)
):
    result = await CardOperations.get_card_transactions(
        user=request.auth, card_id=card_id, page_params=page_params
    )
    return CustomResponse.success(
        message="Card transactions retrieved successfully", data=result
    )


@card_router.delete(
    "/card/{card_id}",
    summary="Delete card",
    description="""
        Delete/terminate a card.

        **Process:**
        1. Card is blocked first
        2. Card record is retained for transaction history

        **Note:** This is effectively the same as blocking a card.
    """,
    response={200: ResponseSchema},
)
@invalidate_cache(patterns=["cards:detail:{{card_id}}:*", "cards:list:{{user_id}}:*"])
async def delete_card(request, card_id: UUID):
    await CardManager.delete_card(request.auth, card_id)
    return CustomResponse.success(message="Card deleted successfully")
