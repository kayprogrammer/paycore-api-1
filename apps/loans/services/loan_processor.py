from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, F, Case, When, DecimalField, Count, Min, Q
from django.db.models.functions import Coalesce
import secrets

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.paginators import Paginator
from apps.common.schemas import PaginationQuerySchema
from apps.loans.models import (
    LoanApplication,
    LoanStatus,
    LoanRepayment,
    LoanRepaymentSchedule,
    RepaymentStatus,
)
from apps.wallets.models import Wallet
from apps.transactions.models import Transaction, TransactionType, TransactionStatus
from apps.common.exceptions import (
    NotFoundError,
    BodyValidationError,
    RequestError,
    ErrorCode,
)
from apps.loans.schemas import MakeLoanRepaymentSchema
from apps.loans.services.credit_score_service import CreditScoreService
from apps.notifications.services.dispatcher import (
    UnifiedNotificationDispatcher,
    NotificationChannel,
    NotificationEventType,
)
from apps.notifications.models import NotificationPriority
from asgiref.sync import sync_to_async


class LoanProcessor:
    """Service for processing loan disbursements and repayments"""

    @staticmethod
    @aatomic
    async def disburse_loan(application_id, admin_user: User = None) -> LoanApplication:
        loan = await LoanApplication.objects.select_related(
            "user", "wallet", "wallet__currency", "loan_product"
        ).aget_or_none(application_id=application_id)

        if not loan:
            raise NotFoundError("Loan application not found")

        if loan.status != LoanStatus.APPROVED:
            raise RequestError(
                ErrorCode.LOAN_NOT_APPROVED,
                f"Loan must be approved before disbursement. Current status: {loan.status}",
            )

        if loan.disbursed_at:
            raise RequestError(
                ErrorCode.LOAN_ALREADY_DISBURSED, "Loan has already been disbursed"
            )

        wallet = loan.wallet
        wallet.balance += loan.approved_amount
        wallet.available_balance += loan.approved_amount
        await wallet.asave(update_fields=["balance", "available_balance", "updated_at"])

        transaction_ref = (
            f"LOAN-{int(timezone.now().timestamp())}-{secrets.token_urlsafe(8)}"
        )
        transaction = await Transaction.objects.acreate(
            to_user=loan.user,
            to_wallet=wallet,
            transaction_type=TransactionType.LOAN_DISBURSEMENT,
            amount=loan.approved_amount,
            net_amount=loan.approved_amount,
            to_balance_before=wallet.balance - loan.approved_amount,
            to_balance_after=wallet.balance,
            reference=transaction_ref,
            status=TransactionStatus.COMPLETED,
            description=f"Loan disbursement for {loan.loan_product.name}",
            metadata={
                "loan_id": str(loan.application_id),
                "loan_product": loan.loan_product.name,
                "tenure_months": loan.tenure_months,
                "interest_rate": str(loan.interest_rate),
            },
        )

        loan.status = LoanStatus.ACTIVE
        loan.disbursed_at = timezone.now()
        loan.disbursement_transaction = transaction
        await loan.asave(
            update_fields=[
                "status",
                "disbursed_at",
                "disbursement_transaction",
                "updated_at",
            ]
        )

        # Send loan disbursement notification (in-app, push, email)
        await sync_to_async(UnifiedNotificationDispatcher.dispatch)(
            user=loan.user,
            event_type=NotificationEventType.LOAN_DISBURSED,
            channels=[
                NotificationChannel.IN_APP,
                NotificationChannel.PUSH,
                NotificationChannel.EMAIL,
            ],
            title="Loan Disbursed!",
            message=f"Your loan of {wallet.currency.symbol}{loan.approved_amount:,.2f} has been disbursed to your wallet",
            context_data={"loan_id": str(loan.application_id)},
            priority=NotificationPriority.HIGH,
            related_object_type="Loan",
            related_object_id=str(loan.application_id),
            action_url=f"/loans/{loan.application_id}",
        )

        return loan

    @staticmethod
    @aatomic
    async def make_repayment(
        user: User, application_id, data: MakeLoanRepaymentSchema
    ) -> LoanRepayment:
        loan = await LoanApplication.objects.select_related(
            "user", "wallet", "wallet__currency", "loan_product"
        ).aget_or_none(application_id=application_id, user=user)

        if not loan:
            raise NotFoundError("Loan application not found")
        if not loan.is_active:
            raise RequestError(
                ErrorCode.LOAN_NOT_ACTIVE,
                f"Loan is not active. Current status: {loan.status}",
            )

        payer_wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=data.wallet_id, user=user
        )
        if not payer_wallet:
            raise BodyValidationError("wallet_id", "Wallet not found")

        if payer_wallet.currency_id != loan.wallet.currency_id:
            raise BodyValidationError(
                "wallet_id", f"Wallet currency must be {loan.wallet.currency.code}"
            )

        if data.amount <= 0:
            raise BodyValidationError(
                "amount", "Repayment amount must be greater than zero"
            )

        if payer_wallet.balance < data.amount:
            raise BodyValidationError(
                "amount",
                f"Insufficient balance. Available: {payer_wallet.balance} {payer_wallet.currency.code}",
            )

        if data.schedule_id:
            schedule = await LoanRepaymentSchedule.objects.aget_or_none(
                schedule_id=data.schedule_id, loan=loan
            )
            if not schedule:
                raise BodyValidationError("schedule_id", "Repayment schedule not found")
        else:
            # Get next pending/overdue schedule
            schedule = (
                await LoanRepaymentSchedule.objects.filter(
                    loan=loan,
                    status__in=[
                        RepaymentStatus.PENDING,
                        RepaymentStatus.OVERDUE,
                        RepaymentStatus.PARTIAL,
                    ],
                )
                .order_by("installment_number")
                .afirst()
            )

            if not schedule:
                raise RequestError(
                    ErrorCode.LOAN_ALREADY_PAID, "All loan installments have been paid"
                )

        amount_to_pay = min(
            data.amount, schedule.outstanding_amount + schedule.late_fee
        )

        # Pay late fee first
        late_fee_paid = min(amount_to_pay, schedule.late_fee)
        remaining_after_late_fee = amount_to_pay - late_fee_paid

        # Allocate remaining to principal and interest (proportionally)
        if schedule.outstanding_amount > 0:
            interest_ratio = schedule.interest_amount / schedule.total_amount
            principal_ratio = schedule.principal_amount / schedule.total_amount

            interest_paid = remaining_after_late_fee * interest_ratio
            principal_paid = remaining_after_late_fee * principal_ratio
        else:
            interest_paid = Decimal("0")
            principal_paid = Decimal("0")

        # Debit payer wallet
        payer_wallet.balance -= amount_to_pay
        await payer_wallet.asave(update_fields=["balance", "updated_at"])

        transaction_ref = (
            f"REPAY-{int(timezone.now().timestamp())}-{secrets.token_urlsafe(8)}"
        )
        transaction = await Transaction.objects.acreate(
            from_user=user,
            from_wallet=payer_wallet,
            transaction_type=TransactionType.LOAN_REPAYMENT,
            amount=amount_to_pay,
            net_amount=amount_to_pay - late_fee_paid,
            from_balance_before=payer_wallet.balance + amount_to_pay,
            from_balance_after=payer_wallet.balance,
            reference=transaction_ref,
            status=TransactionStatus.COMPLETED,
            description=f"Loan repayment for installment #{schedule.installment_number}",
            metadata={
                "loan_id": str(loan.application_id),
                "schedule_id": str(schedule.schedule_id),
                "installment_number": schedule.installment_number,
            },
        )

        repayment_ref = f"LRP-{int(timezone.now().timestamp())}-{loan.application_id.hex[:8].upper()}"
        repayment = await LoanRepayment.objects.acreate(
            loan=loan,
            schedule=schedule,
            amount=amount_to_pay,
            principal_paid=principal_paid,
            interest_paid=interest_paid,
            late_fee_paid=late_fee_paid,
            wallet=payer_wallet,
            transaction=transaction,
            reference=repayment_ref,
            status="completed",
            notes=data.notes,
        )

        # Update schedule
        schedule.amount_paid += amount_to_pay
        schedule.outstanding_amount -= remaining_after_late_fee
        schedule.late_fee = max(Decimal("0"), schedule.late_fee - late_fee_paid)

        if schedule.outstanding_amount <= 0:
            schedule.status = RepaymentStatus.PAID
            schedule.paid_at = timezone.now()
        elif schedule.amount_paid > 0:
            schedule.status = RepaymentStatus.PARTIAL

        await schedule.asave(
            update_fields=[
                "amount_paid",
                "outstanding_amount",
                "late_fee",
                "status",
                "paid_at",
                "updated_at",
            ]
        )

        # Check if all schedules are paid
        remaining_schedules = await LoanRepaymentSchedule.objects.filter(
            loan=loan,
            status__in=[
                RepaymentStatus.PENDING,
                RepaymentStatus.OVERDUE,
                RepaymentStatus.PARTIAL,
            ],
        ).acount()

        if remaining_schedules == 0:
            # Loan fully paid
            loan.status = LoanStatus.PAID
            await loan.asave(update_fields=["status", "updated_at"])
            # Update credit score after loan completion
            await CreditScoreService.calculate_credit_score(user)

        # Send loan repayment notification (in-app, push, email)
        await sync_to_async(UnifiedNotificationDispatcher.dispatch)(
            user=user,
            event_type=NotificationEventType.LOAN_REPAYMENT,
            channels=[
                NotificationChannel.IN_APP,
                NotificationChannel.PUSH,
                NotificationChannel.EMAIL,
            ],
            title="Loan Repayment Successful!",
            message=f"Your loan repayment of {payer_wallet.currency.symbol}{amount_to_pay:,.2f} was successful",
            context_data={"repayment_id": str(repayment.repayment_id)},
            priority=NotificationPriority.MEDIUM,
            related_object_type="LoanRepayment",
            related_object_id=str(repayment.repayment_id),
            action_url=f"/loans/{loan.application_id}",
        )

        return repayment

    @staticmethod
    async def get_loan_repayments(
        user: User, application_id, page_params: PaginationQuerySchema
    ):
        loan = await LoanApplication.objects.aget_or_none(
            application_id=application_id, user=user
        )
        if not loan:
            raise NotFoundError("Loan application not found")
        return await Paginator.paginate_queryset(
            LoanRepayment.objects.filter(loan=loan)
            .select_related("wallet", "transaction", "schedule")
            .order_by("-created_at"),
            page_params.page,
            page_params.limit,
        )

    @staticmethod
    async def get_loan_summary(user: User) -> dict:
        loans_q = LoanApplication.objects.filter(user=user).select_related(
            "wallet__currency"
        )

        total_loans = await loans_q.acount()
        active_loans = await loans_q.filter(status=LoanStatus.ACTIVE).acount()
        completed_loans = await loans_q.filter(status=LoanStatus.PAID).acount()
        rejected_loans = await loans_q.filter(status=LoanStatus.REJECTED).acount()

        # Calculate financial metrics
        total_borrowed_agg = await loans_q.filter(
            status__in=[
                LoanStatus.DISBURSED,
                LoanStatus.ACTIVE,
                LoanStatus.OVERDUE,
                LoanStatus.PAID,
            ]
        ).aaggregate(total_borrowed=Coalesce(Sum("approved_amount"), Decimal("0")))
        total_borrowed = total_borrowed_agg["total_borrowed"] or Decimal("0")

        # Get total repaid
        repayments_qs = LoanRepayment.objects.filter(loan__user=user)

        total_repaid = (
            await repayments_qs.aaggregate(
                total_repaid=Coalesce(Sum("amount"), Decimal("0"))
            )
        )["total_repaid"] or Decimal("0")

        # Calculate outstanding balance
        outstanding_balance = Decimal("0")
        upcoming_payment_amount = Decimal("0")
        upcoming_payment_date = None
        overdue_amount = Decimal("0")
        overdue_count = 0

        active_loan_ids = await sync_to_async(list)(
            loans_q.filter(status=LoanStatus.ACTIVE).values_list("id", flat=True)
        )

        if active_loan_ids:
            schedules_qs = LoanRepaymentSchedule.objects.filter(
                loan_id__in=active_loan_ids
            )

            # Get current date for overdue calculation
            today = timezone.now().date()

            aggregates = await schedules_qs.aaggregate(
                outstanding_balance=Sum(
                    Case(
                        When(
                            status__in=[
                                RepaymentStatus.PENDING,
                                RepaymentStatus.OVERDUE,
                                RepaymentStatus.PARTIAL,
                            ],
                            then=F("outstanding_amount"),
                        ),
                        output_field=DecimalField(),
                    )
                ),
                overdue_amount=Sum(
                    Case(
                        When(
                            ~Q(status=RepaymentStatus.PAID),
                            due_date__lt=today,
                            then=F("outstanding_amount"),
                        ),
                        output_field=DecimalField(),
                    )
                ),
                overdue_count=Count(
                    Case(
                        When(
                            ~Q(status=RepaymentStatus.PAID), due_date__lt=today, then=1
                        )
                    )
                ),
                upcoming_payment_date=Min(
                    Case(
                        When(
                            status__in=[
                                RepaymentStatus.PENDING,
                                RepaymentStatus.OVERDUE,
                                RepaymentStatus.PARTIAL,
                            ],
                            then=F("due_date"),
                        )
                    )
                ),
            )

            # Get upcoming payment amount for that date
            upcoming_payment_amount = Decimal("0")
            if aggregates["upcoming_payment_date"]:
                next_schedule = await schedules_qs.filter(
                    due_date=aggregates["upcoming_payment_date"]
                ).afirst()
                if next_schedule:
                    upcoming_payment_amount = next_schedule.outstanding_amount

            # Extract results safely
            outstanding_balance = aggregates["outstanding_balance"] or Decimal("0")
            overdue_amount = aggregates["overdue_amount"] or Decimal("0")
            overdue_count = aggregates["overdue_count"] or 0
            upcoming_payment_date = aggregates["upcoming_payment_date"]

        # Get credit score
        credit_score_obj = await CreditScoreService.get_latest_credit_score(user)

        # Get currency (use the first loan's currency or default)
        first_loan = await loans_q.afirst()
        currency = first_loan.wallet.currency if first_loan else None

        return {
            "total_loans": total_loans,
            "active_loans": active_loans,
            "completed_loans": completed_loans,
            "rejected_loans": rejected_loans,
            "total_borrowed": total_borrowed,
            "total_repaid": total_repaid,
            "outstanding_balance": outstanding_balance,
            "upcoming_payment_amount": upcoming_payment_amount,
            "upcoming_payment_date": upcoming_payment_date,
            "overdue_amount": overdue_amount,
            "overdue_count": overdue_count,
            "credit_score": credit_score_obj.score if credit_score_obj else None,
            "credit_score_band": (
                credit_score_obj.score_band if credit_score_obj else None
            ),
            "currency": currency,
        }

    @staticmethod
    async def get_loan_details(user: User, application_id) -> dict:
        loan = await LoanApplication.objects.select_related(
            "user", "loan_product", "wallet", "loan_product__currency", "reviewed_by"
        ).aget_or_none(application_id=application_id, user=user)

        if not loan:
            raise NotFoundError("Loan application not found")

        schedules_qs = LoanRepaymentSchedule.objects.filter(loan=loan).order_by(
            "installment_number"
        )

        repayments_qs = (
            LoanRepayment.objects.filter(loan=loan)
            .select_related("wallet", "transaction")
            .order_by("-created_at")
        )

        # Calculate totals
        total_paid = (
            await repayments_qs.aaggregate(
                total_paid=Coalesce(Sum("amount"), Decimal("0"))
            )
        )["total_paid"]
        remaining_balance = (
            await schedules_qs.filter(
                status__in=[
                    RepaymentStatus.PENDING,
                    RepaymentStatus.OVERDUE,
                    RepaymentStatus.PARTIAL,
                ]
            ).aaggregate(
                remaining_balance=Coalesce(Sum("outstanding_amount"), Decimal("0"))
            )
        )["remaining_balance"]

        # Get next due payment
        next_schedule = (
            await LoanRepaymentSchedule.objects.filter(
                loan=loan, status__in=[RepaymentStatus.PENDING, RepaymentStatus.OVERDUE]
            )
            .order_by("installment_number")
            .afirst()
        )

        next_due_date = next_schedule.due_date if next_schedule else None
        next_due_amount = (
            next_schedule.outstanding_amount if next_schedule else Decimal("0")
        )

        return {
            "application": loan,
            "repayment_schedule": await sync_to_async(list)(schedules_qs),
            "repayments": await sync_to_async(list)(repayments_qs),
            "total_paid": total_paid,
            "remaining_balance": remaining_balance,
            "next_due_date": next_due_date,
            "next_due_amount": next_due_amount,
        }
