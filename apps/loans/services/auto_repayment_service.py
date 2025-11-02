"""
Auto-repayment service for managing automatic loan repayments
"""

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.exceptions import (
    NotFoundError,
    BodyValidationError,
    RequestError,
    ErrorCode,
)
from apps.loans.models import (
    AutoRepayment,
    AutoRepaymentStatus,
    LoanApplication,
)
from apps.loans.schemas import EnableAutoRepaymentSchema, UpdateAutoRepaymentSchema
from apps.wallets.models import Wallet
from apps.common.utils import set_dict_attr


class AutoRepaymentService:
    """Service for managing automatic loan repayments"""

    @staticmethod
    @aatomic
    async def enable_auto_repayment(
        user: User, application_id, data: EnableAutoRepaymentSchema
    ) -> AutoRepayment:
        """Enable automatic repayment for a loan"""
        loan = await LoanApplication.objects.select_related(
            "user", "loan_product", "wallet", "wallet__currency"
        ).aget_or_none(application_id=application_id, user=user)

        if not loan:
            raise NotFoundError("Loan application not found")

        if not loan.is_active:
            raise RequestError(
                ErrorCode.LOAN_NOT_ACTIVE,
                f"Loan must be active to enable auto-repayment. Current status: {loan.status}",
            )

        existing = await AutoRepayment.objects.aget_or_none(loan=loan)
        if existing:
            raise RequestError(
                ErrorCode.LOAN_ALREADY_ACTIVE,
                "Automatic repayment is already enabled for this loan",
            )

        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=data.wallet_id, user=user
        )
        if not wallet:
            raise BodyValidationError("wallet_id", "Wallet not found")

        if wallet.currency_id != loan.wallet.currency_id:
            raise BodyValidationError(
                "wallet_id", f"Wallet currency must be {loan.wallet.currency.code}"
            )

        if not data.auto_pay_full_amount and not data.custom_amount:
            raise BodyValidationError(
                "custom_amount",
                "Custom amount is required when auto_pay_full_amount is False",
            )

        auto_repayment = await AutoRepayment.objects.acreate(
            loan=loan,
            wallet=wallet,
            is_enabled=True,
            status=AutoRepaymentStatus.ACTIVE,
            auto_pay_full_amount=data.auto_pay_full_amount,
            custom_amount=data.custom_amount,
            days_before_due=data.days_before_due,
            retry_on_failure=data.retry_on_failure,
            max_retry_attempts=data.max_retry_attempts,
            retry_interval_hours=data.retry_interval_hours,
            send_notification_on_success=data.send_notification_on_success,
            send_notification_on_failure=data.send_notification_on_failure,
        )
        return auto_repayment

    @staticmethod
    async def get_auto_repayment(user: User, application_id) -> AutoRepayment:
        loan = await LoanApplication.objects.aget_or_none(
            application_id=application_id, user=user
        )
        if not loan:
            raise NotFoundError("Loan application not found")

        auto_repayment = await AutoRepayment.objects.select_related(
            "wallet", "wallet__currency"
        ).aget_or_none(loan=loan)

        if not auto_repayment:
            raise NotFoundError("Automatic repayment is not enabled for this loan")

        return auto_repayment

    @staticmethod
    @aatomic
    async def update_auto_repayment(
        user: User, application_id, data: UpdateAutoRepaymentSchema
    ) -> AutoRepayment:
        loan = await LoanApplication.objects.select_related(
            "loan_product", "wallet", "wallet__currency"
        ).aget_or_none(application_id=application_id, user=user)
        if not loan:
            raise NotFoundError("Loan application not found")

        auto_repayment = await AutoRepayment.objects.select_related(
            "wallet", "wallet__currency"
        ).aget_or_none(loan=loan)

        if not auto_repayment:
            raise NotFoundError("Automatic repayment is not enabled for this loan")

        if data.wallet_id:
            wallet = await Wallet.objects.select_related("currency").aget_or_none(
                wallet_id=data.wallet_id, user=user
            )
            if not wallet:
                raise BodyValidationError("wallet_id", "Wallet not found")

            if wallet.currency_id != loan.wallet.currency_id:
                raise BodyValidationError(
                    "wallet_id", f"Wallet currency must be {loan.wallet.currency.code}"
                )

            auto_repayment.wallet = wallet

        data_to_update = data.model_dump(exclude_unset=True, exclude=["wallet_id"])
        auto_repayment = set_dict_attr(auto_repayment, data_to_update)
        update_fields = ["updated_at"] + list(data_to_update.keys())

        # Validate custom amount if auto_pay_full_amount is False
        if not auto_repayment.auto_pay_full_amount and not auto_repayment.custom_amount:
            raise BodyValidationError(
                "custom_amount",
                "Custom amount is required when auto_pay_full_amount is False",
            )

        await auto_repayment.asave(update_fields=update_fields)
        return auto_repayment

    @staticmethod
    @aatomic
    async def disable_auto_repayment(user: User, application_id) -> None:
        loan = await LoanApplication.objects.aget_or_none(
            application_id=application_id, user=user
        )
        if not loan:
            raise NotFoundError("Loan application not found")

        auto_repayment = await AutoRepayment.objects.aget_or_none(loan=loan)
        if not auto_repayment:
            raise NotFoundError("Automatic repayment is not enabled for this loan")

        auto_repayment.is_enabled = False
        auto_repayment.status = AutoRepaymentStatus.INACTIVE
        await auto_repayment.asave(update_fields=["is_enabled", "status", "updated_at"])

    @staticmethod
    @aatomic
    async def suspend_auto_repayment(
        user: User, application_id, reason: str = None
    ) -> AutoRepayment:
        loan = await LoanApplication.objects.aget_or_none(
            application_id=application_id, user=user
        )
        if not loan:
            raise NotFoundError("Loan application not found")

        auto_repayment = await AutoRepayment.objects.select_related(
            "wallet", "wallet__currency"
        ).aget_or_none(loan=loan)

        if not auto_repayment:
            raise NotFoundError("Automatic repayment is not enabled for this loan")

        if auto_repayment.status == AutoRepaymentStatus.SUSPENDED:
            raise RequestError(
                ErrorCode.LOAN_ALREADY_ACTIVE,
                "Automatic repayment is already suspended",
            )

        auto_repayment.status = AutoRepaymentStatus.SUSPENDED
        auto_repayment.last_failure_reason = reason or "Manually suspended by user"
        await auto_repayment.asave(
            update_fields=["status", "last_failure_reason", "updated_at"]
        )
        return auto_repayment

    @staticmethod
    @aatomic
    async def reactivate_auto_repayment(user: User, application_id) -> AutoRepayment:
        loan = await LoanApplication.objects.aget_or_none(
            application_id=application_id, user=user
        )
        if not loan:
            raise NotFoundError("Loan application not found")

        auto_repayment = await AutoRepayment.objects.select_related(
            "wallet", "wallet__currency"
        ).aget_or_none(loan=loan)

        if not auto_repayment:
            raise NotFoundError("Automatic repayment is not enabled for this loan")

        if auto_repayment.status == AutoRepaymentStatus.ACTIVE:
            raise RequestError(
                ErrorCode.LOAN_ALREADY_ACTIVE, "Automatic repayment is already active"
            )

        if not loan.is_active:
            raise RequestError(
                ErrorCode.LOAN_NOT_ACTIVE,
                f"Loan must be active to reactivate auto-repayment. Current status: {loan.status}",
            )

        auto_repayment.status = AutoRepaymentStatus.ACTIVE
        auto_repayment.consecutive_failures = 0  # Reset failure counter
        auto_repayment.last_failure_reason = None
        await auto_repayment.asave(
            update_fields=[
                "status",
                "consecutive_failures",
                "last_failure_reason",
                "updated_at",
            ]
        )

        return auto_repayment
