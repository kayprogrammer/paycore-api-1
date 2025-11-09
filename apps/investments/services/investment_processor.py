"""
Investment processor service for handling payouts, maturity, and portfolio management
"""

from decimal import Decimal
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F
from typing import Optional
import secrets

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.exceptions import NotFoundError, RequestError, ErrorCode
from apps.investments.models import (
    Investment,
    InvestmentReturn,
    InvestmentPortfolio,
    InvestmentStatus,
)
from apps.wallets.models import Wallet
from apps.transactions.models import Transaction, TransactionType, TransactionStatus
from apps.notifications.services.dispatcher import (
    UnifiedNotificationDispatcher,
    NotificationChannel,
    NotificationEventType,
)
from apps.notifications.models import NotificationPriority


class InvestmentProcessor:
    """Service for processing investment returns, maturity, and portfolios"""

    @staticmethod
    @aatomic
    async def process_maturity(investment_id) -> Investment:
        """Process matured investment - payout principal + returns"""

        investment = await Investment.objects.select_related(
            "user", "product", "wallet", "wallet__currency"
        ).aget_or_none(investment_id=investment_id)

        if not investment:
            raise NotFoundError("Investment not found")

        if investment.status != InvestmentStatus.ACTIVE:
            raise RequestError(
                ErrorCode.INVESTMENT_NOT_ACTIVE,
                f"Cannot process maturity for investment with status: {investment.status}",
            )

        total_payout = investment.principal_amount + investment.actual_returns

        wallet = investment.wallet
        wallet.balance += total_payout
        wallet.available_balance += total_payout
        await wallet.asave(update_fields=["balance", "available_balance", "updated_at"])

        # Create transaction
        transaction_ref = f"INV-PAYOUT-{int(timezone.now().timestamp())}-{secrets.token_urlsafe(8)}"
        transaction = await Transaction.objects.acreate(
            to_user=investment.user,
            to_wallet=wallet,
            transaction_type=TransactionType.INVESTMENT_PAYOUT,
            amount=total_payout,
            net_amount=total_payout,
            status=TransactionStatus.COMPLETED,
            description=f"Maturity payout for {investment.product.name}",
            external_reference=transaction_ref,
            metadata={
                "investment_id": str(investment.investment_id),
                "principal": str(investment.principal_amount),
                "returns": str(investment.actual_returns),
            },
        )

        investment.status = InvestmentStatus.MATURED
        investment.actual_maturity_date = timezone.now()
        investment.total_payout = total_payout
        investment.payout_transaction = transaction
        await investment.asave(
            update_fields=[
                "status",
                "actual_maturity_date",
                "total_payout",
                "payout_transaction",
                "updated_at",
            ]
        )

        product = await investment.product
        if product.available_slots is not None:
            product.slots_taken -= 1
            await product.asave(update_fields=["slots_taken", "updated_at"])

        # Send investment maturity notification (in-app, push, email)
        await sync_to_async(UnifiedNotificationDispatcher.dispatch)(
            user=investment.user,
            event_type=NotificationEventType.INVESTMENT_MATURED,
            channels=[
                NotificationChannel.IN_APP,
                NotificationChannel.PUSH,
                NotificationChannel.EMAIL,
            ],
            title="Investment Matured!",
            message=f"Your investment in {product.name} has matured. Total payout: {wallet.currency.symbol}{total_payout:,.2f}",
            context_data={"investment_id": str(investment.investment_id)},
            priority=NotificationPriority.HIGH,
            related_object_type="Investment",
            related_object_id=str(investment.investment_id),
            action_url=f"/investments/{investment.investment_id}",
        )

        return investment

    @staticmethod
    @aatomic
    async def process_periodic_return(return_id) -> InvestmentReturn:
        investment_return = await InvestmentReturn.objects.select_related(
            "investment",
            "investment__user",
            "investment__wallet",
            "investment__wallet__currency",
        ).aget_or_none(return_id=return_id)

        if not investment_return:
            raise NotFoundError("Investment return not found")

        if investment_return.is_paid:
            raise RequestError(
                ErrorCode.INVESTMENT_RETURN_ALREADY_PAID,
                "This return has already been paid",
            )

        investment = investment_return.investment

        if not investment.is_active:
            raise RequestError(
                ErrorCode.INVESTMENT_NOT_ACTIVE,
                "Cannot process returns for inactive investment",
            )

        wallet = investment.wallet
        wallet.balance += investment_return.amount
        wallet.available_balance += investment_return.amount
        await wallet.asave(update_fields=["balance", "available_balance", "updated_at"])

        # Create transaction
        transaction_ref = f"INV-RETURN-{int(timezone.now().timestamp())}-{secrets.token_urlsafe(8)}"
        transaction = await Transaction.objects.acreate(
            to_user=investment.user,
            to_wallet=wallet,
            transaction_type=TransactionType.INVESTMENT_RETURN,
            amount=investment_return.amount,
            net_amount=investment_return.amount,
            status=TransactionStatus.COMPLETED,
            description=f"Investment return from {investment.product.name}",
            external_reference=transaction_ref,
            metadata={
                "investment_id": str(investment.investment_id),
                "return_id": str(investment_return.return_id),
            },
        )

        investment_return.is_paid = True
        investment_return.actual_payout_date = timezone.now()
        investment_return.transaction = transaction
        await investment_return.asave(
            update_fields=["is_paid", "actual_payout_date", "transaction", "updated_at"]
        )

        investment.actual_returns += investment_return.amount
        await investment.asave(update_fields=["actual_returns", "updated_at"])
        return investment_return

    @staticmethod
    async def get_portfolio_summary(user: User) -> dict:
        investments = Investment.objects.filter(user=user).select_related(
            "product", "product__currency"
        )

        total_investments = await investments.acount()
        active_investments = await investments.filter(
            status=InvestmentStatus.ACTIVE
        ).acount()
        matured_investments = await investments.filter(
            status=InvestmentStatus.MATURED
        ).acount()

        active_agg = await investments.filter(
            status=InvestmentStatus.ACTIVE
        ).aaggregate(
            total_invested=Sum("principal_amount"),
            total_returns=Sum("actual_returns"),
        )

        all_agg = await investments.aaggregate(
            all_invested=Sum("principal_amount"),
            all_returns=Sum("actual_returns"),
        )

        total_invested = all_agg["all_invested"] or Decimal(0)
        total_active_value = (active_agg["total_invested"] or Decimal(0)) + (
            active_agg["total_returns"] or Decimal(0)
        )
        total_returns_earned = all_agg["all_returns"] or Decimal(0)

        if total_invested > 0:
            average_return_rate = (total_returns_earned / total_invested) * 100
        else:
            average_return_rate = Decimal(0)

        investments_by_type = {}
        async for row in investments.values("product__product_type").annotate(
            count=Count("id"), total=Sum("principal_amount")
        ):
            investments_by_type[row["product__product_type"]] = {
                "count": row["count"],
                "total": row["total"],
            }

        investments_by_risk = {}
        async for row in investments.values("product__risk_level").annotate(
            count=Count("id"), total=Sum("principal_amount")
        ):
            investments_by_risk[row["product__risk_level"]] = {
                "count": row["count"],
                "total": row["total"],
            }

        thirty_days_from_now = timezone.now() + timezone.timedelta(days=30)
        upcoming_maturities = await sync_to_async(list)(
            investments.filter(
                status=InvestmentStatus.ACTIVE, maturity_date__lte=thirty_days_from_now
            ).order_by("maturity_date")[:5]
        )

        return {
            "total_investments": total_investments,
            "active_investments": active_investments,
            "matured_investments": matured_investments,
            "total_invested": total_invested,
            "total_active_value": total_active_value,
            "total_returns_earned": total_returns_earned,
            "average_return_rate": average_return_rate,
            "investments_by_type": investments_by_type,
            "investments_by_risk": investments_by_risk,
            "upcoming_maturities": upcoming_maturities,
        }

    @staticmethod
    @aatomic
    async def update_portfolio(user: User) -> InvestmentPortfolio:
        portfolio, created = await InvestmentPortfolio.objects.aget_or_create(user=user)

        investments = Investment.objects.filter(user=user)
        # Aggregate data
        total_count = await investments.acount()
        active_count = await investments.filter(status=InvestmentStatus.ACTIVE).acount()
        matured_count = await investments.filter(
            status=InvestmentStatus.MATURED
        ).acount()

        # Financial aggregates
        active_agg = await investments.filter(
            status=InvestmentStatus.ACTIVE
        ).aaggregate(
            total_active=Sum("principal_amount"),
        )

        all_agg = await investments.aaggregate(
            total_invested=Sum("principal_amount"),
            total_returns=Sum("actual_returns"),
            avg_rate=Avg("interest_rate"),
        )

        matured_agg = await investments.filter(
            status=InvestmentStatus.MATURED
        ).aaggregate(
            total_matured=Sum("total_payout"),
        )

        portfolio.total_invested = all_agg["total_invested"] or Decimal(0)
        portfolio.total_active_investments = active_agg["total_active"] or Decimal(0)
        portfolio.total_returns_earned = all_agg["total_returns"] or Decimal(0)
        portfolio.total_matured_value = matured_agg["total_matured"] or Decimal(0)

        portfolio.active_investments_count = active_count
        portfolio.matured_investments_count = matured_count
        portfolio.total_investments_count = total_count

        portfolio.average_return_rate = all_agg["avg_rate"] or Decimal(0)
        await portfolio.asave()
        return portfolio

    @staticmethod
    async def get_investment_details(user: User, investment_id) -> dict:
        investment = await Investment.objects.select_related(
            "product", "product__currency", "wallet", "wallet__currency"
        ).aget_or_none(investment_id=investment_id, user=user)

        if not investment:
            raise NotFoundError("Investment not found")

        returns_history = await sync_to_async(list)(
            investment.returns.all().order_by("payout_date")
        )
        total_returns_paid = sum(ret.amount for ret in returns_history if ret.is_paid)

        next_return = (
            await investment.returns.filter(is_paid=False)
            .order_by("payout_date")
            .afirst()
        )

        next_payout_date = next_return.payout_date if next_return else None
        next_payout_amount = next_return.amount if next_return else Decimal(0)
        return {
            "investment": investment,
            "returns_history": returns_history,
            "total_returns_paid": total_returns_paid,
            "next_payout_date": next_payout_date,
            "next_payout_amount": next_payout_amount,
        }
