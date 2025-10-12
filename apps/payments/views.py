from uuid import UUID
from typing import Optional
from ninja import Query, Router

from apps.accounts.auth import AuthUser
from apps.common.exceptions import NotFoundError
from apps.common.paginators import Paginator
from apps.common.responses import CustomResponse
from apps.common.schemas import PaginationQuerySchema
from apps.payments.schemas import (
    CreatePaymentLinkSchema,
    UpdatePaymentLinkSchema,
    PaymentLinkDataResponseSchema,
    PaymentLinkListDataResponseSchema,
    CreateInvoiceSchema,
    UpdateInvoiceSchema,
    InvoiceDataResponseSchema,
    InvoiceListDataResponseSchema,
    MakePaymentSchema,
    PaymentDataResponseSchema,
    PaymentListDataResponseSchema,
)
from apps.payments.services.payment_link_manager import PaymentLinkManager
from apps.payments.services.invoice_manager import InvoiceManager
from apps.payments.services.payment_processor import PaymentProcessor
from apps.payments.models import Payment
from apps.wallets.schemas import CurrencySchema


payment_router = Router(tags=["Payments"])


# ==================== PAYMENT LINKS ====================


@payment_router.post(
    "/links/create",
    summary="Create payment link",
    response={201: PaymentLinkDataResponseSchema},
    auth=AuthUser(),
)
async def create_payment_link(request, data: CreatePaymentLinkSchema):
    user = request.auth
    link_data = await PaymentLinkManager.create_payment_link(user, data)
    return CustomResponse.success("Payment link created successfully", link_data, 201)


@payment_router.get(
    "/links/list",
    summary="List payment links",
    response={200: PaymentLinkListDataResponseSchema},
    auth=AuthUser(),
)
async def list_payment_links(
    request,
    status: Optional[str] = None,
    page_params: PaginationQuerySchema = Query(...),
):
    user = request.auth
    links_data = await PaymentLinkManager.list_payment_links(user, status, page_params)
    return CustomResponse.success("Payment links retrieved successfully", links_data)


@payment_router.get(
    "/links/{link_id}",
    summary="Get payment link details",
    response={200: PaymentLinkDataResponseSchema},
    auth=AuthUser(),
)
async def get_payment_link(request, link_id: UUID):
    user = request.auth
    link = await PaymentLinkManager.get_payment_link(user, link_id)
    return CustomResponse.success("Payment link retrieved successfully", link)


@payment_router.put(
    "/links/{link_id}",
    summary="Update payment link",
    response={200: PaymentLinkDataResponseSchema},
    auth=AuthUser(),
)
async def update_payment_link(request, link_id: UUID, data: UpdatePaymentLinkSchema):
    user = request.auth
    link = await PaymentLinkManager.update_payment_link(user, link_id, data)
    return CustomResponse.success("Payment link updated successfully", link)


@payment_router.delete(
    "/links/{link_id}",
    summary="Delete payment link",
    response={200: dict},
    auth=AuthUser(),
)
async def delete_payment_link(request, link_id: UUID):
    user = request.auth
    await PaymentLinkManager.delete_payment_link(user, link_id)
    return CustomResponse.success("Payment link deleted successfully")


# ==================== PUBLIC PAYMENT ENDPOINTS ====================


@payment_router.get(
    "/pay/{slug}",
    summary="Get payment link by slug (public)",
    response={200: PaymentLinkDataResponseSchema},
    auth=None,
)
async def get_payment_link_public(request, slug: str):
    link = await PaymentLinkManager.get_payment_link_by_slug(slug)
    return CustomResponse.success("Payment link retrieved successfully", link)


@payment_router.post(
    "/pay/{slug}",
    summary="Make payment via payment link",
    response={201: PaymentDataResponseSchema},
    auth=None,
)
async def pay_via_link(request, slug: str, data: MakePaymentSchema):
    payment = await PaymentProcessor.process_payment_link_payment(slug, data)

    payment = await Payment.objects.select_related(
        "payment_link",
        "payer_wallet",
        "payer_wallet__currency",
        "merchant_wallet",
        "merchant_wallet__currency",
        "transaction",
    ).aget_or_none(payment_id=payment.payment_id)
    return CustomResponse.success("Payment completed successfully", payment, 201)


# ==================== INVOICES ====================


