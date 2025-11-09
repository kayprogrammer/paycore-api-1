"""
Investment manager service for creating and managing investments
"""

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from typing import Optional
import secrets

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.exceptions import (
    NotFoundError,
    BodyValidationError,
    RequestError,
    ErrorCode,
)
from apps.investments.models import (
    Investment,
    InvestmentProduct,
    InvestmentReturn,
    InvestmentStatus,
    InterestPayoutFrequency,
)
from apps.investments.schemas import CreateInvestmentSchema, RenewInvestmentSchema
from apps.wallets.models import Wallet
from apps.transactions.models import Transaction, TransactionType, TransactionStatus
from apps.notifications.services.dispatcher import (
    UnifiedNotificationDispatcher,
    NotificationChannel,
    NotificationEventType,
)
from apps.notifications.models import NotificationPriority
from asgiref.sync import sync_to_async
from apps.common.paginators import Paginator
from apps.common.schemas import PaginationQuerySchema


class InvestmentManager:
    """Service for managing investments"""

    @staticmethod
    async def get_investment_product(product_id) -> InvestmentProduct:
        product = await InvestmentProduct.objects.select_related(
            "currency"
        ).aget_or_none(product_id=product_id)
        if not product:
            raise NotFoundError("Investment product not found")

        return product

    @staticmethod
    @aatomic
    async def create_investment(user: User, data: CreateInvestmentSchema) -> Investment:
        product = await InvestmentManager.get_investment_product(data.product_id)
        if not product.is_active:
            raise RequestError(
                ErrorCode.INVESTMENT_PRODUCT_INACTIVE,
                "This investment product is not currently available",
            )

        if not product.is_available:
            raise RequestError(
                ErrorCode.INVESTMENT_PRODUCT_SOLD_OUT,
                "This investment product has no available slots",
            )

        if data.amount < product.min_amount:
            raise RequestError(
                ErrorCode.INVESTMENT_AMOUNT_BELOW_MIN,
                f"Minimum investment amount is {product.min_amount} {product.currency.code}",
            )

        if product.max_amount and data.amount > product.max_amount:
            raise RequestError(
                ErrorCode.INVESTMENT_AMOUNT_ABOVE_MAX,
                f"Maximum investment amount is {product.max_amount} {product.currency.code}",
            )

        if data.duration_days < product.min_duration_days:
            raise RequestError(
                ErrorCode.INVESTMENT_DURATION_BELOW_MIN,
                f"Minimum investment duration is {product.min_duration_days} days",
            )

        if product.max_duration_days and data.duration_days > product.max_duration_days:
            raise RequestError(
                ErrorCode.INVESTMENT_DURATION_ABOVE_MAX,
                f"Maximum investment duration is {product.max_duration_days} days",
            )

        wallet = await Wallet.objects.select_related("currency").aget_or_none(
            wallet_id=data.wallet_id, user=user
        )

        if not wallet:
            raise NotFoundError("Wallet not found")

        if wallet.currency_id != product.currency_id:
            raise BodyValidationError(
                "wallet_id", f"Wallet currency must be {product.currency.code}"
            )

        if wallet.available_balance < data.amount:
            raise RequestError(
                ErrorCode.INSUFFICIENT_BALANCE,
                f"Insufficient balance. Available: {wallet.available_balance} {wallet.currency.code}",
            )

        # Calculate investment details
        start_date = timezone.now()
        maturity_date = start_date + timedelta(days=data.duration_days)

        # Calculate expected returns using simple interest
        # Formula: I = P * R * T / 365
        # Where P = principal, R = annual rate (decimal), T = days
        interest_decimal = product.interest_rate / 100
        expected_returns = (data.amount * interest_decimal * data.duration_days) / 365

        wallet.balance -= data.amount
        wallet.available_balance -= data.amount
        await wallet.asave(update_fields=["balance", "available_balance", "updated_at"])

        # Create transaction
        transaction_ref = f"INV-{int(timezone.now().timestamp())}-{secrets.token_urlsafe(8)}"
        transaction = await Transaction.objects.acreate(
            from_user=user,
            from_wallet=wallet,
            transaction_type=TransactionType.INVESTMENT,
            amount=data.amount,
            net_amount=data.amount,
            status=TransactionStatus.COMPLETED,
            description=f"Investment in {product.name}",
            external_reference=transaction_ref,
        )

        # Create investment
        investment = await Investment.objects.acreate(
            user=user,
            product=product,
            wallet=wallet,
            principal_amount=data.amount,
            interest_rate=product.interest_rate,
            duration_days=data.duration_days,
            start_date=start_date,
            maturity_date=maturity_date,
            expected_returns=expected_returns,
            status=InvestmentStatus.ACTIVE,
            auto_renew=data.auto_renew,
            investment_transaction=transaction,
        )

        if product.available_slots is not None:
            product.slots_taken += 1
            await product.asave(update_fields=["slots_taken", "updated_at"])

        # Generate payout schedule if periodic payouts
        if product.payout_frequency != InterestPayoutFrequency.AT_MATURITY:
            await InvestmentManager._generate_payout_schedule(investment, product)

        # Send investment creation notification (in-app, push, email)
        await sync_to_async(UnifiedNotificationDispatcher.dispatch)(
            user=user,
            event_type=NotificationEventType.INVESTMENT_CREATED,
            channels=[
                NotificationChannel.IN_APP,
                NotificationChannel.PUSH,
                NotificationChannel.EMAIL,
            ],
            title="Investment Created Successfully!",
            message=f"Your investment of {wallet.currency.symbol}{data.amount:,.2f} in {product.name} has been created",
            context_data={"investment_id": str(investment.investment_id)},
            priority=NotificationPriority.MEDIUM,
            related_object_type="Investment",
            related_object_id=str(investment.investment_id),
            action_url=f"/investments/{investment.investment_id}",
        )

        return investment

    @staticmethod
    async def _generate_payout_schedule(
        investment: Investment, product: InvestmentProduct
    ):
        frequency_days = {
            InterestPayoutFrequency.MONTHLY: 30,
            InterestPayoutFrequency.QUARTERLY: 90,
            InterestPayoutFrequency.SEMI_ANNUALLY: 180,
            InterestPayoutFrequency.ANNUALLY: 365,
        }

        interval_days = frequency_days.get(product.payout_frequency)
        if not interval_days:
            return  # At maturity or invalid frequency

        # Calculate number of payouts
        total_payouts = investment.duration_days // interval_days
        if total_payouts == 0:
            return  # Duration too short for periodic payouts

        interest_per_payout = investment.expected_returns / total_payouts

        current_date = investment.start_date
        returns_to_create = []
        for i in range(total_payouts):
            payout_date = current_date + timedelta(days=interval_days * (i + 1))

            returns_to_create.append(
                InvestmentReturn(
                    investment=investment,
                    amount=interest_per_payout,
                    payout_date=payout_date,
                    is_paid=False,
                )
            )

        await InvestmentReturn.objects.abulk_create(returns_to_create)

    @staticmethod
    async def get_investment(user: User, investment_id) -> Investment:
        investment = await Investment.objects.select_related(
            "product", "product__currency", "wallet", "wallet__currency"
        ).aget_or_none(investment_id=investment_id, user=user)

        if not investment:
            raise NotFoundError("Investment not found")
        return investment

    @staticmethod
    async def list_investments(
        user: User,
        status: Optional[str] = None,
        page_params: PaginationQuerySchema = None,
    ):
        queryset = Investment.objects.filter(user=user).select_related(
            "product", "product__currency", "wallet"
        )

        if status:
            queryset = queryset.filter(status=status)
        paginated_data = await Paginator.paginate_queryset(
            queryset.order_by("-created_at"), page_params.page, page_params.limit
        )
        return paginated_data

    @staticmethod
    @aatomic
    async def liquidate_investment(user: User, investment_id) -> Investment:
        """Liquidate (early exit) an investment"""

        investment = await InvestmentManager.get_investment(user, investment_id)
        if not investment.is_active:
            raise RequestError(
                ErrorCode.INVESTMENT_NOT_ACTIVE,
                f"Cannot liquidate investment with status: {investment.status}",
            )
        if not investment.product.allows_early_liquidation:
            raise RequestError(
                ErrorCode.INVESTMENT_EARLY_LIQUIDATION_NOT_ALLOWED,
                "Early liquidation is not allowed for this investment product",
            )

        penalty_amount = Decimal(0)
        if investment.product.early_liquidation_penalty > 0:
            penalty_rate = investment.product.early_liquidation_penalty / 100
            penalty_amount = investment.principal_amount * penalty_rate

        payout_amount = (
            investment.principal_amount + investment.actual_returns - penalty_amount
        )

        wallet = await Wallet.objects.select_related("currency").aget(
            id=investment.wallet_id
        )
        wallet.balance += payout_amount
        wallet.available_balance += payout_amount
        await wallet.asave(update_fields=["balance", "available_balance", "updated_at"])

        transaction_ref = f"INV-LIQ-{int(timezone.now().timestamp())}-{secrets.token_urlsafe(8)}"
        transaction = await Transaction.objects.acreate(
            to_user=user,
            to_wallet=wallet,
            transaction_type=TransactionType.INVESTMENT_PAYOUT,
            amount=payout_amount,
            net_amount=payout_amount,
            status=TransactionStatus.COMPLETED,
            description=f"Early liquidation of investment {investment.investment_id}",
            external_reference=transaction_ref,
            metadata={
                "principal": str(investment.principal_amount),
                "returns": str(investment.actual_returns),
                "penalty": str(penalty_amount),
            },
        )

        # Update investment
        investment.status = InvestmentStatus.LIQUIDATED
        investment.liquidation_date = timezone.now()
        investment.liquidation_penalty = penalty_amount
        investment.total_payout = payout_amount
        investment.payout_transaction = transaction
        await investment.asave(
            update_fields=[
                "status",
                "liquidation_date",
                "liquidation_penalty",
                "total_payout",
                "payout_transaction",
                "updated_at",
            ]
        )

        product = await InvestmentProduct.objects.aget(id=investment.product_id)
        if product.available_slots is not None:
            product.slots_taken -= 1
            await product.asave(update_fields=["slots_taken", "updated_at"])
        return investment

    @staticmethod
    @aatomic
    async def renew_investment(
        user: User, investment_id, data: RenewInvestmentSchema
    ) -> Investment:
        old_investment = await InvestmentManager.get_investment(user, investment_id)
        if old_investment.status != InvestmentStatus.MATURED:
            raise RequestError(
                ErrorCode.INVESTMENT_NOT_MATURED,
                "Only matured investments can be renewed",
            )

        product = await InvestmentProduct.objects.select_related("currency").aget(
            id=old_investment.product_id
        )

        if not product.allows_auto_renewal:
            raise RequestError(
                ErrorCode.INVESTMENT_RENEWAL_NOT_ALLOWED,
                "This investment product does not allow renewals",
            )

        if not product.is_available:
            raise RequestError(
                ErrorCode.INVESTMENT_PRODUCT_SOLD_OUT,
                "This investment product has no available slots",
            )

        duration_days = data.duration_days or old_investment.duration_days
        if duration_days < product.min_duration_days:
            raise RequestError(
                ErrorCode.INVESTMENT_DURATION_BELOW_MIN,
                f"Minimum investment duration is {product.min_duration_days} days",
            )

        if product.max_duration_days and duration_days > product.max_duration_days:
            raise RequestError(
                ErrorCode.INVESTMENT_DURATION_ABOVE_MAX,
                f"Maximum investment duration is {product.max_duration_days} days",
            )

        # Calculate new investment details
        # Use maturity value (principal + returns) as new principal
        new_principal = old_investment.principal_amount + old_investment.actual_returns

        start_date = timezone.now()
        maturity_date = start_date + timedelta(days=duration_days)

        interest_decimal = product.interest_rate / 100
        expected_returns = (new_principal * interest_decimal * duration_days) / 365

        # Create new investment
        new_investment = await Investment.objects.acreate(
            user=user,
            product=product,
            wallet=old_investment.wallet,
            principal_amount=new_principal,
            interest_rate=product.interest_rate,
            duration_days=duration_days,
            start_date=start_date,
            maturity_date=maturity_date,
            expected_returns=expected_returns,
            status=InvestmentStatus.ACTIVE,
            auto_renew=data.auto_renew,
            renewed_from=old_investment,
        )

        old_investment.status = InvestmentStatus.RENEWED
        await old_investment.asave(update_fields=["status", "updated_at"])

        if product.available_slots is not None:
            product.slots_taken += 1
            await product.asave(update_fields=["slots_taken", "updated_at"])
        if product.payout_frequency != InterestPayoutFrequency.AT_MATURITY:
            await InvestmentManager._generate_payout_schedule(new_investment, product)

        return new_investment

    @staticmethod
    async def calculate_investment(
        product_id, amount: Decimal, duration_days: int
    ) -> dict:
        product = await InvestmentManager.get_investment_product(product_id)

        interest_decimal = product.interest_rate / 100
        expected_returns = (amount * interest_decimal * duration_days) / 365
        total_maturity_value = amount + expected_returns

        effective_annual_rate = (
            float(expected_returns / amount) * (365 / duration_days) * 100
        )

        payout_schedule = []

        if product.payout_frequency == InterestPayoutFrequency.AT_MATURITY:
            payout_schedule.append(
                {
                    "date": (
                        timezone.now() + timedelta(days=duration_days)
                    ).isoformat(),
                    "amount": float(total_maturity_value),
                    "type": "maturity",
                }
            )
        else:
            frequency_days = {
                InterestPayoutFrequency.MONTHLY: 30,
                InterestPayoutFrequency.QUARTERLY: 90,
                InterestPayoutFrequency.SEMI_ANNUALLY: 180,
                InterestPayoutFrequency.ANNUALLY: 365,
            }

            interval_days = frequency_days.get(product.payout_frequency, 0)
            if interval_days:
                total_payouts = duration_days // interval_days
                interest_per_payout = (
                    expected_returns / total_payouts if total_payouts > 0 else 0
                )

                current_date = timezone.now()
                for i in range(total_payouts):
                    payout_date = current_date + timedelta(days=interval_days * (i + 1))
                    payout_schedule.append(
                        {
                            "date": payout_date.isoformat(),
                            "amount": float(interest_per_payout),
                            "type": "interest",
                        }
                    )

                # Final payout with principal
                maturity_date = current_date + timedelta(days=duration_days)
                payout_schedule.append(
                    {
                        "date": maturity_date.isoformat(),
                        "amount": float(amount),
                        "type": "principal",
                    }
                )

        return {
            "product_id": product.product_id,
            "amount": amount,
            "duration_days": duration_days,
            "interest_rate": product.interest_rate,
            "expected_returns": expected_returns,
            "total_maturity_value": total_maturity_value,
            "effective_annual_rate": effective_annual_rate,
            "payout_schedule": payout_schedule,
            "currency": product.currency,
        }
