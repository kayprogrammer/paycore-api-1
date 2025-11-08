"""
Celery tasks for wallets app
"""

import logging
from celery import shared_task
from apps.wallets.models import Wallet
from apps.wallets.emails import WalletEmailUtil

logger = logging.getLogger(__name__)


class WalletEmailTasks:
    """Email tasks for wallet-related notifications"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="wallets.send_wallet_created_email",
        queue="emails",
    )
    def send_wallet_created_email(self, wallet_id: str):
        """Send wallet creation notification email"""
        try:
            wallet = Wallet.objects.select_related("user", "currency").get_or_none(
                wallet_id=wallet_id
            )

            if not wallet:
                logger.error(f"Wallet {wallet_id} not found")
                return {"status": "failed", "error": "Wallet not found"}

            WalletEmailUtil.send_wallet_created_email(wallet)
            logger.info(f"Wallet created email sent for wallet {wallet.wallet_id}")
            return {"status": "success", "wallet_id": str(wallet.wallet_id)}
        except Exception as exc:
            logger.error(f"Wallet created email failed: {str(exc)}")
            raise self.retry(exc=exc)


# Expose task functions for imports
send_wallet_created_email_async = WalletEmailTasks.send_wallet_created_email
