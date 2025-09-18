from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.utils import timezone
from datetime import timedelta
import random, threading, logging

logger = logging.getLogger(__name__)


# We're using threading for now, but a better option is celery and we'll update it later
class EmailThread(threading.Thread):
    def __init__(self, email):
        self.email = email
        super().__init__()

    def run(self):
        try:
            self.email.send()
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)


class EmailUtil:
    OTP_EXPIRY_MINUTES = 15

    @classmethod
    def _send_email(cls, subject, template_name, context, recipient):
        """Internal helper to render template and send email."""
        try:
            message = render_to_string(template_name, context)
            email_message = EmailMessage(subject=subject, body=message, to=[recipient])
            email_message.content_subtype = "html"
            email_message.send()  # Use EmailThread(email_message).start() if you don't want to use celery
        except Exception as e:
            logger.error(f"Email sending failed for {recipient}: {e}", exc_info=True)

    @classmethod
    def send_otp(cls, user, purpose):
        code = random.randint(100000, 999999)
        user.otp_code = code
        user.otp_expires_at = timezone.now() + timedelta(minutes=cls.OTP_EXPIRY_MINUTES)
        user.save(update_fields=["otp_code", "otp_expires_at"])

        cls._send_email(
            subject=purpose.title(),
            template_name="email-otp.html",
            context={
                "name": user.full_name,
                "otp": code,
                "purpose": purpose,
                "expiry_minutes": cls.OTP_EXPIRY_MINUTES,
            },
            recipient=user.email,
        )

    @classmethod
    def password_reset_confirmation(cls, user):
        cls._send_email(
            subject="Password Reset Successful!",
            template_name="password-reset-success.html",
            context={"name": user.full_name},
            recipient=user.email,
        )

    @classmethod
    def welcome_email(cls, user):
        cls._send_email(
            subject="Account verified!",
            template_name="welcome.html",
            context={"name": user.full_name},
            recipient=user.email,
        )