@payment_router.post(
    "/invoices/create",
    summary="Create invoice",
    response={201: InvoiceDataResponseSchema},
    auth=AuthUser(),
)
async def create_invoice(request, data: CreateInvoiceSchema):
    user = request.auth
    invoice = await InvoiceManager.create_invoice(user, data)
    invoice = await InvoiceManager.get_invoice(user, invoice.invoice_id)
    return CustomResponse.success("Invoice created successfully", invoice, 201)


@payment_router.get(
    "/invoices/list",
    summary="List invoices",
    response={200: InvoiceListDataResponseSchema},
    auth=AuthUser(),
)
async def list_invoices(
    request,
    status: Optional[str] = None,
    page_params: PaginationQuerySchema = Query(...),
):
    user = request.auth
    invoices_data = await InvoiceManager.list_invoices(user, status, page_params)
    return CustomResponse.success("Invoices retrieved successfully", invoices_data)


@payment_router.get(
    "/invoices/{invoice_id}",
    summary="Get invoice details",
    response={200: InvoiceDataResponseSchema},
    auth=AuthUser(),
)
async def get_invoice(request, invoice_id: UUID):
    user = request.auth
    invoice = await InvoiceManager.get_invoice(user, invoice_id)
    return CustomResponse.success("Invoice retrieved successfully", invoice)


@payment_router.put(
    "/invoices/{invoice_id}",
    summary="Update invoice",
    response={200: InvoiceDataResponseSchema},
    auth=AuthUser(),
)
async def update_invoice(request, invoice_id: UUID, data: UpdateInvoiceSchema):
    user = request.auth
    invoice = await InvoiceManager.update_invoice(user, invoice_id, data)
    return CustomResponse.success("Invoice updated successfully", invoice)


@payment_router.delete(
    "/invoices/{invoice_id}",
    summary="Delete invoice",
    response={200: dict},
    auth=AuthUser(),
)
async def delete_invoice(request, invoice_id: UUID):
    user = request.auth
    await InvoiceManager.delete_invoice(user, invoice_id)
    return CustomResponse.success("Invoice deleted successfully")


# ==================== PUBLIC INVOICE PAYMENT ====================


@payment_router.get(
    "/invoice/{invoice_number}",
    summary="Get invoice by number (public)",
    response={200: InvoiceDataResponseSchema},
)
async def get_invoice_public(request, invoice_number: str):
    invoice = await InvoiceManager.get_invoice_by_number(invoice_number)
    return CustomResponse.success("Invoice retrieved successfully", invoice)


@payment_router.post(
    "/invoice/{invoice_number}/pay",
    summary="Pay invoice",
    response={201: PaymentDataResponseSchema},
    auth=None,
)
async def pay_invoice(request, invoice_number: str, data: MakePaymentSchema):
    payment = await PaymentProcessor.process_invoice_payment(invoice_number, data)

    payment = await Payment.objects.select_related(
        "invoice",
        "payer_wallet",
        "payer_wallet__currency",
        "merchant_wallet",
        "merchant_wallet__currency",
        "transaction",
    ).aget_or_none(payment_id=payment.payment_id)
    return CustomResponse.success("Payment completed successfully", payment, 201)


# ==================== PAYMENT HISTORY ====================
@payment_router.get(
    "/payments/list",
    summary="List merchant payments",
    response={200: PaymentListDataResponseSchema},
    auth=AuthUser(),
)
async def list_merchant_payments(
    request,
    status: Optional[str] = None,
    page_params: PaginationQuerySchema = Query(...),
):
    user = request.auth
    queryset = Payment.objects.filter(merchant_user=user).select_related(
        "payer_wallet",
        "payer_wallet__currency",
        "merchant_wallet",
        "merchant_wallet__currency",
        "payment_link",
        "invoice",
        "transaction",
    )
    if status:
        queryset = queryset.filter(status=status)

    paginated_payments_data = await Paginator.paginate(
        queryset, page_params.page, page_params.limit
    )
    return CustomResponse.success(
        "Payments retrieved successfully", paginated_payments_data
    )


@payment_router.get(
    "/payments/{payment_id}",
    summary="Get payment details",
    response={200: PaymentDataResponseSchema},
    auth=AuthUser(),
)
async def get_payment(request, payment_id: UUID):
    user = request.auth

    payment = await Payment.objects.select_related(
        "payer_wallet",
        "payer_wallet__currency",
        "merchant_wallet",
        "merchant_wallet__currency",
        "payment_link",
        "invoice",
        "transaction",
    ).aget_or_none(payment_id=payment_id, merchant_user=user)

    if not payment:
        raise NotFoundError("Payment not found")
    return CustomResponse.success("Payment retrieved successfully", payment)
