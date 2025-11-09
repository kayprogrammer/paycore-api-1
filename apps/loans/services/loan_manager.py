from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.paginators import Paginator
from apps.common.schemas import PaginationQuerySchema
from apps.loans.models import (
    LoanProduct,
    LoanApplication,
    LoanStatus,
    RepaymentFrequency,
    LoanRepaymentSchedule,
    RepaymentStatus,
    CollateralType,
)
from apps.wallets.models import Wallet
from apps.common.exceptions import (
    NotFoundError,
    BodyValidationError,
    RequestError,
    ErrorCode,
)
from apps.loans.schemas import (
    CreateLoanApplicationSchema,
    ApproveLoanSchema,
    RejectLoanSchema,
)
from apps.notifications.services.dispatcher import (
    UnifiedNotificationDispatcher,
    NotificationChannel,
    NotificationEventType,
)
from apps.notifications.models import NotificationPriority
from apps.loans.services.credit_score_service import CreditScoreService
from asgiref.sync import sync_to_async


class LoanManager:
    """Service for managing loan applications"""

    @staticmethod
    async def get_active_loan_products(
        currency_code: str = None, product_type: str = None
    ):
        queryset = LoanProduct.objects.filter(is_active=True).select_related("currency")
        if currency_code:
            queryset = queryset.filter(currency__code=currency_code)
        if product_type:
            queryset = queryset.filter(product_type=product_type)
        return await sync_to_async(list)(
            queryset.order_by("product_type", "min_amount")
        )

    @staticmethod
    async def get_loan_product(product_id) -> LoanProduct:
        product = await LoanProduct.objects.select_related("currency").aget_or_none(
            product_id=product_id
        )
        if not product:
            raise NotFoundError("Loan product not found")
        return product

    @staticmethod
    async def calculate_loan(
        product: LoanProduct,
        amount: Decimal,
        tenure_months: int,
        repayment_frequency: str,
    ) -> dict:
        """
        Calculate loan details including interest, fees, and repayment schedule
        """
        if not product.is_active:
            raise RequestError(
                ErrorCode.LOAN_PRODUCT_INACTIVE,
                "This loan product is no longer available",
            )

        if amount < product.min_amount:
            raise RequestError(
                ErrorCode.LOAN_AMOUNT_BELOW_MIN,
                f"Loan amount must be at least {product.min_amount} {product.currency.code}",
            )

        if amount > product.max_amount:
            raise RequestError(
                ErrorCode.LOAN_AMOUNT_ABOVE_MAX,
                f"Loan amount cannot exceed {product.max_amount} {product.currency.code}",
            )

        if (
            tenure_months < product.min_tenure_months
            or tenure_months > product.max_tenure_months
        ):
            raise RequestError(
                ErrorCode.LOAN_TENURE_INVALID,
                f"Loan tenure must be between {product.min_tenure_months} and {product.max_tenure_months} months",
            )

        if repayment_frequency not in product.allowed_repayment_frequencies:
            raise BodyValidationError(
                "repayment_frequency",
                f"Repayment frequency must be one of: {', '.join(product.allowed_repayment_frequencies)}",
            )

        # Calculate interest rate (use min rate for now, can be adjusted based on credit score)
        interest_rate = product.min_interest_rate

        processing_fee = max(
            (amount * product.processing_fee_percentage / Decimal("100")),
            product.processing_fee_fixed,
        )

        # Calculate total interest (simple interest for simplicity)
        # Total Interest = Principal × Rate × Time
        annual_interest = amount * (interest_rate / Decimal("100"))
        total_interest = (annual_interest * tenure_months) / Decimal("12")

        total_repayable = amount + total_interest

        number_of_installments = LoanManager._calculate_installments(
            tenure_months, repayment_frequency
        )

        installment_amount = total_repayable / number_of_installments

        # Monthly repayment (for display purposes)
        monthly_repayment = total_repayable / tenure_months

        return {
            "requested_amount": amount,
            "approved_amount": amount,
            "interest_rate": interest_rate,
            "tenure_months": tenure_months,
            "repayment_frequency": repayment_frequency,
            "processing_fee": processing_fee,
            "total_interest": total_interest,
            "total_repayable": total_repayable,
            "monthly_repayment": monthly_repayment,
            "installment_amount": installment_amount,
            "number_of_installments": number_of_installments,
            "currency": product.currency,
        }

    @staticmethod
    def _calculate_installments(tenure_months: int, frequency: str) -> int:
        if frequency == RepaymentFrequency.DAILY:
            return tenure_months * 30  # Approximate
        elif frequency == RepaymentFrequency.WEEKLY:
            return tenure_months * 4  # Approximate
        elif frequency == RepaymentFrequency.BIWEEKLY:
            return tenure_months * 2
        elif frequency == RepaymentFrequency.MONTHLY:
            return tenure_months
        elif frequency == RepaymentFrequency.QUARTERLY:
            return max(1, tenure_months // 3)
        return tenure_months

    @staticmethod
    @aatomic
    async def create_loan_application(
        user: User, data: CreateLoanApplicationSchema
    ) -> LoanApplication:
        product = await LoanManager.get_loan_product(data.loan_product_id)
        if not product.is_active:
            raise RequestError(
                ErrorCode.LOAN_PRODUCT_INACTIVE,
                "This loan product is no longer available",
            )
        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=data.wallet_id, user=user
        )
        if not wallet:
            raise BodyValidationError("wallet_id", "Wallet not found")

        if wallet.currency_id != product.currency_id:
            raise BodyValidationError(
                "wallet_id", f"Wallet currency must be {product.currency.code}"
            )

        has_active_loan = await LoanApplication.objects.filter(
            user=user,
            status__in=[
                LoanStatus.PENDING,
                LoanStatus.UNDER_REVIEW,
                LoanStatus.APPROVED,
                LoanStatus.DISBURSED,
                LoanStatus.ACTIVE,
                LoanStatus.OVERDUE,
            ],
        ).aexists()

        if has_active_loan:
            raise RequestError(
                ErrorCode.LOAN_ALREADY_ACTIVE,
                "You already have an active loan application or outstanding loan",
            )

        loan_calc = await LoanManager.calculate_loan(
            product, data.requested_amount, data.tenure_months, data.repayment_frequency
        )

        credit_score = await CreditScoreService.get_latest_credit_score(user)
        if credit_score.score < product.min_credit_score:
            raise RequestError(
                ErrorCode.CREDIT_SCORE_TOO_LOW,
                f"Your credit score ({credit_score.score}) is below the minimum requirement ({product.min_credit_score})",
            )

        account_age_days = (timezone.now().date() - user.created_at.date()).days
        if account_age_days < product.min_account_age_days:
            raise RequestError(
                ErrorCode.ACCOUNT_AGE_INSUFFICIENT,
                f"Your account must be at least {product.min_account_age_days} days old",
            )

        if product.requires_collateral:
            if not data.collateral_type or data.collateral_type == CollateralType.NONE:
                raise BodyValidationError(
                    "collateral_type", "This loan product requires collateral"
                )
            if not data.collateral_value or data.collateral_value <= 0:
                raise BodyValidationError(
                    "collateral_value", "Collateral value is required"
                )

        if product.requires_guarantor:
            if not data.guarantor_name or not data.guarantor_phone:
                raise BodyValidationError(
                    "guarantor_name", "This loan product requires a guarantor name"
                )
            if not data.guarantor_phone:
                raise BodyValidationError(
                    "guarantor_phone",
                    "This loan product requires a guarantor phone number",
                )
            if not data.guarantor_email:
                raise BodyValidationError(
                    "guarantor_email",
                    "This loan product requires a guarantor email address",
                )

        data_to_dump = data.model_dump(exclude=["wallet_id", "loan_product_id"])

        loan = await LoanApplication.objects.acreate(
            user=user,
            loan_product=product,
            wallet=wallet,
            interest_rate=loan_calc["interest_rate"],
            processing_fee=loan_calc["processing_fee"],
            total_interest=loan_calc["total_interest"],
            total_repayable=loan_calc["total_repayable"],
            monthly_repayment=loan_calc["monthly_repayment"],
            credit_score=credit_score.score,
            credit_score_band=credit_score.score_band,
            status=LoanStatus.PENDING,
            **data_to_dump,
        )
        return loan

    @staticmethod
    async def get_loan_application(user: User, application_id) -> LoanApplication:
        loan = await LoanApplication.objects.select_related(
            "user", "loan_product", "wallet", "loan_product__currency", "reviewed_by"
        ).aget_or_none(application_id=application_id, user=user)

        if not loan:
            raise NotFoundError("Loan application not found")
        return loan

    @staticmethod
    async def list_loan_applications(
        user: User, status: str = None, page_params: PaginationQuerySchema = None
    ):
        queryset = LoanApplication.objects.filter(user=user).select_related(
            "loan_product", "wallet", "loan_product__currency"
        )

        if status:
            queryset = queryset.filter(status=status)

        return await Paginator.paginate_queryset(
            queryset.order_by("-created_at"), page_params.page, page_params.limit
        )

    @staticmethod
    @aatomic
    async def approve_loan(
        reviewer: User, application_id, data: ApproveLoanSchema
    ) -> LoanApplication:
        """Approve a loan application (admin only)"""
        loan = await LoanApplication.objects.select_related(
            "user",
            "loan_product",
            "loan_product__currency",
            "wallet",
            "wallet__currency",
        ).aget_or_none(application_id=application_id)

        if not loan:
            raise NotFoundError("Loan application not found")

        if loan.status not in [LoanStatus.PENDING, LoanStatus.UNDER_REVIEW]:
            raise RequestError(
                ErrorCode.INVALID_ENTRY,
                f"Cannot approve loan with status: {loan.status}",
            )

        approved_amount = data.approved_amount or loan.requested_amount

        if approved_amount < loan.loan_product.min_amount:
            raise BodyValidationError(
                "approved_amount",
                f"Approved amount must be at least {loan.loan_product.min_amount}",
            )

        if approved_amount > loan.loan_product.max_amount:
            raise BodyValidationError(
                "approved_amount",
                f"Approved amount cannot exceed {loan.loan_product.max_amount}",
            )

        interest_rate = data.interest_rate or loan.interest_rate

        if (
            approved_amount != loan.requested_amount
            or interest_rate != loan.interest_rate
        ):
            loan_calc = await LoanManager.calculate_loan(
                loan.loan_product,
                approved_amount,
                loan.tenure_months,
                loan.repayment_frequency,
            )

            loan.approved_amount = approved_amount
            loan.interest_rate = interest_rate
            loan.total_interest = loan_calc["total_interest"]
            loan.total_repayable = loan_calc["total_repayable"]
            loan.monthly_repayment = loan_calc["monthly_repayment"]
        else:
            loan.approved_amount = approved_amount

        loan.status = LoanStatus.APPROVED
        loan.reviewed_by = reviewer
        loan.reviewed_at = timezone.now()

        await loan.asave(
            update_fields=[
                "approved_amount",
                "interest_rate",
                "total_interest",
                "total_repayable",
                "monthly_repayment",
                "status",
                "reviewed_by",
                "reviewed_at",
                "updated_at",
            ]
        )

        await LoanManager._generate_repayment_schedule(loan)

        # Send loan approval notification (in-app, push, email)
        await sync_to_async(UnifiedNotificationDispatcher.dispatch)(
            user=loan.user,
            event_type=NotificationEventType.LOAN_APPROVED,
            channels=[
                NotificationChannel.IN_APP,
                NotificationChannel.PUSH,
                NotificationChannel.EMAIL,
            ],
            title="Loan Approved!",
            message=f"Your loan application for {loan.wallet.currency.symbol}{loan.approved_amount:,.2f} has been approved",
            context_data={"loan_id": str(loan.application_id)},
            priority=NotificationPriority.HIGH,
            related_object_type="Loan",
            related_object_id=str(loan.application_id),
            action_url=f"/loans/{loan.application_id}",
        )

        return loan

    @staticmethod
    async def reject_loan(
        reviewer: User, application_id, data: RejectLoanSchema
    ) -> LoanApplication:
        """Reject a loan application (admin only)"""
        loan = await LoanApplication.objects.aget_or_none(application_id=application_id)
        if not loan:
            raise NotFoundError("Loan application not found")

        if loan.status not in [LoanStatus.PENDING, LoanStatus.UNDER_REVIEW]:
            raise RequestError(
                ErrorCode.INVALID_ENTRY,
                f"Cannot reject loan with status: {loan.status}",
            )

        loan.status = LoanStatus.REJECTED
        loan.reviewed_by = reviewer
        loan.reviewed_at = timezone.now()
        loan.rejection_reason = data.rejection_reason
        await loan.asave(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
                "updated_at",
            ]
        )
        return loan

    @staticmethod
    async def _generate_repayment_schedule(loan: LoanApplication):
        num_installments = LoanManager._calculate_installments(
            loan.tenure_months, loan.repayment_frequency
        )

        installment_amount = loan.total_repayable / num_installments

        # Calculate principal and interest per installment (simple allocation)
        principal_per_installment = loan.approved_amount / num_installments
        interest_per_installment = loan.total_interest / num_installments

        interval_days = LoanManager._get_payment_interval_days(loan.repayment_frequency)

        schedules = []
        current_date = timezone.now().date()

        for i in range(1, int(num_installments) + 1):
            if loan.repayment_frequency == RepaymentFrequency.MONTHLY:
                due_date = current_date + relativedelta(months=i)
            elif loan.repayment_frequency == RepaymentFrequency.QUARTERLY:
                due_date = current_date + relativedelta(months=i * 3)
            else:
                due_date = current_date + timedelta(days=interval_days * i)

            schedule = LoanRepaymentSchedule(
                loan=loan,
                installment_number=i,
                due_date=due_date,
                principal_amount=principal_per_installment,
                interest_amount=interest_per_installment,
                total_amount=installment_amount,
                outstanding_amount=installment_amount,
                status=RepaymentStatus.PENDING,
            )
            schedules.append(schedule)
        await LoanRepaymentSchedule.objects.abulk_create(schedules)

    @staticmethod
    def _get_payment_interval_days(frequency: str) -> int:
        if frequency == RepaymentFrequency.DAILY:
            return 1
        elif frequency == RepaymentFrequency.WEEKLY:
            return 7
        elif frequency == RepaymentFrequency.BIWEEKLY:
            return 14
        elif frequency == RepaymentFrequency.MONTHLY:
            return 30  # Approximate
        elif frequency == RepaymentFrequency.QUARTERLY:
            return 90  # Approximate
        return 30

    @staticmethod
    async def get_repayment_schedule(user: User, application_id):
        loan = await LoanManager.get_loan_application(user, application_id)
        schedules = await sync_to_async(list)(
            LoanRepaymentSchedule.objects.filter(loan=loan).order_by(
                "installment_number"
            )
        )
        return schedules

    @staticmethod
    async def cancel_loan_application(user: User, application_id) -> LoanApplication:
        loan = await LoanManager.get_loan_application(user, application_id)
        if loan.status not in [LoanStatus.PENDING, LoanStatus.UNDER_REVIEW]:
            raise RequestError(
                ErrorCode.INVALID_ENTRY,
                f"Cannot cancel loan with status: {loan.status}",
            )
        loan.status = LoanStatus.CANCELLED
        await loan.asave(update_fields=["status", "updated_at"])
        return loan
