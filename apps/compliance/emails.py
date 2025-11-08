from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class KYCEmailUtil:
    """Email utilities for KYC-related notifications"""

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
    def send_kyc_approved_email(cls, kyc_verification):
        """Send KYC approval notification to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            dashboard_url = f"{frontend_url}/dashboard"

            context = {
                "user_name": kyc_verification.user.full_name,
                "verification_level": kyc_verification.verification_level.replace(
                    "_", " "
                ).title(),
                "verified_date": kyc_verification.verified_at.strftime("%B %d, %Y"),
                "reference_number": kyc_verification.reference_number,
                "dashboard_url": dashboard_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject="KYC Verification Approved!",
                template_name="kyc-approved.html",
                context=context,
                recipient=kyc_verification.user.email,
            )
        except Exception as e:
            logger.error(f"Failed to send KYC approval email: {e}", exc_info=True)

    @classmethod
    def send_kyc_pending_email(cls, kyc_verification):
        """Send KYC pending review notification to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            status_url = f"{frontend_url}/kyc/status"

            # Get submitted documents list
            submitted_documents = []
            if hasattr(kyc_verification, "documents"):
                submitted_documents = [
                    doc.document_type.replace("_", " ").title()
                    for doc in kyc_verification.documents.all()
                ]

            context = {
                "user_name": kyc_verification.user.full_name,
                "submission_date": kyc_verification.submitted_at.strftime(
                    "%B %d, %Y at %I:%M %p"
                ),
                "reference_number": kyc_verification.reference_number,
                "submitted_documents": submitted_documents,
                "status_url": status_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject="KYC Verification Under Review",
                template_name="kyc-pending.html",
                context=context,
                recipient=kyc_verification.user.email,
            )
        except Exception as e:
            logger.error(f"Failed to send KYC pending email: {e}", exc_info=True)

    @classmethod
    def send_kyc_rejected_email(cls, kyc_verification):
        """Send KYC rejection/action required notification to user"""
        try:
            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            resubmit_url = f"{frontend_url}/kyc/resubmit"

            # Get missing documents list if available
            missing_documents = []
            if (
                hasattr(kyc_verification, "missing_documents")
                and kyc_verification.missing_documents
            ):
                missing_documents = kyc_verification.missing_documents

            context = {
                "user_name": kyc_verification.user.full_name,
                "reviewed_date": kyc_verification.reviewed_at.strftime("%B %d, %Y"),
                "reference_number": kyc_verification.reference_number,
                "rejection_reason": kyc_verification.rejection_reason
                or "The submitted documents require clarification or resubmission.",
                "missing_documents": missing_documents,
                "resubmit_url": resubmit_url,
                "current_year": datetime.now().year,
                "terms_url": f"{frontend_url}/terms",
                "privacy_url": f"{frontend_url}/privacy",
            }

            cls._send_email(
                subject="KYC Verification - Action Required",
                template_name="kyc-rejected.html",
                context=context,
                recipient=kyc_verification.user.email,
            )
        except Exception as e:
            logger.error(f"Failed to send KYC rejection email: {e}", exc_info=True)
