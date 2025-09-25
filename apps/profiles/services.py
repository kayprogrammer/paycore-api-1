import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
import requests

from .models import KYC, KYCStatus, VerificationMethod, RiskLevel

logger = logging.getLogger(__name__)


class KYCProviderInterface(ABC):
    """Abstract base class for KYC verification providers"""

    @abstractmethod
    def submit_verification(
        self, kyc: KYC, document_files: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit KYC data to provider for verification"""
        pass

    @abstractmethod
    def get_verification_status(self, provider_reference_id: str) -> Dict[str, Any]:
        """Get current verification status from provider"""
        pass

    @abstractmethod
    def map_provider_status(self, provider_status: str) -> KYCStatus:
        """Map provider-specific status to our KYCStatus"""
        pass


class MockKYCProvider(KYCProviderInterface):
    """Mock KYC provider for development and testing"""

    def __init__(self):
        # No actual API calls made - this is purely for local simulation
        pass

    def submit_verification(
        self, kyc: KYC, document_files: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mock verification submission"""
        import uuid
        import random

        # Simulate processing delay
        reference_id = f"mock_check_{uuid.uuid4().hex[:12]}"

        # Mock results based on user data for testing
        mock_results = ["in_progress", "complete", "consider"]
        if kyc.first_name.lower() == "test":
            status = "complete"
            result = "clear"
        elif kyc.first_name.lower() == "reject":
            status = "complete"
            result = "reject"
        else:
            status = random.choice(mock_results)
            result = "clear" if status == "complete" else "pending"

        logger.info(
            f"Mock KYC verification submitted for {kyc.user.email}: {reference_id}"
        )

        return {
            "provider_reference_id": reference_id,
            "applicant_id": f"mock_applicant_{uuid.uuid4().hex[:8]}",
            "status": status,
            "result": result,
        }

    def get_verification_status(self, provider_reference_id: str) -> Dict[str, Any]:
        """Mock status check"""
        # Simulate different outcomes based on reference ID
        if "test" in provider_reference_id:
            return {
                "id": provider_reference_id,
                "status": "complete",
                "result": "clear",
                "fraud_score": 0.1,
            }
        elif "reject" in provider_reference_id:
            return {
                "id": provider_reference_id,
                "status": "complete",
                "result": "reject",
                "fraud_score": 0.9,
            }
        else:
            return {
                "id": provider_reference_id,
                "status": "complete",
                "result": "consider",
                "fraud_score": 0.5,
            }

    def map_provider_status(self, provider_status: str) -> KYCStatus:
        """Map mock status to KYCStatus"""
        status_mapping = {
            "in_progress": KYCStatus.UNDER_REVIEW,
            "complete": KYCStatus.APPROVED,
            "consider": KYCStatus.UNDER_REVIEW,
            "reject": KYCStatus.REJECTED,
        }
        return status_mapping.get(provider_status, KYCStatus.PENDING)


class OnfidoProvider(KYCProviderInterface):
    """Onfido KYC verification provider implementation"""

    def __init__(self):
        self.api_key = settings.ONFIDO_API_KEY
        self.base_url = settings.ONFIDO_BASE_URL
        self.webhook_token = settings.ONFIDO_WEBHOOK_TOKEN

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Token token={self.api_key}",
            "Content-Type": "application/json",
        }

    def submit_verification(
        self, kyc: KYC, document_files: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit verification to Onfido"""
        try:
            # Create applicant
            applicant_data = {
                "first_name": kyc.first_name,
                "last_name": kyc.last_name,
                "dob": kyc.date_of_birth.isoformat(),
                "address": {
                    "street": kyc.address_line1,
                    "town": kyc.city,
                    "country": kyc.country.code if kyc.country else "US",
                    "postcode": kyc.postal_code or "",
                },
            }

            response = requests.post(
                f"{self.base_url}/applicants",
                json=applicant_data,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            applicant = response.json()
            applicant_id = applicant["id"]

            # Upload documents
            if "document_file" in document_files:
                self._upload_document(
                    applicant_id, document_files["document_file"], "front"
                )

            if "document_back_file" in document_files:
                self._upload_document(
                    applicant_id, document_files["document_back_file"], "back"
                )

            if "selfie_file" in document_files:
                self._upload_selfie(applicant_id, document_files["selfie_file"])

            # Create check
            check_data = {
                "applicant_id": applicant_id,
                "report_names": ["identity_enhanced"],
                "suppress_form_emails": True,
            }

            check_response = requests.post(
                f"{self.base_url}/checks", json=check_data, headers=self._get_headers()
            )
            check_response.raise_for_status()

            check = check_response.json()

            return {
                "provider_reference_id": check["id"],
                "applicant_id": applicant_id,
                "status": check["status"],
                "result": check.get("result", "pending"),
            }

        except Exception as e:
            logger.error(f"Onfido verification submission failed: {str(e)}")
            raise

    def _upload_document(self, applicant_id: str, file_data: Any, side: str):
        """Upload document to Onfido"""
        files = {
            "file": file_data,
            "type": "passport",  # This should be dynamic based on document type
            "side": side,
        }

        response = requests.post(
            f"{self.base_url}/documents",
            files=files,
            headers={"Authorization": f"Token token={self.api_key}"},
            data={"applicant_id": applicant_id},
        )
        response.raise_for_status()
        return response.json()

    def _upload_selfie(self, applicant_id: str, file_data: Any):
        """Upload selfie to Onfido"""
        files = {"file": file_data, "advanced_validation": "true"}

        response = requests.post(
            f"{self.base_url}/live_photos",
            files=files,
            headers={"Authorization": f"Token token={self.api_key}"},
            data={"applicant_id": applicant_id},
        )
        response.raise_for_status()
        return response.json()

    def get_verification_status(self, provider_reference_id: str) -> Dict[str, Any]:
        """Get verification status from Onfido"""
        response = requests.get(
            f"{self.base_url}/checks/{provider_reference_id}",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def map_provider_status(self, provider_status: str) -> KYCStatus:
        """Map Onfido status to our KYCStatus"""
        status_mapping = {
            "in_progress": KYCStatus.UNDER_REVIEW,
            "awaiting_applicant": KYCStatus.RESUBMIT_REQUIRED,
            "complete": KYCStatus.APPROVED,
            "withdrawn": KYCStatus.REJECTED,
            "paused": KYCStatus.UNDER_REVIEW,
            "reopened": KYCStatus.UNDER_REVIEW,
        }
        return status_mapping.get(provider_status, KYCStatus.PENDING)


class KYCValidationService:
    """Main service for handling KYC validation workflows"""

    def __init__(self, provider: Optional[KYCProviderInterface] = None):
        self.provider = provider or self._get_default_provider()

    def _get_default_provider(self) -> KYCProviderInterface:
        """Get the configured KYC provider"""
        provider_name = getattr(settings, "KYC_PROVIDER", "mock")

        if provider_name == "onfido":
            return OnfidoProvider()
        elif provider_name == "mock":
            return MockKYCProvider()
        else:
            raise ValueError(f"Unsupported KYC provider: {provider_name}")

    def submit_kyc_for_verification(
        self, kyc: KYC, document_files: Dict[str, Any]
    ) -> bool:
        """Submit KYC to third-party provider for verification"""
        try:
            # Update status to under review
            kyc.status = KYCStatus.UNDER_REVIEW
            kyc.verification_method = VerificationMethod.AUTOMATED
            kyc.provider_name = settings.KYC_PROVIDER

            # Submit to provider
            result = self.provider.submit_verification(kyc, document_files)

            # Update KYC with provider response
            kyc.provider_reference_id = result["provider_reference_id"]
            kyc.provider_status = result["status"]

            # Set risk level based on initial assessment
            kyc.risk_level = self._assess_risk_level(kyc, result)

            kyc.save()

            logger.info(
                f"KYC {kyc.id} submitted for verification with reference {result['provider_reference_id']}"
            )
            return True

        except Exception as e:
            logger.error(f"KYC submission failed for {kyc.id}: {str(e)}")
            kyc.status = KYCStatus.PENDING
            kyc.notes = f"Submission failed: {str(e)}"
            kyc.save()
            return False

    def process_webhook_update(self, webhook_data: Dict[str, Any]) -> bool:
        """Process webhook update from KYC provider"""
        try:
            provider_reference_id = webhook_data.get("object", {}).get("id")
            if not provider_reference_id:
                logger.error("No reference ID in webhook data")
                return False

            kyc = KYC.objects.get_or_none(provider_reference_id=provider_reference_id)
            if not kyc:
                logger.error(f"No KYC found for reference ID {provider_reference_id}")
                return False

            # Get latest status from provider
            status_data = self.provider.get_verification_status(provider_reference_id)

            # Update KYC status
            old_status = kyc.status
            kyc.provider_status = status_data.get("status")
            kyc.status = self.provider.map_provider_status(kyc.provider_status)
            kyc.webhook_verified_at = timezone.now()

            # Update risk assessment if completed
            if kyc.status in [KYCStatus.APPROVED, KYCStatus.REJECTED]:
                kyc.reviewed_at = timezone.now()
                kyc.risk_level = self._assess_final_risk_level(kyc, status_data)

                # Set AML check based on provider results
                kyc.aml_check_passed = status_data.get("result") == "clear"

                # Extract fraud score if available
                if "fraud_score" in status_data:
                    kyc.fraud_score = status_data["fraud_score"]

            kyc.save()

            logger.info(f"KYC {kyc.id} updated from {old_status} to {kyc.status}")
            return True

        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return False

    def manual_review_required(self, kyc: KYC, reason: str) -> None:
        """Mark KYC for manual review"""
        kyc.status = KYCStatus.UNDER_REVIEW
        kyc.verification_method = VerificationMethod.MANUAL
        kyc.notes = f"Manual review required: {reason}"
        kyc.risk_level = RiskLevel.HIGH
        kyc.save()

        logger.info(f"KYC {kyc.id} marked for manual review: {reason}")

    def approve_kyc(self, kyc: KYC, reviewer_notes: str = "") -> None:
        """Manually approve KYC"""
        kyc.status = KYCStatus.APPROVED
        kyc.reviewed_at = timezone.now()
        kyc.notes = reviewer_notes
        kyc.aml_check_passed = True
        kyc.save()

        logger.info(f"KYC {kyc.id} manually approved")

    def reject_kyc(self, kyc: KYC, rejection_reason: str) -> None:
        """Reject KYC with reason"""
        kyc.status = KYCStatus.REJECTED
        kyc.reviewed_at = timezone.now()
        kyc.rejection_reason = rejection_reason
        kyc.aml_check_passed = False
        kyc.save()

        logger.info(f"KYC {kyc.id} rejected: {rejection_reason}")

    def _assess_risk_level(
        self, kyc: KYC, provider_result: Dict[str, Any]
    ) -> RiskLevel:
        """Assess initial risk level based on KYC data and provider response"""
        risk_factors = 0

        # Age-based risk
        age = (timezone.now().date() - kyc.date_of_birth).days // 365
        if age < 21 or age > 65:
            risk_factors += 1

        # PEP flag
        if kyc.is_politically_exposed:
            risk_factors += 2

        # Provider-specific risk indicators
        if provider_result.get("result") == "consider":
            risk_factors += 1

        if risk_factors >= 3:
            return RiskLevel.HIGH
        elif risk_factors >= 1:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _assess_final_risk_level(
        self, kyc: KYC, status_data: Dict[str, Any]
    ) -> RiskLevel:
        """Final risk assessment after provider verification"""
        risk_factors = 0

        # Provider result assessment
        provider_result = status_data.get("result")
        if provider_result == "clear":
            risk_factors += 0
        elif provider_result == "consider":
            risk_factors += 2
        else:  # rejected or unknown
            risk_factors += 3

        # Additional KYC-based risk factors
        if kyc.is_politically_exposed:
            risk_factors += 2

        # Age-based risk (same as initial assessment)
        age = (timezone.now().date() - kyc.date_of_birth).days // 365
        if age < 21 or age > 65:
            risk_factors += 1

        # Fraud score consideration
        if kyc.fraud_score and kyc.fraud_score > 0.7:
            risk_factors += 1

        # Document expiry check
        if (
            kyc.document_expiry_date
            and kyc.document_expiry_date < timezone.now().date()
        ):
            risk_factors += 1

        if risk_factors >= 4:
            return RiskLevel.HIGH
        elif risk_factors >= 2:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
