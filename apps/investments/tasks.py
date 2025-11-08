import logging
from celery import shared_task
from django.utils import timezone
from asgiref.sync import async_to_sync
from apps.investments.emails import InvestmentEmailUtil

from apps.investments.models import Investment, InvestmentReturn, InvestmentStatus
from apps.investments.services.investment_processor import InvestmentProcessor
from apps.investments.services.investment_manager import InvestmentManager
from apps.investments.schemas import RenewInvestmentSchema
from apps.accounts.models import User

logger = logging.getLogger(__name__)


class InvestmentTasks:
    """Automated investment processing tasks"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 2, "countdown": 300},
        name="investments.process_matured_investments",
        queue="investments",
    )
    def process_matured_investments(self):
        """
        Process matured investments - pay out principal + returns
        Runs daily to check for matured investments
        """
        try:
            today = timezone.now()
            processed_count = 0
            failed_count = 0
            renewed_count = 0

            matured_investments = Investment.objects.filter(
                status=InvestmentStatus.ACTIVE, maturity_date__lte=today
            ).select_related("user", "product", "wallet", "wallet__currency")

            for investment in matured_investments:
                try:
                    # Check if investment has auto-renew enabled
                    if investment.auto_renew and investment.product.allows_auto_renewal:
                        renew_data = RenewInvestmentSchema(
                            duration_days=investment.duration_days, auto_renew=True
                        )

                        new_investment = async_to_sync(
                            InvestmentManager.renew_investment
                        )(investment.user, investment.investment_id, renew_data)

                        renewed_count += 1
                        logger.info(
                            f"Investment {investment.investment_id} auto-renewed as {new_investment.investment_id}"
                        )
                    else:
                        # Process maturity payout
                        processed_investment = async_to_sync(
                            InvestmentProcessor.process_maturity
                        )(investment.investment_id)

                        processed_count += 1
                        logger.info(
                            f"Investment {investment.investment_id} matured - paid out {processed_investment.total_payout}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to process matured investment {investment.investment_id}: {str(e)}"
                    )
                    failed_count += 1

            logger.info(
                f"Maturity processing complete: {processed_count} paid out, {renewed_count} renewed, {failed_count} failed"
            )

            return {
                "status": "success",
                "processed": processed_count,
                "renewed": renewed_count,
                "failed": failed_count,
            }

        except Exception as exc:
            logger.error(f"Maturity processing batch failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 2, "countdown": 300},
        name="investments.process_periodic_returns",
        queue="investments",
    )
    def process_periodic_returns(self):
        """
        Process periodic return payouts (monthly, quarterly, etc.)
        Runs daily to check for due returns
        """
        try:
            today = timezone.now()
            processed_count = 0
            failed_count = 0

            due_returns = InvestmentReturn.objects.filter(
                is_paid=False,
                payout_date__lte=today,
                investment__status=InvestmentStatus.ACTIVE,
            ).select_related(
                "investment",
                "investment__user",
                "investment__wallet",
                "investment__wallet__currency",
            )

            for investment_return in due_returns:
                try:
                    processed_return = async_to_sync(
                        InvestmentProcessor.process_periodic_return
                    )(investment_return.return_id)

                    processed_count += 1
                    logger.info(
                        f"Periodic return {investment_return.return_id} processed - paid {processed_return.amount}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to process return {investment_return.return_id}: {str(e)}"
                    )
                    failed_count += 1

            logger.info(
                f"Periodic returns processing complete: {processed_count} paid, {failed_count} failed"
            )

            return {
                "status": "success",
                "processed": processed_count,
                "failed": failed_count,
            }

        except Exception as exc:
            logger.error(f"Periodic returns processing batch failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(name="investments.update_portfolios", queue="maintenance")
    def update_portfolios():
        """
        Update all user investment portfolios
        Runs daily to recalculate portfolio values
        """

        try:
            updated_count = 0
            failed_count = 0

            users_with_investments = User.objects.filter(
                investments__isnull=False
            ).distinct()

            for user in users_with_investments:
                try:
                    portfolio = async_to_sync(InvestmentProcessor.update_portfolio)(
                        user
                    )
                    updated_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to update portfolio for user {user.id}: {str(e)}"
                    )
                    failed_count += 1

            logger.info(
                f"Portfolio update complete: {updated_count} updated, {failed_count} failed"
            )

            return {
                "status": "success",
                "updated": updated_count,
                "failed": failed_count,
            }

        except Exception as e:
            logger.error(f"Portfolio update batch failed: {str(e)}")
            return {"status": "failed", "error": str(e)}


# ==================== INVESTMENT EMAIL TASKS ====================


class InvestmentEmailTasks:
    """Email tasks for investment-related notifications"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="investments.send_investment_created_email",
        queue="emails",
    )
    def send_investment_created_email(self, investment_id: str):
        """Send investment creation confirmation email"""
        try:
            investment = Investment.objects.select_related(
                "user", "product", "wallet", "wallet__currency"
            ).get_or_none(investment_id=investment_id)

            if not investment:
                logger.error(f"Investment {investment_id} not found")
                return {"status": "failed", "error": "Investment not found"}

            InvestmentEmailUtil.send_investment_created_email(investment)
            logger.info(
                f"Investment created email sent for investment {investment.investment_id}"
            )
            return {"status": "success", "investment_id": str(investment.investment_id)}
        except Exception as exc:
            logger.error(f"Investment created email failed: {str(exc)}")
            raise self.retry(exc=exc)

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="investments.send_investment_matured_email",
        queue="emails",
    )
    def send_investment_matured_email(self, investment_id: str):
        """Send investment maturity notification email"""
        try:
            investment = Investment.objects.select_related(
                "user", "product", "wallet", "wallet__currency"
            ).get_or_none(investment_id=investment_id)

            if not investment:
                logger.error(f"Investment {investment_id} not found")
                return {"status": "failed", "error": "Investment not found"}

            InvestmentEmailUtil.send_investment_matured_email(investment)
            logger.info(
                f"Investment matured email sent for investment {investment.investment_id}"
            )
            return {"status": "success", "investment_id": str(investment.investment_id)}
        except Exception as exc:
            logger.error(f"Investment matured email failed: {str(exc)}")
            raise self.retry(exc=exc)


# Expose task functions for imports
process_matured_investments = InvestmentTasks.process_matured_investments
process_periodic_returns = InvestmentTasks.process_periodic_returns
update_portfolios = InvestmentTasks.update_portfolios
send_investment_created_email_async = InvestmentEmailTasks.send_investment_created_email
send_investment_matured_email_async = InvestmentEmailTasks.send_investment_matured_email
