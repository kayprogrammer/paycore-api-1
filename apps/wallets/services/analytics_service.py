from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from datetime import timedelta
from typing import Dict, Any, List
import calendar

from apps.accounts.models import User
from apps.wallets.models import (
    Wallet,
    VirtualCard,
    QRCode,
    SplitPayment,
    SplitPaymentParticipant,
    RecurringPayment,
    Currency,
)


class WalletAnalyticsService:
    """Service for wallet analytics and reporting"""

    @staticmethod
    async def get_wallet_overview(user: User) -> Dict[str, Any]:
        """Get comprehensive wallet overview for user"""

        # Basic wallet counts
        total_wallets = await Wallet.objects.filter(user=user).acount()
        active_wallets = await Wallet.objects.filter(
            user=user, status="active"
        ).acount()

        # Balance aggregation
        balances_by_currency = {}
        total_balance_usd = Decimal("0")

        async for wallet in Wallet.objects.filter(user=user).select_related("currency"):
            currency_code = wallet.currency.code
            if currency_code not in balances_by_currency:
                balances_by_currency[currency_code] = {
                    "total_balance": Decimal("0"),
                    "available_balance": Decimal("0"),
                    "pending_balance": Decimal("0"),
                    "symbol": wallet.currency.symbol,
                    "exchange_rate": wallet.currency.exchange_rate_usd,
                }

            balances_by_currency[currency_code]["total_balance"] += wallet.balance
            balances_by_currency[currency_code][
                "available_balance"
            ] += wallet.available_balance
            balances_by_currency[currency_code][
                "pending_balance"
            ] += wallet.pending_balance

            # Convert to USD for total calculation
            usd_value = wallet.balance * wallet.currency.exchange_rate_usd
            total_balance_usd += usd_value

        # Virtual cards
        total_virtual_cards = await VirtualCard.objects.filter(
            wallet__user=user
        ).acount()
        active_virtual_cards = await VirtualCard.objects.filter(
            wallet__user=user, is_active=True, is_frozen=False
        ).acount()

        # QR codes
        total_qr_codes = await QRCode.objects.filter(wallet__user=user).acount()
        active_qr_codes = await QRCode.objects.filter(
            wallet__user=user, is_active=True
        ).acount()

        # Split payments
        created_split_payments = await SplitPayment.objects.filter(
            created_by=user
        ).acount()
        participated_split_payments = await SplitPaymentParticipant.objects.filter(
            user=user
        ).acount()

        # Recurring payments
        total_recurring = await RecurringPayment.objects.filter(
            from_wallet__user=user
        ).acount()
        active_recurring = await RecurringPayment.objects.filter(
            from_wallet__user=user, is_active=True
        ).acount()

        return {
            "wallet_summary": {
                "total_wallets": total_wallets,
                "active_wallets": active_wallets,
                "total_balance_usd": total_balance_usd,
                "balances_by_currency": balances_by_currency,
            },
            "features_usage": {
                "virtual_cards": {
                    "total": total_virtual_cards,
                    "active": active_virtual_cards,
                },
                "qr_codes": {"total": total_qr_codes, "active": active_qr_codes},
                "split_payments": {
                    "created": created_split_payments,
                    "participated": participated_split_payments,
                },
                "recurring_payments": {
                    "total": total_recurring,
                    "active": active_recurring,
                },
            },
        }

    @staticmethod
    async def get_spending_analytics(
        user: User, period_days: int = 30, currency_code: str = None
    ) -> Dict[str, Any]:
        """Get spending analytics for a user"""

        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)

        filters = {"user": user, "updated_at__gte": start_date}
        if currency_code:
            filters["currency__code"] = currency_code

        # Get spending by wallet
        wallet_spending = {}
        total_spent = Decimal("0")

        async for wallet in Wallet.objects.filter(**filters).select_related("currency"):
            daily_spent = wallet.daily_spent
            monthly_spent = wallet.monthly_spent

            # Use appropriate spending based on period
            if period_days <= 7:
                spent = daily_spent
            else:
                spent = monthly_spent

            currency_code = wallet.currency.code
            if currency_code not in wallet_spending:
                wallet_spending[currency_code] = {
                    "total_spent": Decimal("0"),
                    "wallets": [],
                    "symbol": wallet.currency.symbol,
                }

            wallet_spending[currency_code]["total_spent"] += spent
            wallet_spending[currency_code]["wallets"].append(
                {
                    "wallet_id": str(wallet.wallet_id),
                    "name": wallet.name,
                    "spent": spent,
                    "limit": (
                        wallet.daily_limit if period_days <= 7 else wallet.monthly_limit
                    ),
                }
            )

            total_spent += spent * wallet.currency.exchange_rate_usd

        # Calculate daily averages
        daily_average = total_spent / max(period_days, 1)

        return {
            "period_days": period_days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_spent_usd": total_spent,
            "daily_average_usd": daily_average,
            "spending_by_currency": wallet_spending,
        }

    @staticmethod
    async def get_transaction_trends(
        user: User, period_days: int = 30
    ) -> Dict[str, Any]:
        """Get transaction trends and patterns"""

        # This would typically analyze actual transaction records
        # For now, we'll provide analytics based on wallet activity

        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)

        # Analyze wallet last transaction times
        recent_activity = await Wallet.objects.filter(
            user=user, last_transaction_at__gte=start_date
        ).acount()

        total_wallets = await Wallet.objects.filter(user=user).acount()
        activity_rate = (recent_activity / max(total_wallets, 1)) * 100

        # Virtual card usage
        card_transactions = await VirtualCard.objects.filter(
            wallet__user=user, last_used_at__gte=start_date
        ).acount()

        # QR code usage
        qr_usage = await QRCode.objects.filter(
            wallet__user=user, last_used_at__gte=start_date
        ).acount()

        # Split payment activity
        split_activity = (
            await SplitPayment.objects.filter(
                Q(created_by=user) | Q(participants__user=user),
                created_at__gte=start_date,
            )
            .distinct()
            .acount()
        )

        return {
            "period_days": period_days,
            "wallet_activity_rate": activity_rate,
            "recent_wallet_activity": recent_activity,
            "virtual_card_transactions": card_transactions,
            "qr_code_usage": qr_usage,
            "split_payment_activity": split_activity,
            "analysis_date": timezone.now().isoformat(),
        }

    @staticmethod
    async def get_security_insights(user: User) -> Dict[str, Any]:
        """Get security-related analytics"""

        # Wallet security analysis
        total_wallets = await Wallet.objects.filter(user=user).acount()
        pin_protected = await Wallet.objects.filter(
            user=user, requires_pin=True
        ).acount()
        biometric_protected = await Wallet.objects.filter(
            user=user, requires_biometric=True
        ).acount()

        # Security score calculation
        security_score = 0
        if user.biometrics_enabled:
            security_score += 30
        if pin_protected > 0:
            security_score += 20
        if biometric_protected > 0:
            security_score += 25
        if user.is_email_verified:
            security_score += 15
        if hasattr(user, "profile") and getattr(user.profile, "phone_verified", False):
            security_score += 10

        # Virtual card security
        total_cards = await VirtualCard.objects.filter(wallet__user=user).acount()
        active_cards = await VirtualCard.objects.filter(
            wallet__user=user, is_active=True, is_frozen=False
        ).acount()

        return {
            "wallet_security": {
                "total_wallets": total_wallets,
                "pin_protected": pin_protected,
                "biometric_protected": biometric_protected,
                "protection_rate": (
                    max(pin_protected, biometric_protected) / max(total_wallets, 1)
                )
                * 100,
            },
            "account_security": {
                "biometrics_enabled": user.biometrics_enabled,
                "email_verified": user.is_email_verified,
                "security_score": min(security_score, 100),
            },
            "virtual_card_security": {
                "total_cards": total_cards,
                "active_cards": active_cards,
                "frozen_cards": total_cards - active_cards,
            },
        }

    @staticmethod
    async def get_usage_patterns(user: User) -> Dict[str, Any]:
        """Analyze user's wallet usage patterns"""

        # Most used wallet types
        wallet_types = {}
        async for wallet in Wallet.objects.filter(user=user):
            wallet_type = wallet.wallet_type
            if wallet_type not in wallet_types:
                wallet_types[wallet_type] = {"count": 0, "total_balance": Decimal("0")}
            wallet_types[wallet_type]["count"] += 1
            wallet_types[wallet_type]["total_balance"] += wallet.balance

        # Currency preferences
        currency_usage = {}
        async for wallet in Wallet.objects.filter(user=user).select_related("currency"):
            currency = wallet.currency.code
            if currency not in currency_usage:
                currency_usage[currency] = {"wallets": 0, "balance": Decimal("0")}
            currency_usage[currency]["wallets"] += 1
            currency_usage[currency]["balance"] += wallet.balance

        # Feature adoption
        features_used = []
        if await VirtualCard.objects.filter(wallet__user=user).aexists():
            features_used.append("virtual_cards")
        if await QRCode.objects.filter(wallet__user=user).aexists():
            features_used.append("qr_payments")
        if await SplitPayment.objects.filter(created_by=user).aexists():
            features_used.append("split_payments")
        if await RecurringPayment.objects.filter(from_wallet__user=user).aexists():
            features_used.append("recurring_payments")

        return {
            "wallet_type_distribution": wallet_types,
            "currency_preferences": currency_usage,
            "features_adopted": features_used,
            "feature_adoption_rate": (len(features_used) / 4) * 100,  # 4 main features
        }

    @staticmethod
    async def get_monthly_summary(user: User, year: int, month: int) -> Dict[str, Any]:
        """Get monthly wallet activity summary"""

        # Get the first and last day of the month
        first_day = timezone.datetime(
            year, month, 1, tzinfo=timezone.get_current_timezone()
        )
        last_day = timezone.datetime(
            year,
            month,
            calendar.monthrange(year, month)[1],
            23,
            59,
            59,
            tzinfo=timezone.get_current_timezone(),
        )

        # Spending analysis
        monthly_spending = Decimal("0")
        async for wallet in Wallet.objects.filter(user=user):
            if (
                wallet.last_monthly_reset.month == month
                and wallet.last_monthly_reset.year == year
            ):
                monthly_spending += wallet.monthly_spent

        # Virtual card activity
        card_activity = await VirtualCard.objects.filter(
            wallet__user=user, last_used_at__range=[first_day, last_day]
        ).acount()

        # QR code activity
        qr_activity = await QRCode.objects.filter(
            wallet__user=user, last_used_at__range=[first_day, last_day]
        ).acount()

        # Split payments created
        split_payments_created = await SplitPayment.objects.filter(
            created_by=user, created_at__range=[first_day, last_day]
        ).acount()

        # Recurring payments executed
        recurring_executed = await RecurringPayment.objects.filter(
            from_wallet__user=user, last_payment_at__range=[first_day, last_day]
        ).acount()

        return {
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "total_spending": monthly_spending,
            "virtual_card_activity": card_activity,
            "qr_code_activity": qr_activity,
            "split_payments_created": split_payments_created,
            "recurring_payments_executed": recurring_executed,
            "period": {"start": first_day.isoformat(), "end": last_day.isoformat()},
        }

    @staticmethod
    async def get_yearly_summary(user: User, year: int) -> Dict[str, Any]:
        """Get yearly wallet activity summary"""

        yearly_data = {
            "year": year,
            "monthly_breakdown": [],
            "total_spending": Decimal("0"),
            "feature_usage": {
                "virtual_cards": 0,
                "qr_codes": 0,
                "split_payments": 0,
                "recurring_payments": 0,
            },
        }

        # Get data for each month
        for month in range(1, 13):
            monthly_data = await WalletAnalyticsService.get_monthly_summary(
                user, year, month
            )
            yearly_data["monthly_breakdown"].append(monthly_data)
            yearly_data["total_spending"] += monthly_data["total_spending"]
            yearly_data["feature_usage"]["virtual_cards"] += monthly_data[
                "virtual_card_activity"
            ]
            yearly_data["feature_usage"]["qr_codes"] += monthly_data["qr_code_activity"]
            yearly_data["feature_usage"]["split_payments"] += monthly_data[
                "split_payments_created"
            ]
            yearly_data["feature_usage"]["recurring_payments"] += monthly_data[
                "recurring_payments_executed"
            ]

        # Calculate averages
        yearly_data["monthly_average_spending"] = yearly_data["total_spending"] / 12

        return yearly_data

    @staticmethod
    async def export_wallet_data(user: User, format: str = "json") -> Dict[str, Any]:
        """Export user's wallet data for analysis or backup"""

        export_data = {
            "export_date": timezone.now().isoformat(),
            "user_id": str(user.id),
            "user_email": user.email,
            "wallets": [],
            "virtual_cards": [],
            "qr_codes": [],
            "split_payments": [],
            "recurring_payments": [],
        }

        # Export wallets
        async for wallet in Wallet.objects.filter(user=user).select_related("currency"):
            export_data["wallets"].append(
                {
                    "wallet_id": str(wallet.wallet_id),
                    "name": wallet.name,
                    "type": wallet.wallet_type,
                    "currency": wallet.currency.code,
                    "balance": float(wallet.balance),
                    "status": wallet.status,
                    "created_at": wallet.created_at.isoformat(),
                }
            )

        # Export virtual cards (masked data)
        async for card in VirtualCard.objects.filter(wallet__user=user).select_related(
            "wallet"
        ):
            export_data["virtual_cards"].append(
                {
                    "card_id": str(card.id),
                    "wallet_name": card.wallet.name,
                    "masked_number": card.masked_number,
                    "nickname": card.nickname,
                    "is_active": card.is_active,
                    "created_at": card.created_at.isoformat(),
                }
            )

        # Export QR codes
        async for qr in QRCode.objects.filter(wallet__user=user).select_related(
            "wallet"
        ):
            export_data["qr_codes"].append(
                {
                    "qr_id": str(qr.qr_id),
                    "wallet_name": qr.wallet.name,
                    "amount": float(qr.amount) if qr.amount else None,
                    "description": qr.description,
                    "times_used": qr.times_used,
                    "created_at": qr.created_at.isoformat(),
                }
            )

        # Export split payments
        async for split in SplitPayment.objects.filter(created_by=user).select_related(
            "currency"
        ):
            export_data["split_payments"].append(
                {
                    "payment_id": str(split.payment_id),
                    "total_amount": float(split.total_amount),
                    "currency": split.currency.code,
                    "description": split.description,
                    "status": split.status,
                    "created_at": split.created_at.isoformat(),
                }
            )

        # Export recurring payments
        async for recurring in RecurringPayment.objects.filter(
            from_wallet__user=user
        ).select_related("from_wallet"):
            export_data["recurring_payments"].append(
                {
                    "payment_id": str(recurring.payment_id),
                    "amount": float(recurring.amount),
                    "frequency": recurring.frequency,
                    "description": recurring.description,
                    "is_active": recurring.is_active,
                    "total_payments_made": recurring.total_payments_made,
                    "created_at": recurring.created_at.isoformat(),
                }
            )

        return export_data

    @staticmethod
    async def get_performance_metrics(user: User) -> Dict[str, Any]:
        """Get performance metrics for the wallet system"""

        # Response time simulation (in a real app, this would be measured)
        metrics = {
            "user_engagement": {
                "total_wallets": await Wallet.objects.filter(user=user).acount(),
                "active_features": 0,
                "last_activity": None,
            },
            "feature_performance": {
                "virtual_cards_adoption": False,
                "qr_payments_adoption": False,
                "split_payments_adoption": False,
                "recurring_payments_adoption": False,
            },
            "security_compliance": {
                "biometric_enabled": user.biometrics_enabled,
                "email_verified": user.is_email_verified,
                "protected_wallets_ratio": 0,
            },
        }

        # Check feature adoption
        if await VirtualCard.objects.filter(wallet__user=user).aexists():
            metrics["feature_performance"]["virtual_cards_adoption"] = True
            metrics["user_engagement"]["active_features"] += 1

        if await QRCode.objects.filter(wallet__user=user).aexists():
            metrics["feature_performance"]["qr_payments_adoption"] = True
            metrics["user_engagement"]["active_features"] += 1

        if await SplitPayment.objects.filter(created_by=user).aexists():
            metrics["feature_performance"]["split_payments_adoption"] = True
            metrics["user_engagement"]["active_features"] += 1

        if await RecurringPayment.objects.filter(from_wallet__user=user).aexists():
            metrics["feature_performance"]["recurring_payments_adoption"] = True
            metrics["user_engagement"]["active_features"] += 1

        # Get last activity
        latest_wallet = (
            await Wallet.objects.filter(user=user, last_transaction_at__isnull=False)
            .order_by("-last_transaction_at")
            .afirst()
        )

        if latest_wallet:
            metrics["user_engagement"][
                "last_activity"
            ] = latest_wallet.last_transaction_at.isoformat()

        # Security compliance
        total_wallets = await Wallet.objects.filter(user=user).acount()
        protected_wallets = await Wallet.objects.filter(
            Q(user=user) & (Q(requires_pin=True) | Q(requires_biometric=True))
        ).acount()

        if total_wallets > 0:
            metrics["security_compliance"]["protected_wallets_ratio"] = (
                protected_wallets / total_wallets
            )

        return metrics
