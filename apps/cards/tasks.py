"""
Celery tasks for cards app
"""

import logging
from celery import shared_task
from apps.cards.models import Card
from apps.cards.emails import CardEmailUtil

logger = logging.getLogger(__name__)


class CardEmailTasks:
    """Email tasks for card-related notifications"""

    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="cards.send_card_issued_email",
        queue="emails",
    )
    def send_card_issued_email(self, card_id: str):
        """Send card issuance notification email"""
        try:
            card = Card.objects.select_related(
                "user", "wallet", "wallet__currency"
            ).get_or_none(card_id=card_id)

            if not card:
                logger.error(f"Card {card_id} not found")
                return {"status": "failed", "error": "Card not found"}

            CardEmailUtil.send_card_issued_email(card)
            logger.info(
                f"Card issued email sent for card ending in {card.card_number[-4:] if card.card_number else 'N/A'}"
            )
            return {"status": "success", "card_id": str(card.card_id)}
        except Exception as exc:
            logger.error(f"Card issued email failed: {str(exc)}")
            raise self.retry(exc=exc)


# Expose task functions for imports
send_card_issued_email_async = CardEmailTasks.send_card_issued_email
