from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from typing import List, Dict, Any, Optional
from dateutil.relativedelta import relativedelta

from apps.accounts.models import User
from apps.wallets.models import RecurringPayment, Wallet, WalletStatus, PaymentFrequency
from apps.common.exceptions import RequestError, ErrorCode
from apps.transactions.services.transaction_service import TransactionService
from apps.transactions.models import TransactionType, TransactionDirection


class RecurringPaymentService:
    """Service for managing recurring payments"""

    @staticmethod
    def _calculate_next_payment_date(
        current_date: timezone.datetime, frequency: str
    ) -> timezone.datetime:
        """Calculate the next payment date based on frequency"""

        if frequency == PaymentFrequency.DAILY:
            return current_date + timedelta(days=1)
        elif frequency == PaymentFrequency.WEEKLY:
            return current_date + timedelta(weeks=1)
        elif frequency == PaymentFrequency.MONTHLY:
            return current_date + relativedelta(months=1)
        elif frequency == PaymentFrequency.QUARTERLY:
            return current_date + relativedelta(months=3)
        elif frequency == PaymentFrequency.YEARLY:
            return current_date + relativedelta(years=1)
        else:
            raise ValueError(f"Invalid frequency: {frequency}")

    @staticmethod
    async def create_recurring_payment(
        user: User,
        from_wallet_id: str,
        amount: Decimal,
        frequency: str,
        description: str,
        start_date: timezone.datetime,
        to_wallet_id: str = None,
        to_external: str = None,
        end_date: timezone.datetime = None,
        reference: str = None,
    ) -> RecurringPayment:
        """Create a new recurring payment"""

        if amount <= 0:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Payment amount must be positive",
                status_code=400,
            )

        # Get source wallet
        try:
            from_wallet = await Wallet.objects.aget(wallet_id=from_wallet_id, user=user)
        except Wallet.DoesNotExist:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg="Source wallet not found",
                status_code=404,
            )

        if from_wallet.status != WalletStatus.ACTIVE:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Source wallet is not active",
                status_code=400,
            )

        # Validate destination
        to_wallet = None
        if to_wallet_id:
            try:
                to_wallet = await Wallet.objects.aget(wallet_id=to_wallet_id)
                if to_wallet.currency != from_wallet.currency:
                    raise RequestError(
                        err_code=ErrorCode.VALIDATION_ERROR,
                        err_msg="Currency mismatch between wallets",
                        status_code=400,
                    )
            except Wallet.DoesNotExist:
                raise RequestError(
                    err_code=ErrorCode.NOT_FOUND,
                    err_msg="Destination wallet not found",
                    status_code=404,
                )
        elif not to_external:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Either destination wallet or external account required",
                status_code=400,
            )

        # Validate dates
        if start_date <= timezone.now():
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Start date must be in the future",
                status_code=400,
            )

        if end_date and end_date <= start_date:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="End date must be after start date",
                status_code=400,
            )

        # Calculate next payment date
        next_payment_date = start_date

        # Create recurring payment
        recurring_payment = await RecurringPayment.objects.acreate(
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            to_external=to_external,
            amount=amount,
            frequency=frequency,
            description=description,
            start_date=start_date,
            end_date=end_date,
            next_payment_date=next_payment_date,
            reference=reference,
            is_active=True,
        )

        return recurring_payment

    @staticmethod
    async def get_user_recurring_payments(
        user: User, wallet_id: str = None, is_active: bool = None
    ) -> List[RecurringPayment]:
        """Get user's recurring payments"""

        filters = {"from_wallet__user": user}

        if wallet_id:
            filters["from_wallet__wallet_id"] = wallet_id
        if is_active is not None:
            filters["is_active"] = is_active

        payments = []
        async for payment in RecurringPayment.objects.filter(**filters).select_related(
            "from_wallet", "to_wallet", "from_wallet__currency"
        ):
            payments.append(payment)

        return payments

    @staticmethod
    async def get_recurring_payment(user: User, payment_id: str) -> RecurringPayment:
        """Get a specific recurring payment"""

        try:
            payment = await RecurringPayment.objects.select_related(
                "from_wallet", "to_wallet", "from_wallet__currency"
            ).aget(payment_id=payment_id, from_wallet__user=user)
        except RecurringPayment.DoesNotExist:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg="Recurring payment not found",
                status_code=404,
            )

        return payment

    @staticmethod
    async def update_recurring_payment(
        user: User,
        payment_id: str,
        amount: Decimal = None,
        frequency: str = None,
        description: str = None,
        end_date: timezone.datetime = None,
        is_active: bool = None,
    ) -> RecurringPayment:
        """Update recurring payment settings"""

        payment = await RecurringPaymentService.get_recurring_payment(user, payment_id)

        if amount is not None:
            if amount <= 0:
                raise RequestError(
                    err_code=ErrorCode.VALIDATION_ERROR,
                    err_msg="Payment amount must be positive",
                    status_code=400,
                )
            payment.amount = amount

        if frequency is not None:
            # Recalculate next payment date if frequency changes
            if payment.frequency != frequency:
                payment.frequency = frequency
                payment.next_payment_date = (
                    RecurringPaymentService._calculate_next_payment_date(
                        timezone.now(), frequency
                    )
                )

        if description is not None:
            payment.description = description

        if end_date is not None:
            if end_date <= timezone.now():
                raise RequestError(
                    err_code=ErrorCode.VALIDATION_ERROR,
                    err_msg="End date must be in the future",
                    status_code=400,
                )
            payment.end_date = end_date

        if is_active is not None:
            payment.is_active = is_active

        await payment.asave()
        return payment

    @staticmethod
    async def pause_recurring_payment(user: User, payment_id: str) -> RecurringPayment:
        """Pause a recurring payment"""

        payment = await RecurringPaymentService.get_recurring_payment(user, payment_id)
        payment.is_active = False
        await payment.asave()

        return payment

    @staticmethod
    async def resume_recurring_payment(user: User, payment_id: str) -> RecurringPayment:
        """Resume a paused recurring payment"""

        payment = await RecurringPaymentService.get_recurring_payment(user, payment_id)

        if payment.end_date and payment.end_date <= timezone.now():
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Cannot resume payment past its end date",
                status_code=400,
            )

        payment.is_active = True
        # Update next payment date to avoid immediate execution
        payment.next_payment_date = (
            RecurringPaymentService._calculate_next_payment_date(
                timezone.now(), payment.frequency
            )
        )
        await payment.asave()

        return payment

    @staticmethod
    async def cancel_recurring_payment(user: User, payment_id: str) -> RecurringPayment:
        """Cancel a recurring payment permanently"""

        payment = await RecurringPaymentService.get_recurring_payment(user, payment_id)
        payment.is_active = False
        payment.end_date = timezone.now()
        await payment.asave()

        return payment

    @staticmethod
    async def execute_recurring_payment(payment: RecurringPayment) -> Dict[str, Any]:
        """Execute a single recurring payment"""

        # Check if payment should still be executed
        if not payment.is_active:
            return {"status": "skipped", "reason": "Payment is inactive"}

        if payment.end_date and timezone.now() > payment.end_date:
            payment.is_active = False
            await payment.asave()
            return {"status": "skipped", "reason": "Payment has expired"}

        # Check wallet balance
        if payment.from_wallet.available_balance < payment.amount:
            payment.retry_count += 1
            if payment.auto_retry and payment.retry_count < payment.max_retries:
                # Retry later
                payment.next_payment_date = timezone.now() + timedelta(hours=1)
                await payment.asave()
                return {"status": "retrying", "reason": "Insufficient balance"}
            else:
                # Max retries reached or auto-retry disabled
                payment.is_active = False
                await payment.asave()
                return {
                    "status": "failed",
                    "reason": "Insufficient balance - max retries reached",
                }

        try:
            # Execute the payment
            from .wallet_operations import WalletOperations

            if payment.to_wallet:
                # Internal transfer
                transfer_result = await WalletOperations.transfer_between_wallets(
                    from_user=payment.from_wallet.user,
                    from_wallet_id=str(payment.from_wallet.wallet_id),
                    to_wallet_id=str(payment.to_wallet.wallet_id),
                    amount=payment.amount,
                    description=f"Recurring: {payment.description}",
                    reference=payment.reference,
                )
            else:
                # External payment (would integrate with external payment processor)
                # Capture balance before transaction
                balance_before = payment.from_wallet.balance

                # Debit the wallet
                await WalletOperations.update_balance(
                    payment.from_wallet,
                    payment.amount,
                    "debit",
                    f"Recurring external payment: {payment.description}",
                )

                # Create transaction record for external payment
                transaction_obj = await TransactionService.create_transaction(
                    transaction_type=TransactionType.WITHDRAWAL,
                    amount=payment.amount,
                    direction=TransactionDirection.OUTBOUND,
                    from_user=payment.from_wallet.user,
                    from_wallet_id=payment.from_wallet,
                    description=f"Recurring external payment: {payment.description}",
                    reference=payment.reference,
                    external_reference=payment.to_external,
                    from_balance_before=balance_before,
                    from_balance_after=payment.from_wallet.balance,
                    metadata={
                        "payment_type": "recurring_external",
                        "recurring_payment_id": str(payment.payment_id),
                        "external_account": payment.to_external,
                        "currency_code": payment.from_wallet.currency.code,
                    },
                    recurring_payment_id=payment.payment_id,
                )

                await TransactionService.complete_transaction(transaction_obj)

                transfer_result = {
                    "transfer_id": str(transaction_obj.transaction_id),
                    "external_account": payment.to_external,
                }

            # Update payment record
            payment.last_payment_at = timezone.now()
            payment.total_payments_made += 1
            payment.retry_count = 0  # Reset retry count on success

            # Calculate next payment date
            payment.next_payment_date = (
                RecurringPaymentService._calculate_next_payment_date(
                    payment.next_payment_date, payment.frequency
                )
            )

            # Check if this was the final payment
            if payment.end_date and payment.next_payment_date > payment.end_date:
                payment.is_active = False

            await payment.asave()

            return {
                "status": "success",
                "transfer_result": transfer_result,
                "next_payment_date": payment.next_payment_date.isoformat(),
                "payments_made": payment.total_payments_made,
            }

        except Exception as e:
            # Handle payment failure
            payment.retry_count += 1
            if payment.auto_retry and payment.retry_count < payment.max_retries:
                payment.next_payment_date = timezone.now() + timedelta(hours=1)
            else:
                payment.is_active = False

            await payment.asave()

            return {
                "status": "failed",
                "reason": str(e),
                "retry_count": payment.retry_count,
            }

    @staticmethod
    async def get_due_payments() -> List[RecurringPayment]:
        """Get recurring payments that are due for execution"""

        now = timezone.now()
        payments = []

        async for payment in RecurringPayment.objects.filter(
            is_active=True, next_payment_date__lte=now
        ).select_related("from_wallet", "to_wallet"):
            payments.append(payment)

        return payments

    @staticmethod
    async def process_due_payments() -> Dict[str, Any]:
        """Process all due recurring payments"""

        due_payments = await RecurringPaymentService.get_due_payments()

        results = {
            "total_processed": len(due_payments),
            "successful": 0,
            "failed": 0,
            "retrying": 0,
            "skipped": 0,
            "details": [],
        }

        for payment in due_payments:
            result = await RecurringPaymentService.execute_recurring_payment(payment)
            results["details"].append(
                {
                    "payment_id": str(payment.payment_id),
                    "description": payment.description,
                    "amount": payment.amount,
                    "status": result["status"],
                    "reason": result.get("reason", ""),
                }
            )

            if result["status"] == "success":
                results["successful"] += 1
            elif result["status"] == "failed":
                results["failed"] += 1
            elif result["status"] == "retrying":
                results["retrying"] += 1
            else:
                results["skipped"] += 1

        return results

    @staticmethod
    async def get_recurring_payment_details(
        user: User, payment_id: str
    ) -> Dict[str, Any]:
        """Get detailed recurring payment information"""

        payment = await RecurringPaymentService.get_recurring_payment(user, payment_id)

        return {
            "payment_id": str(payment.payment_id),
            "from_wallet": {
                "wallet_id": str(payment.from_wallet.wallet_id),
                "name": payment.from_wallet.name,
                "currency": payment.from_wallet.currency.code,
            },
            "to_wallet": (
                {
                    "wallet_id": str(payment.to_wallet.wallet_id),
                    "name": payment.to_wallet.name,
                    "owner": payment.to_wallet.user.email,
                }
                if payment.to_wallet
                else None
            ),
            "to_external": payment.to_external,
            "amount": payment.amount,
            "frequency": payment.frequency,
            "description": payment.description,
            "start_date": payment.start_date.isoformat(),
            "end_date": payment.end_date.isoformat() if payment.end_date else None,
            "next_payment_date": payment.next_payment_date.isoformat(),
            "last_payment_at": (
                payment.last_payment_at.isoformat() if payment.last_payment_at else None
            ),
            "total_payments_made": payment.total_payments_made,
            "is_active": payment.is_active,
            "auto_retry": payment.auto_retry,
            "retry_count": payment.retry_count,
            "max_retries": payment.max_retries,
            "reference": payment.reference,
            "created_at": payment.created_at.isoformat(),
        }

    @staticmethod
    async def get_payment_schedule(
        user: User, payment_id: str, next_n_payments: int = 12
    ) -> List[Dict[str, Any]]:
        """Get the upcoming payment schedule"""

        payment = await RecurringPaymentService.get_recurring_payment(user, payment_id)

        if not payment.is_active:
            return []

        schedule = []
        current_date = payment.next_payment_date

        for i in range(next_n_payments):
            if payment.end_date and current_date > payment.end_date:
                break

            schedule.append(
                {
                    "payment_number": payment.total_payments_made + i + 1,
                    "scheduled_date": current_date.isoformat(),
                    "amount": payment.amount,
                    "description": payment.description,
                }
            )

            current_date = RecurringPaymentService._calculate_next_payment_date(
                current_date, payment.frequency
            )

        return schedule

    @staticmethod
    async def get_recurring_payment_analytics(user: User) -> Dict[str, Any]:
        """Get recurring payment analytics for user"""

        total_payments = await RecurringPayment.objects.filter(
            from_wallet__user=user
        ).acount()
        active_payments = await RecurringPayment.objects.filter(
            from_wallet__user=user, is_active=True
        ).acount()

        # Calculate totals
        total_amount_per_period = Decimal("0")
        total_payments_made = 0

        async for payment in RecurringPayment.objects.filter(
            from_wallet__user=user, is_active=True
        ):
            total_amount_per_period += payment.amount
            total_payments_made += payment.total_payments_made

        # Calculate upcoming payments for next 30 days
        upcoming_payments = await RecurringPayment.objects.filter(
            from_wallet__user=user,
            is_active=True,
            next_payment_date__lte=timezone.now() + timedelta(days=30),
        ).acount()

        return {
            "total_recurring_payments": total_payments,
            "active_payments": active_payments,
            "inactive_payments": total_payments - active_payments,
            "total_amount_per_period": total_amount_per_period,
            "total_payments_executed": total_payments_made,
            "upcoming_payments_30_days": upcoming_payments,
            "average_payment_amount": total_amount_per_period / max(active_payments, 1),
        }
