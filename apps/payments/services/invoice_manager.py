import time
from uuid import UUID
from typing import List, Optional
from decimal import Decimal
from django.utils import timezone

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.paginators import Paginator
from apps.common.schemas import PaginationQuerySchema
from apps.common.utils import set_dict_attr
from apps.payments.models import Invoice, InvoiceItem, InvoiceStatus
from apps.wallets.models import Wallet
from apps.common.exceptions import (
    NotFoundError,
    RequestError,
    ErrorCode,
    BodyValidationError,
)
from apps.payments.schemas import CreateInvoiceSchema, UpdateInvoiceSchema


class InvoiceManager:
    """Service for managing invoices"""

    @staticmethod
    async def generate_invoice_number() -> str:
        timestamp = int(time.time())
        count = await Invoice.objects.acount()
        return f"INV-{timestamp}-{count + 1:04d}"

    @staticmethod
    @aatomic
    async def create_invoice(user: User, data: CreateInvoiceSchema) -> Invoice:
        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=data.wallet_id, user=user
        )
        if not wallet:
            raise BodyValidationError("wallet_id", "Wallet not found")

        subtotal = sum(item.quantity * item.unit_price for item in data.items)
        total_amount = subtotal + data.tax_amount - data.discount_amount
        amount_due = total_amount
        invoice_number = await InvoiceManager.generate_invoice_number()

        data_to_add = data.model_dump(exclude=["wallet_id"])
        items = data_to_add.pop("items")
        invoice = await Invoice.objects.acreate(
            user=user,
            wallet=wallet,
            invoice_number=invoice_number,
            amount_due=amount_due,
            subtotal=subtotal,
            total_amount=total_amount,
            **data_to_add,
        )

        # Create invoice items
        items_to_create = [
            InvoiceItem(
                invoice=invoice,
                amount=item.get("quantity", 1) * item.get("unit_price"),
                **item,
            )
            for item in items
        ]
        await InvoiceItem.objects.abulk_create(items_to_create)
        return invoice

    @staticmethod
    async def get_invoice(user: User, invoice_id: UUID) -> Invoice:
        invoice = (
            await Invoice.objects.select_related(
                "user", "wallet", "wallet__currency", "payment_link"
            )
            .prefetch_related("items")
            .aget_or_none(invoice_id=invoice_id, user=user)
        )

        if not invoice:
            raise NotFoundError("Invoice not found")
        return invoice

    @staticmethod
    async def get_invoice_by_number(invoice_number: str) -> Invoice:
        invoice = (
            await Invoice.objects.select_related(
                "wallet", "wallet__currency", "user", "payment_link"
            )
            .prefetch_related("items")
            .aget_or_none(invoice_number=invoice_number)
        )
        if not invoice:
            raise NotFoundError("Invoice not found")
        return invoice

    @staticmethod
    async def list_invoices(
        user: User,
        status: Optional[str] = None,
        page_params: PaginationQuerySchema = None,
    ) -> List[Invoice]:
        queryset = (
            Invoice.objects.filter(user=user)
            .select_related("user", "wallet", "wallet__currency")
            .prefetch_related("items")
        )

        if status:
            queryset = queryset.filter(status=status)
        invoice_data = await Paginator.paginate_queryset(
            queryset, page_params.page, page_params.limit
        )
        return invoice_data

    @staticmethod
    async def update_invoice(
        user: User, invoice_id: UUID, data: UpdateInvoiceSchema
    ) -> Invoice:
        invoice = await InvoiceManager.get_invoice(user, invoice_id)

        if invoice.status != InvoiceStatus.DRAFT:
            if data.status or data.notes:
                update_fields = ["updated_at"]
                if data.status:
                    invoice.status = data.status
                    update_fields.append("status")
                if data.notes:
                    invoice.notes = data.notes
                    update_fields.append("notes")
                await invoice.asave(update_fields=update_fields)
                return invoice
            else:
                raise RequestError(
                    ErrorCode.NOT_ALLOWED,
                    "Can only update status and notes for non-draft invoices",
                )

        # Update draft invoice
        data_to_update = data.model_dump(exclude_unset=True)
        update_fields = ["updated_at"] + list(data_to_update.keys())
        invoice = set_dict_attr(invoice, data_to_update)
        await invoice.asave(update_fields=update_fields)
        return invoice

    @staticmethod
    async def delete_invoice(user: User, invoice_id: UUID) -> None:
        invoice = await InvoiceManager.get_invoice(user, invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise RequestError(
                ErrorCode.NOT_ALLOWED,
                "Can only delete draft invoices",
            )
        await invoice.adelete()

    @staticmethod
    async def mark_invoice_paid(invoice: Invoice, amount_paid: Decimal) -> None:
        invoice.amount_paid += amount_paid
        invoice.amount_due = invoice.total_amount - invoice.amount_paid

        if invoice.amount_due <= 0:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = timezone.now()
        elif invoice.amount_paid > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        await invoice.asave(
            update_fields=[
                "amount_paid",
                "amount_due",
                "status",
                "paid_at",
                "updated_at",
            ]
        )
