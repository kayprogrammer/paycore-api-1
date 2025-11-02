import time
from decimal import Decimal
from apps.common.decorators import aatomic
from apps.payments.models import (
    Payment,
    PaymentStatus,
    InvoiceStatus,
)
from apps.wallets.models import Wallet
from apps.transactions.models import Transaction, TransactionType, TransactionStatus
from apps.common.exceptions import (
    BodyValidationError,
    RequestError,
    ErrorCode,
)
from apps.payments.schemas import MakePaymentSchema
from apps.payments.services.payment_link_manager import PaymentLinkManager
from apps.payments.services.invoice_manager import InvoiceManager


class PaymentProcessor:
    """Service for processing payments"""

    PAYMENT_FEE_PERCENTAGE = Decimal("0.015")  # 1.5% fee
    PAYMENT_FEE_CAP = Decimal("1000.00")  # Cap at 1000

    @staticmethod
    def calculate_fee(amount: Decimal) -> Decimal:
        fee = amount * PaymentProcessor.PAYMENT_FEE_PERCENTAGE
        return min(fee, PaymentProcessor.PAYMENT_FEE_CAP)

    @staticmethod
    @aatomic
    async def process_payment_link_payment(
        link_slug: str, data: MakePaymentSchema
    ) -> Payment:
        link = await PaymentLinkManager.get_payment_link_by_slug(link_slug)
        await PaymentLinkManager.validate_payment_link(link)
        if link.is_amount_fixed:
            amount = link.amount
        else:
            if not data.amount:
                raise BodyValidationError(
                    "amount", "Amount is required for this payment link"
                )
            amount = data.amount

            if link.min_amount and amount < link.min_amount:
                raise BodyValidationError(
                    "amount", f"Amount must be at least {link.min_amount}"
                )
            if link.max_amount and amount > link.max_amount:
                raise BodyValidationError(
                    "amount", f"Amount cannot exceed {link.max_amount}"
                )

        payer_wallet = await Wallet.objects.select_related(
            "currency", "user"
        ).aget_or_none(wallet_id=data.wallet_id)
        if not payer_wallet:
            raise BodyValidationError("wallet_id", "Wallet not found")
        if payer_wallet.currency_id != link.wallet.currency_id:
            raise BodyValidationError(
                "wallet_id", "Wallet currency must match payment link currency"
            )

        # Calculate fee and net amount
        fee_amount = PaymentProcessor.calculate_fee(amount)
        net_amount = amount - fee_amount
        total_amount = amount

        # Check balance
        if payer_wallet.balance < total_amount:
            raise BodyValidationError(
                "wallet_id",
                f"Insufficient balance. Required: {total_amount}, Available: {payer_wallet.balance}",
            )

        # Generate reference
        reference = f"PAY-{int(time.time())}-{link.link_id.hex[:8]}"

        # Debit payer wallet
        balance_before = payer_wallet.balance
        payer_wallet.balance -= total_amount
        await payer_wallet.asave(update_fields=["balance", "updated_at"])
        balance_after = payer_wallet.balance

        # Credit merchant wallet
        merchant_wallet = link.wallet
        merchant_balance_before = merchant_wallet.balance
        merchant_wallet.balance += net_amount
        await merchant_wallet.asave(update_fields=["balance", "updated_at"])
        merchant_balance_after = merchant_wallet.balance

        # Create transaction record
        transaction = await Transaction.objects.acreate(
            from_user=payer_wallet.user,
            from_wallet=payer_wallet,
            to_wallet=merchant_wallet,
            to_user=link.user,
            transaction_type=TransactionType.PAYMENT,
            amount=total_amount,
            status=TransactionStatus.COMPLETED,
            from_balance_before=balance_before,
            from_balance_after=balance_after,
            to_balance_before=merchant_balance_before,
            to_balance_after=merchant_balance_after,
            fee_amount=fee_amount,
            net_amount=net_amount,
            description=f"Payment: {link.title}",
            external_reference=reference,
        )

        # Create payment record
        payment = await Payment.objects.acreate(
            payment_link=link,
            payer_name=data.payer_name,
            payer_email=data.payer_email,
            payer_phone=data.payer_phone,
            payer_wallet=payer_wallet,
            merchant_user=link.user,
            merchant_wallet=merchant_wallet,
            amount=amount,
            fee_amount=fee_amount,
            net_amount=net_amount,
            status=PaymentStatus.COMPLETED,
            reference=reference,
            transaction=transaction,
        )

        # Update payment link stats
        link.payments_count += 1
        link.total_collected += amount
        if link.is_single_use:
            link.status = "completed"
        await link.asave(
            update_fields=["payments_count", "total_collected", "status", "updated_at"]
        )
        return payment

    @staticmethod
    @aatomic
    async def process_invoice_payment(
        invoice_number: str, data: MakePaymentSchema
    ) -> Payment:
        invoice = await InvoiceManager.get_invoice_by_number(invoice_number)
        if invoice.status == InvoiceStatus.PAID:
            raise RequestError(
                ErrorCode.INVOICE_ALREADY_PAID, "This invoice is already paid"
            )
        if invoice.status == InvoiceStatus.CANCELLED:
            raise RequestError(ErrorCode.NOT_ALLOWED, "This invoice has been cancelled")

        amount = data.amount if data.amount else invoice.amount_due
        if amount > invoice.amount_due:
            raise BodyValidationError(
                "amount",
                f"Amount cannot exceed invoice due amount of {invoice.amount_due}",
            )

        payer_wallet = await Wallet.objects.select_related(
            "currency", "user"
        ).aget_or_none(wallet_id=data.wallet_id)
        if not payer_wallet:
            raise BodyValidationError("wallet_id", "Wallet not found")

        if payer_wallet.currency_id != invoice.wallet.currency_id:
            raise BodyValidationError(
                "wallet_id", "Wallet currency must match invoice currency"
            )

        fee_amount = PaymentProcessor.calculate_fee(amount)
        net_amount = amount - fee_amount
        total_amount = amount

        if payer_wallet.balance < total_amount:
            raise BodyValidationError(
                "wallet_id",
                f"Insufficient balance. Required: {total_amount}, Available: {payer_wallet.balance}",
            )

        reference = f"INV-PAY-{int(time.time())}-{invoice.invoice_id.hex[:8]}"

        # Process payment (debit/credit wallets)
        balance_before = payer_wallet.balance
        payer_wallet.balance -= total_amount
        await payer_wallet.asave(update_fields=["balance", "updated_at"])
        balance_after = payer_wallet.balance

        merchant_wallet = invoice.wallet
        merchant_balance_before = merchant_wallet.balance
        merchant_wallet.balance += net_amount
        await merchant_wallet.asave(update_fields=["balance", "updated_at"])
        merchant_balance_after = merchant_wallet.balance

        # Create transaction
        transaction = await Transaction.objects.acreate(
            from_user=payer_wallet.user,
            from_wallet=payer_wallet,
            to_user=invoice.user,
            to_wallet=merchant_wallet,
            transaction_type=TransactionType.PAYMENT,
            amount=total_amount,
            status=TransactionStatus.COMPLETED,
            from_balance_before=balance_before,
            from_balance_after=balance_after,
            to_balance_before=merchant_balance_before,
            to_balance_after=merchant_balance_after,
            fee_amount=fee_amount,
            net_amount=net_amount,
            description=f"Invoice Payment: {invoice.invoice_number}",
            external_reference=reference,
        )

        # Create payment record
        payment = await Payment.objects.acreate(
            invoice=invoice,
            payer_name=data.payer_name or invoice.customer_name,
            payer_email=data.payer_email or invoice.customer_email,
            payer_phone=data.payer_phone or invoice.customer_phone,
            payer_wallet=payer_wallet,
            merchant_user=invoice.user,
            merchant_wallet=merchant_wallet,
            amount=amount,
            fee_amount=fee_amount,
            net_amount=net_amount,
            status=PaymentStatus.COMPLETED,
            reference=reference,
            transaction=transaction,
        )

        await InvoiceManager.mark_invoice_paid(invoice, amount)
        return payment
