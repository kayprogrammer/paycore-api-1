from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from typing import List, Dict, Any
import uuid

from apps.accounts.models import User
from apps.wallets.models import (
    SplitPayment,
    SplitPaymentParticipant,
    Currency,
    Wallet,
    WalletStatus,
    SplitPaymentType,
    SplitPaymentStatus,
    ParticipantStatus,
)
from apps.common.exceptions import RequestError, ErrorCode


class SplitPaymentService:
    """Service for managing split payments"""

    @staticmethod
    async def create_split_payment(
        creator: User,
        total_amount: Decimal,
        currency_code: str,
        description: str,
        participants: List[str],  # Email addresses
        split_type: str = "equal",
        custom_amounts: List[Decimal] = None,
        due_date: timezone.datetime = None,
    ) -> SplitPayment:
        """Create a new split payment request"""

        if total_amount <= 0:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Total amount must be positive",
                status_code=400,
            )

        # Get currency
        try:
            currency = await Currency.objects.aget(code=currency_code, is_active=True)
        except Currency.DoesNotExist:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg=f"Currency {currency_code} not found or inactive",
                status_code=404,
            )

        # Validate participants
        if len(participants) < 2:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="At least 2 participants required",
                status_code=400,
            )

        if len(participants) > 20:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Maximum 20 participants allowed",
                status_code=400,
            )

        # Remove duplicates and creator from participants
        unique_participants = list(set(participants))
        if creator.email in unique_participants:
            unique_participants.remove(creator.email)

        if len(unique_participants) == 0:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="No valid participants found",
                status_code=400,
            )

        # Validate custom amounts if provided
        if split_type == "custom" and custom_amounts:
            if len(custom_amounts) != len(unique_participants):
                raise RequestError(
                    err_code=ErrorCode.VALIDATION_ERROR,
                    err_msg="Custom amounts count must match participants count",
                    status_code=400,
                )

            if sum(custom_amounts) != total_amount:
                raise RequestError(
                    err_code=ErrorCode.VALIDATION_ERROR,
                    err_msg="Sum of custom amounts must equal total amount",
                    status_code=400,
                )

        # Create split payment
        async with transaction.atomic():
            split_payment = await SplitPayment.objects.acreate(
                created_by=creator,
                total_amount=total_amount,
                currency=currency,
                description=description,
                split_type=split_type,
                due_date=due_date,
                status=SplitPaymentStatus.PENDING,
            )

            # Calculate amounts for each participant
            if split_type == "equal":
                amount_per_person = total_amount / len(unique_participants)
                participant_amounts = [amount_per_person] * len(unique_participants)
            elif split_type == "custom":
                participant_amounts = custom_amounts
            else:  # percentage split
                # For percentage split, custom_amounts should contain percentages
                if not custom_amounts or sum(custom_amounts) != 100:
                    raise RequestError(
                        err_code=ErrorCode.VALIDATION_ERROR,
                        err_msg="Percentages must sum to 100",
                        status_code=400,
                    )
                participant_amounts = [(p / 100) * total_amount for p in custom_amounts]

            # Create participant records
            for i, email in enumerate(unique_participants):
                try:
                    participant_user = await User.objects.aget(email=email)
                except User.DoesNotExist:
                    # Create pending participant record even if user doesn't exist
                    participant_user = None

                amount_owed = participant_amounts[i]
                percentage = (
                    (amount_owed / total_amount) * 100
                    if split_type == "percentage"
                    else None
                )

                await SplitPaymentParticipant.objects.acreate(
                    split_payment=split_payment,
                    user=participant_user,
                    amount_owed=amount_owed,
                    percentage=percentage,
                    status=ParticipantStatus.PENDING,
                )

        return split_payment

    @staticmethod
    async def get_user_split_payments(
        user: User, status: str = None, as_creator: bool = None
    ) -> List[SplitPayment]:
        """Get split payments for a user"""

        filters = {}

        if as_creator is True:
            filters["created_by"] = user
        elif as_creator is False:
            filters["participants__user"] = user
        else:
            # Get both created and participated payments
            created_payments = []
            participated_payments = []

            async for payment in SplitPayment.objects.filter(created_by=user):
                created_payments.append(payment)

            async for payment in SplitPayment.objects.filter(
                participants__user=user
            ).distinct():
                participated_payments.append(payment)

            # Combine and remove duplicates
            all_payments = list(
                {p.id: p for p in created_payments + participated_payments}.values()
            )

            if status:
                all_payments = [p for p in all_payments if p.status == status]

            return all_payments

        if status:
            filters["status"] = status

        payments = []
        async for payment in SplitPayment.objects.filter(**filters).select_related(
            "currency", "created_by"
        ):
            payments.append(payment)

        return payments

    @staticmethod
    async def get_split_payment(payment_id: str, user: User = None) -> SplitPayment:
        """Get a specific split payment"""

        try:
            split_payment = await SplitPayment.objects.select_related(
                "currency", "created_by"
            ).aget(payment_id=payment_id)
        except SplitPayment.DoesNotExist:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg="Split payment not found",
                status_code=404,
            )

        # Check if user has access to this split payment
        if user:
            has_access = (
                split_payment.created_by.id == user.id
                or await SplitPaymentParticipant.objects.filter(
                    split_payment=split_payment, user=user
                ).aexists()
            )

            if not has_access:
                raise RequestError(
                    err_code=ErrorCode.UNAUTHORIZED_USER,
                    err_msg="Access denied to this split payment",
                    status_code=403,
                )

        return split_payment

    @staticmethod
    async def pay_split_payment(
        user: User,
        payment_id: str,
        wallet_id: str,
        amount: Decimal = None,
        pin: str = None,
    ) -> Dict[str, Any]:
        """Pay a portion of a split payment"""

        split_payment = await SplitPaymentService.get_split_payment(payment_id, user)

        if split_payment.status not in [
            SplitPaymentStatus.PENDING,
            SplitPaymentStatus.PARTIAL,
        ]:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Split payment is not available for payment",
                status_code=400,
            )

        # Get participant record
        try:
            participant = await SplitPaymentParticipant.objects.aget(
                split_payment=split_payment, user=user
            )
        except SplitPaymentParticipant.DoesNotExist:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg="You are not a participant in this split payment",
                status_code=404,
            )

        if participant.status == ParticipantStatus.PAID:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="You have already paid your portion",
                status_code=400,
            )

        # Determine payment amount
        payment_amount = amount or participant.amount_remaining

        if payment_amount <= 0:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Payment amount must be positive",
                status_code=400,
            )

        if payment_amount > participant.amount_remaining:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Payment amount exceeds remaining balance",
                status_code=400,
            )

        # Get creator's default wallet for the currency
        from .wallet_manager import WalletManager

        creator_wallet = await WalletManager.get_default_wallet(
            split_payment.created_by, split_payment.currency.code
        )

        if not creator_wallet:
            raise RequestError(
                err_code=ErrorCode.NOT_FOUND,
                err_msg="Creator's wallet not found for this currency",
                status_code=404,
            )

        # Process transfer
        from .wallet_operations import WalletOperations

        transfer_result = await WalletOperations.transfer_between_wallets(
            from_user=user,
            from_wallet_id=wallet_id,
            to_wallet_id=str(creator_wallet.wallet_id),
            amount=payment_amount,
            description=f"Split payment: {split_payment.description}",
            pin=pin,
            reference=f"SPLIT_{split_payment.payment_id}_{user.id}",
        )

        # Update participant record
        async with transaction.atomic():
            participant.amount_paid += payment_amount
            if participant.amount_paid >= participant.amount_owed:
                participant.status = ParticipantStatus.PAID
                participant.paid_at = timezone.now()
            await participant.asave()

            # Check if all participants have paid
            unpaid_count = await SplitPaymentParticipant.objects.filter(
                split_payment=split_payment,
                status__in=[ParticipantStatus.PENDING, ParticipantStatus.OVERDUE],
            ).acount()

            if unpaid_count == 0:
                split_payment.status = SplitPaymentStatus.COMPLETED
                split_payment.completed_at = timezone.now()
            elif split_payment.status == SplitPaymentStatus.PENDING:
                split_payment.status = SplitPaymentStatus.PARTIAL

            await split_payment.asave()

        return {
            "payment_id": transfer_result["transfer_id"],
            "split_payment_id": str(split_payment.payment_id),
            "amount_paid": payment_amount,
            "remaining_amount": participant.amount_remaining,
            "participant_status": participant.status,
            "split_payment_status": split_payment.status,
            "timestamp": timezone.now().isoformat(),
        }

    @staticmethod
    async def cancel_split_payment(user: User, payment_id: str) -> SplitPayment:
        """Cancel a split payment (creator only)"""

        split_payment = await SplitPaymentService.get_split_payment(payment_id, user)

        if split_payment.created_by.id != user.id:
            raise RequestError(
                err_code=ErrorCode.UNAUTHORIZED_USER,
                err_msg="Only the creator can cancel a split payment",
                status_code=403,
            )

        if split_payment.status not in [
            SplitPaymentStatus.PENDING,
            SplitPaymentStatus.PARTIAL,
        ]:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Cannot cancel completed or already cancelled split payment",
                status_code=400,
            )

        # Check if any payments have been made
        paid_participants = await SplitPaymentParticipant.objects.filter(
            split_payment=split_payment, amount_paid__gt=0
        ).acount()

        if paid_participants > 0:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Cannot cancel split payment with existing payments",
                status_code=400,
            )

        split_payment.status = SplitPaymentStatus.CANCELLED
        await split_payment.asave()

        return split_payment

    @staticmethod
    async def remind_participants(user: User, payment_id: str) -> Dict[str, Any]:
        """Send reminders to unpaid participants"""

        split_payment = await SplitPaymentService.get_split_payment(payment_id, user)

        if split_payment.created_by.id != user.id:
            raise RequestError(
                err_code=ErrorCode.UNAUTHORIZED_USER,
                err_msg="Only the creator can send reminders",
                status_code=403,
            )

        # Get unpaid participants
        unpaid_participants = []
        async for participant in SplitPaymentParticipant.objects.filter(
            split_payment=split_payment,
            status__in=[ParticipantStatus.PENDING, ParticipantStatus.OVERDUE],
        ).select_related("user"):
            participant.reminded_at = timezone.now()
            await participant.asave()
            unpaid_participants.append(participant)

        # Here you would send notification/email to participants
        # For now, just return the count

        return {
            "split_payment_id": str(split_payment.payment_id),
            "reminders_sent": len(unpaid_participants),
            "reminded_participants": [
                p.user.email for p in unpaid_participants if p.user
            ],
        }

    @staticmethod
    async def get_split_payment_details(
        payment_id: str, user: User = None
    ) -> Dict[str, Any]:
        """Get detailed split payment information"""

        split_payment = await SplitPaymentService.get_split_payment(payment_id, user)

        # Get participants
        participants = []
        async for participant in SplitPaymentParticipant.objects.filter(
            split_payment=split_payment
        ).select_related("user"):
            participants.append(
                {
                    "user_email": (
                        participant.user.email if participant.user else "Unknown"
                    ),
                    "user_name": (
                        participant.user.full_name if participant.user else "Unknown"
                    ),
                    "amount_owed": participant.amount_owed,
                    "amount_paid": participant.amount_paid,
                    "amount_remaining": participant.amount_remaining,
                    "percentage": participant.percentage,
                    "status": participant.status,
                    "paid_at": (
                        participant.paid_at.isoformat() if participant.paid_at else None
                    ),
                }
            )

        return {
            "payment_id": str(split_payment.payment_id),
            "creator": {
                "email": split_payment.created_by.email,
                "name": split_payment.created_by.full_name,
            },
            "total_amount": split_payment.total_amount,
            "currency": {
                "code": split_payment.currency.code,
                "symbol": split_payment.currency.symbol,
                "name": split_payment.currency.name,
            },
            "description": split_payment.description,
            "split_type": split_payment.split_type,
            "status": split_payment.status,
            "participants": participants,
            "due_date": (
                split_payment.due_date.isoformat() if split_payment.due_date else None
            ),
            "completed_at": (
                split_payment.completed_at.isoformat()
                if split_payment.completed_at
                else None
            ),
            "created_at": split_payment.created_at.isoformat(),
        }

    @staticmethod
    async def get_split_payment_analytics(user: User) -> Dict[str, Any]:
        """Get split payment analytics for user"""

        # Created payments
        created_payments = await SplitPayment.objects.filter(created_by=user).acount()
        created_completed = await SplitPayment.objects.filter(
            created_by=user, status=SplitPaymentStatus.COMPLETED
        ).acount()

        # Participated payments
        participated_payments = await SplitPaymentParticipant.objects.filter(
            user=user
        ).acount()
        participated_paid = await SplitPaymentParticipant.objects.filter(
            user=user, status=ParticipantStatus.PAID
        ).acount()

        # Calculate totals
        total_created_amount = Decimal("0")
        total_owed_amount = Decimal("0")
        total_paid_amount = Decimal("0")

        async for payment in SplitPayment.objects.filter(created_by=user):
            total_created_amount += payment.total_amount

        async for participant in SplitPaymentParticipant.objects.filter(user=user):
            total_owed_amount += participant.amount_owed
            total_paid_amount += participant.amount_paid

        return {
            "created_payments": {
                "total": created_payments,
                "completed": created_completed,
                "completion_rate": (created_completed / max(created_payments, 1)) * 100,
                "total_amount": total_created_amount,
            },
            "participated_payments": {
                "total": participated_payments,
                "paid": participated_paid,
                "payment_rate": (participated_paid / max(participated_payments, 1))
                * 100,
                "total_owed": total_owed_amount,
                "total_paid": total_paid_amount,
                "outstanding": total_owed_amount - total_paid_amount,
            },
        }
