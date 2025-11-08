from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class InvestmentEmailUtil:
    """Email utilities for investment-related notifications"""

    @classmethod
    def _send_email(cls, subject, template_name, context, recipient):
        """Internal helper to render template and send email."""
        try:
            message = render_to_string(template_name, context)
            email_message = EmailMessage(subject=subject, body=message, to=[recipient])
            email_message.content_subtype = "html"
            email_message.send()
            logger.info(f"Email sent successfully to {recipient}: {subject}")
        except Exception as e:
            logger.error(f"Email sending failed for {recipient}: {e}", exc_info=True)

    @classmethod
    def send_investment_created_email(cls, investment):
        """Send investment creation confirmation to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            investment_url = f"{frontend_url}/investments/{investment.investment_id}"

            product_type_display = investment.product.get_product_type_display()
            payout_frequency_display = investment.product.get_payout_frequency_display()

            total_value = investment.principal_amount + investment.expected_returns

            context = {
                "user_name": investment.user.full_name,
                "product_name": investment.product.name,
                "product_type": product_type_display,
                "principal_amount": f"{investment.principal_amount:,.2f}",
                "interest_rate": f"{investment.interest_rate}",
                "duration_days": investment.duration_days,
                "start_date": investment.start_date.strftime("%B %d, %Y"),
                "maturity_date": investment.maturity_date.strftime("%B %d, %Y"),
                "expected_returns": f"{investment.expected_returns:,.2f}",
                "total_value_at_maturity": f"{total_value:,.2f}",
                "currency_symbol": investment.wallet.currency.symbol,
                "payout_frequency": payout_frequency_display,
                "investment_url": investment_url,
                "current_year": datetime.now().year,
            }

            cls._send_email(
                subject=f"Investment Created - {investment.product.name}",
                template_name="investment-created.html",
                context=context,
                recipient=investment.user.email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send investment created email for {investment.investment_id}: {e}",
                exc_info=True,
            )

    @classmethod
    def send_investment_matured_email(cls, investment):
        """Send investment maturity notification to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            investment_url = f"{frontend_url}/investments"
            portfolio_url = f"{frontend_url}/investments/portfolio"

            product_type_display = investment.product.get_product_type_display()
            auto_renewed = (
                hasattr(investment, "renewals") and investment.renewals.exists()
            )

            context = {
                "user_name": investment.user.full_name,
                "product_name": investment.product.name,
                "product_type": product_type_display,
                "principal_amount": f"{investment.principal_amount:,.2f}",
                "actual_returns": f"{investment.actual_returns:,.2f}",
                "total_payout": f"{investment.total_payout:,.2f}",
                "duration_days": investment.duration_days,
                "start_date": investment.start_date.strftime("%B %d, %Y"),
                "maturity_date": (
                    investment.actual_maturity_date.strftime("%B %d, %Y")
                    if investment.actual_maturity_date
                    else investment.maturity_date.strftime("%B %d, %Y")
                ),
                "currency_symbol": investment.wallet.currency.symbol,
                "wallet_name": f"{investment.wallet.currency.name} Wallet",
                "new_balance": f"{investment.wallet.balance:,.2f}",
                "auto_renewed": auto_renewed,
                "investment_url": investment_url,
                "portfolio_url": portfolio_url,
                "current_year": datetime.now().year,
            }

            cls._send_email(
                subject=f"Investment Matured - {investment.product.name}",
                template_name="investment-matured.html",
                context=context,
                recipient=investment.user.email,
            )
        except Exception as e:
            logger.error(
                f"Failed to send investment matured email for {investment.investment_id}: {e}",
                exc_info=True,
            )
