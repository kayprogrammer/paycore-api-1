from uuid import UUID
from typing import Optional

from apps.accounts.models import User
from apps.common.paginators import Paginator
from apps.common.schemas import PaginationQuerySchema
from apps.common.utils import set_dict_attr
from apps.payments.models import PaymentLink, PaymentLinkStatus
from apps.wallets.models import Wallet
from apps.common.exceptions import (
    NotFoundError,
    BodyValidationError,
    RequestError,
    ErrorCode,
)
from apps.payments.schemas import CreatePaymentLinkSchema, UpdatePaymentLinkSchema


class PaymentLinkManager:
    """Service for managing payment links"""

    @staticmethod
    async def create_payment_link(
        user: User, data: CreatePaymentLinkSchema
    ) -> PaymentLink:
        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=data.wallet_id, user=user
        )
        if not wallet:
            raise NotFoundError("Wallet not found")

        if data.is_amount_fixed and not data.amount:
            raise BodyValidationError(
                "amount", "Amount is required when is_amount_fixed is True"
            )

        if not data.is_amount_fixed:
            if not data.min_amount:
                raise BodyValidationError(
                    "min_amount", "Min amount is required for flexible amounts"
                )
            if data.max_amount and data.max_amount < data.min_amount:
                raise BodyValidationError(
                    "max_amount", "Max amount must be greater than min amount"
                )

        data_to_save = data.model_dump()
        data_to_save.pop("wallet_id")
        link = await PaymentLink.objects.acreate(
            user=user, wallet=wallet, **data_to_save
        )
        return link

    @staticmethod
    async def get_payment_link(user: User, link_id: UUID) -> PaymentLink:
        link = await PaymentLink.objects.select_related(
            "wallet", "wallet__currency"
        ).aget_or_none(link_id=link_id, user=user)
        if not link:
            raise NotFoundError("Payment link not found")
        return link

    @staticmethod
    async def get_payment_link_by_slug(slug: str) -> PaymentLink:
        link = await PaymentLink.objects.select_related(
            "wallet", "wallet__currency", "user"
        ).aget_or_none(slug=slug)
        if not link:
            raise NotFoundError("Payment link not found")

        # Increment views
        link.views_count += 1
        await link.asave(update_fields=["views_count", "updated_at"])
        return link

    @staticmethod
    async def list_payment_links(
        user: User,
        status: Optional[PaymentLinkStatus] = None,
        page_params: PaginationQuerySchema = None,
    ):
        queryset = PaymentLink.objects.filter(user=user).select_related(
            "wallet", "wallet__currency"
        )
        if status:
            queryset = queryset.filter(status=status)
        paginated_data = await Paginator.paginate_queryset(
            queryset, page_params.page, page_params.limit
        )
        return paginated_data

    @staticmethod
    async def update_payment_link(
        user: User, link_id: UUID, data: UpdatePaymentLinkSchema
    ) -> PaymentLink:
        link = await PaymentLinkManager.get_payment_link(user, link_id)

        # Don't allow updates to completed/expired links
        if link.status in [PaymentLinkStatus.COMPLETED, PaymentLinkStatus.EXPIRED]:
            raise RequestError(
                ErrorCode.NOT_ALLOWED,
                "Cannot update completed or expired payment links",
            )

        # Update fields
        data_to_update = data.model_dump(exclude_unset=True)
        update_fields = list(data_to_update.keys()) + ["updated_at"]
        link = set_dict_attr(link, data_to_update)
        await link.asave(update_fields=update_fields)
        return link

    @staticmethod
    async def delete_payment_link(user: User, link_id: UUID) -> None:
        link = await PaymentLinkManager.get_payment_link(user, link_id)
        link.status = PaymentLinkStatus.INACTIVE
        await link.asave(update_fields=["status", "updated_at"])

    @staticmethod
    async def validate_payment_link(link: PaymentLink) -> None:
        if link.status != PaymentLinkStatus.ACTIVE:
            raise RequestError(
                ErrorCode.PAYMENT_LINK_INACTIVE, "This payment link is no longer active"
            )

        if link.is_expired:
            if link.status != PaymentLinkStatus.EXPIRED:
                link.status = PaymentLinkStatus.EXPIRED
                await link.asave(update_fields=["status", "updated_at"])
            raise RequestError(
                ErrorCode.PAYMENT_LINK_EXPIRED, "This payment link has expired"
            )

        if link.is_single_use and link.payments_count > 0:
            raise RequestError(
                ErrorCode.PAYMENT_LINK_INACTIVE,
                "This payment link is single-use and has already been used",
            )
