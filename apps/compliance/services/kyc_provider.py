import logging
from abc import ABC, abstractmethod
import random
from typing import Dict, Any, Optional
import uuid
from django.conf import settings
from django.utils import timezone
import requests

from apps.compliance.models import (
    KYCVerification,
    KYCDocument,
    KYCStatus,
    RiskLevel,
    AMLCheck,
)

logger = logging.getLogger(__name__)


class KYCProviderInterface(ABC):
    """Abstract base class for KYC verification providers"""

    @abstractmethod
    def submit_verification(
        self, kyc: KYCVerification, documents: list[KYCDocument]
    ) -> Dict[str, Any]:
        """Submit KYC data to provider for verification"""
        pass

    @abstractmethod
    def get_verification_status(self, provider_reference_id: str) -> Dict[str, Any]:
        """Get current verification status from provider"""
        pass

    @abstractmethod
    def map_provider_status(self, provider_status: str) -> str:
        """Map provider-specific status to our KYCStatus"""
        pass


class MockKYCProvider(KYCProviderInterface):
    """Mock KYC provider for development and testing"""

    def __init__(self):
        self.provider_name = "Mock Provider"

    def submit_verification(
        self, kyc: KYCVerification, documents: list[KYCDocument]
    ) -> Dict[str, Any]:
        reference_id = f"mock_check_{uuid.uuid4().hex[:12]}"

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
            "confidence": random.uniform(0.7, 0.99),
        }

    def get_verification_status(self, provider_reference_id: str) -> Dict[str, Any]:
        """Get mock verification status"""

        # Simulate different outcomes based on reference ID
        if "test" in provider_reference_id:
            return {
                "id": provider_reference_id,
                "status": "complete",
                "result": "clear",
                "fraud_score": 0.1,
                "breakdown": {
                    "document_verification": "clear",
                    "face_match": "clear",
                    "data_validation": "clear",
                },
            }
        elif "reject" in provider_reference_id:
            return {
                "id": provider_reference_id,
                "status": "complete",
                "result": "reject",
                "fraud_score": 0.9,
                "breakdown": {
                    "document_verification": "reject",
                    "face_match": "clear",
                    "data_validation": "consider",
                },
            }
        else:
            return {
                "id": provider_reference_id,
                "status": "complete",
                "result": "consider",
                "fraud_score": 0.5,
                "breakdown": {
                    "document_verification": "clear",
                    "face_match": "consider",
                    "data_validation": "clear",
                },
            }

    def map_provider_status(self, provider_status: str) -> str:
        """Map mock provider status to KYCStatus"""

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
        self.api_key = getattr(settings, "ONFIDO_API_KEY", None)
        self.base_url = getattr(
            settings, "ONFIDO_BASE_URL", "https://api.onfido.com/v3"
        )
        self.webhook_token = getattr(settings, "ONFIDO_WEBHOOK_TOKEN", None)
        self.provider_name = "Onfido"

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        return {
            "Authorization": f"Token token={self.api_key}",
            "Content-Type": "application/json",
        }

    def submit_verification(
        self, kyc: KYCVerification, documents: list[KYCDocument]
    ) -> Dict[str, Any]:
        """Submit KYC to Onfido for verification"""

        try:
            # Create applicant
            applicant_data = {
                "first_name": kyc.first_name,
                "last_name": kyc.last_name,
                "dob": kyc.date_of_birth.isoformat(),
                "email": kyc.user.email,
                "address": {
                    "street": kyc.address_line_1,
                    "town": kyc.city,
                    "state": kyc.state,
                    "country": kyc.country,
                    "postcode": kyc.postal_code or "",
                },
            }

            response = requests.post(
                f"{self.base_url}/applicants",
                json=applicant_data,
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()

            applicant = response.json()
            applicant_id = applicant["id"]

            # Upload documents
            for document in documents:
                if document.file:
                    self._upload_document(applicant_id, document)

            # Create check
            check_data = {
                "applicant_id": applicant_id,
                "report_names": ["identity_enhanced", "document"],
                "consider": ["clear"],
                "suppress_form_emails": True,
            }

            check_response = requests.post(
                f"{self.base_url}/checks",
                json=check_data,
                headers=self._get_headers(),
                timeout=30,
            )
            check_response.raise_for_status()

            check = check_response.json()

            logger.info(
                f"Onfido check created: {check['id']} for applicant {applicant_id}"
            )

            return {
                "provider_reference_id": check["id"],
                "applicant_id": applicant_id,
                "status": check["status"],
                "result": check.get("result", "pending"),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Onfido API request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Onfido verification submission failed: {str(e)}")
            raise

    def _upload_document(self, applicant_id: str, document: KYCDocument):
        """Upload document to Onfido"""

        try:
            # Map our document types to Onfido's
            document_type_mapping = {
                "passport": "passport",
                "national_id": "national_identity_card",
                "drivers_license": "driving_licence",
                "residence_permit": "residence_permit",
            }

            onfido_doc_type = document_type_mapping.get(
                document.document_type, "unknown"
            )

            files = {
                "file": (document.file_name, document.file.read(), "image/jpeg"),
            }

            data = {
                "applicant_id": applicant_id,
                "type": onfido_doc_type,
            }

            response = requests.post(
                f"{self.base_url}/documents",
                files=files,
                data=data,
                headers={"Authorization": f"Token token={self.api_key}"},
                timeout=60,
            )
            response.raise_for_status()

            logger.info(f"Document uploaded to Onfido: {document.document_type}")
            return response.json()

        except Exception as e:
            logger.error(f"Onfido document upload failed: {str(e)}")
            raise

    def get_verification_status(self, provider_reference_id: str) -> Dict[str, Any]:
        """Get verification status from Onfido"""

        try:
            response = requests.get(
                f"{self.base_url}/checks/{provider_reference_id}",
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Onfido status check failed: {str(e)}")
            raise

    def map_provider_status(self, provider_status: str) -> str:
        """Map Onfido status to our KYCStatus"""

        status_mapping = {
            "in_progress": KYCStatus.UNDER_REVIEW,
            "awaiting_applicant": KYCStatus.PENDING,
            "complete": KYCStatus.APPROVED,
            "withdrawn": KYCStatus.REJECTED,
            "paused": KYCStatus.UNDER_REVIEW,
            "reopened": KYCStatus.UNDER_REVIEW,
        }
        return status_mapping.get(provider_status, KYCStatus.PENDING)


class JumioProvider(KYCProviderInterface):
    """
    Jumio KYC verification provider implementation
    Uses Jumio's Identity Verification API (v4)
    """

    def __init__(self):
        self.api_token = getattr(settings, "JUMIO_API_TOKEN", None)
        self.api_secret = getattr(settings, "JUMIO_API_SECRET", None)
        self.base_url = getattr(
            settings, "JUMIO_BASE_URL", "https://account.amer-1.jumio.ai/api/v1"
        )
        self.provider_name = "Jumio"

    def _get_auth(self) -> tuple:
        """Get HTTP Basic Auth credentials"""
        return (self.api_token, self.api_secret)

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        return {
            "Content-Type": "application/json",
            "User-Agent": "Paycore-API/1.0",
        }

    def submit_verification(
        self, kyc: KYCVerification, documents: list[KYCDocument]
    ) -> Dict[str, Any]:
        """Submit KYC to Jumio for verification"""

        try:
            # Step 1: Create account (workflow)
            workflow_data = {
                "customerInternalReference": str(kyc.kyc_id),
                "workflowDefinition": {
                    "key": 1,  # ID verification workflow
                    "credentials": [
                        {
                            "category": "ID",
                            "type": {
                                "values": ["DRIVING_LICENSE", "ID_CARD", "PASSPORT"]
                            },
                            "country": {"values": [kyc.country]},
                        }
                    ],
                },
                "userReference": str(kyc.user.id),
            }

            # Add customer data
            workflow_data["callbackUrl"] = (
                f"{settings.SITE_URL}/api/v1/compliance/webhooks/kyc"
            )

            response = requests.post(
                f"{self.base_url}/accounts",
                json=workflow_data,
                auth=self._get_auth(),
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()

            account_data = response.json()
            account_id = account_data.get("account", {}).get("id")
            workflow_execution_id = account_data.get("workflowExecution", {}).get("id")

            if not account_id or not workflow_execution_id:
                raise Exception("Invalid response from Jumio - missing IDs")

            # Step 2: Upload documents (if provided directly)
            # Note: Jumio typically uses redirect/iframe for user to upload directly
            # But we can also upload via API

            if documents:
                self._upload_documents(account_id, workflow_execution_id, documents)

            logger.info(
                f"Jumio account created: {account_id}, workflow: {workflow_execution_id}"
            )

            return {
                "provider_reference_id": workflow_execution_id,
                "applicant_id": account_id,
                "status": "in_progress",
                "result": "pending",
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Jumio API request failed: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Jumio error response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Jumio verification submission failed: {str(e)}")
            raise

    def _upload_documents(
        self, account_id: str, workflow_execution_id: str, documents: list[KYCDocument]
    ):
        """Upload documents to Jumio"""

        try:
            for document in documents:
                if not document.file:
                    continue

                # Map our document types to Jumio's classifier
                classifier_mapping = {
                    "passport": "ID",
                    "national_id": "ID",
                    "drivers_license": "ID",
                    "selfie": "FACEMAP",
                    "utility_bill": "PROOF_OF_RESIDENCE",
                    "bank_statement": "PROOF_OF_RESIDENCE",
                }

                classifier = classifier_mapping.get(document.document_type, "ID")

                # Read file content
                file_content = document.file.read()

                # Prepare multipart upload
                files = {
                    "file": (document.file_name, file_content, "image/jpeg"),
                }

                data = {
                    "classifier": classifier,
                }

                response = requests.post(
                    f"{self.base_url}/accounts/{account_id}/workflow-executions/{workflow_execution_id}/image",
                    files=files,
                    data=data,
                    auth=self._get_auth(),
                    timeout=60,
                )
                response.raise_for_status()

                logger.info(
                    f"Document uploaded to Jumio: {document.document_type} for account {account_id}"
                )

        except Exception as e:
            logger.error(f"Jumio document upload failed: {str(e)}")
            raise

    def get_verification_status(self, provider_reference_id: str) -> Dict[str, Any]:
        """Get verification status from Jumio"""

        try:
            # Jumio uses workflow execution ID to get status
            # We need to retrieve the account associated with this workflow
            # Since we store workflow_execution_id as provider_reference_id

            # Query workflow execution details
            response = requests.get(
                f"{self.base_url}/workflow-executions/{provider_reference_id}",
                auth=self._get_auth(),
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()

            workflow_data = response.json()

            # Extract status and decision
            status = workflow_data.get("status", "IN_PROGRESS")
            decision = workflow_data.get("decision", {})

            result_status = "pending"
            if status == "PROCESSED":
                decision_type = decision.get("type", "NOT_EXECUTED")
                if decision_type == "ACCEPTED":
                    result_status = "clear"
                elif decision_type == "REJECTED":
                    result_status = "reject"
                else:
                    result_status = "consider"

            # Extract fraud/risk score if available
            fraud_score = 0.0
            risk_labels = decision.get("labels", [])
            if "FRAUD" in risk_labels:
                fraud_score = 0.9
            elif "WARN" in risk_labels:
                fraud_score = 0.5
            else:
                fraud_score = 0.1

            return {
                "id": provider_reference_id,
                "status": status,
                "result": result_status,
                "fraud_score": fraud_score,
                "decision": decision,
                "breakdown": workflow_data.get("capabilities", {}),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Jumio status check failed: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Jumio error response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Jumio status retrieval failed: {str(e)}")
            raise

    def map_provider_status(self, provider_status: str) -> str:
        """Map Jumio status to our KYCStatus"""

        # Jumio workflow statuses:
        # INITIATED, ACQUIRED, PROCESSING, PROCESSED, EXPIRED, FAILED
        status_mapping = {
            "INITIATED": KYCStatus.PENDING,
            "ACQUIRED": KYCStatus.UNDER_REVIEW,
            "PROCESSING": KYCStatus.UNDER_REVIEW,
            "PROCESSED": KYCStatus.APPROVED,  # Will be refined by decision
            "EXPIRED": KYCStatus.EXPIRED,
            "FAILED": KYCStatus.REJECTED,
        }
        return status_mapping.get(provider_status, KYCStatus.PENDING)

    def map_decision_to_status(self, decision_type: str) -> str:
        """Map Jumio decision to our KYCStatus"""

        # Jumio decision types:
        # ACCEPTED, REJECTED, NOT_EXECUTED, WARNING
        decision_mapping = {
            "ACCEPTED": KYCStatus.APPROVED,
            "REJECTED": KYCStatus.REJECTED,
            "NOT_EXECUTED": KYCStatus.UNDER_REVIEW,
            "WARNING": KYCStatus.UNDER_REVIEW,
        }
        return decision_mapping.get(decision_type, KYCStatus.UNDER_REVIEW)


class KYCProviderService:
    """Service to manage KYC provider operations"""

    def __init__(self, provider: Optional[KYCProviderInterface] = None):
        self.provider = provider or self._get_default_provider()

    def _get_default_provider(self) -> KYCProviderInterface:
        """Get the configured KYC provider"""

        provider_name = getattr(settings, "KYC_PROVIDER", "mock")

        if provider_name == "onfido":
            return OnfidoProvider()
        elif provider_name == "jumio":
            return JumioProvider()
        elif provider_name == "mock":
            return MockKYCProvider()
        else:
            logger.warning(f"Unknown KYC provider '{provider_name}', using Mock")
            return MockKYCProvider()

    def submit_kyc_for_verification(
        self, kyc: KYCVerification, documents: list[KYCDocument]
    ) -> bool:
        """Submit KYC to third-party provider for verification"""

        try:
            # Update KYC status
            kyc.status = KYCStatus.UNDER_REVIEW
            kyc.verification_method = "automated"
            kyc.provider_name = self.provider.provider_name

            # Submit to provider
            result = self.provider.submit_verification(kyc, documents)

            # Update KYC with provider response
            kyc.provider_reference_id = result["provider_reference_id"]
            kyc.provider_status = result["status"]

            # Assess initial risk level
            kyc_data = {
                "is_politically_exposed": kyc.is_politically_exposed,
                "date_of_birth": kyc.date_of_birth,
            }
            # You can implement more sophisticated risk assessment here

            kyc.save()

            logger.info(
                f"KYC {kyc.kyc_id} submitted to {self.provider.provider_name} "
                f"with reference {result['provider_reference_id']}"
            )
            return True

        except Exception as e:
            logger.error(f"KYC submission failed for {kyc.kyc_id}: {str(e)}")
            kyc.status = KYCStatus.PENDING
            kyc.notes = (
                f"Automated submission failed: {str(e)}. Requires manual review."
            )
            kyc.verification_method = "manual"
            kyc.save()
            return False

    def process_webhook_update(self, webhook_data: Dict[str, Any]) -> bool:
        """Process webhook update from KYC provider"""

        try:
            # Extract provider reference ID from webhook
            provider_reference_id = webhook_data.get("object", {}).get(
                "id"
            ) or webhook_data.get("check_id")

            if not provider_reference_id:
                logger.error("No reference ID in webhook data")
                return False

            # Find KYC verification
            kyc = KYCVerification.objects.filter(
                provider_reference_id=provider_reference_id
            ).first()

            if not kyc:
                logger.error(f"No KYC found for reference ID {provider_reference_id}")
                return False

            # Get latest status from provider
            status_data = self.provider.get_verification_status(provider_reference_id)

            old_status = kyc.status
            kyc.provider_status = status_data.get("status")
            kyc.status = self.provider.map_provider_status(kyc.provider_status)
            kyc.webhook_verified_at = timezone.now()

            # Update review timestamp for completed checks
            if kyc.status in [KYCStatus.APPROVED, KYCStatus.REJECTED]:
                kyc.reviewed_at = timezone.now()

                # Extract fraud score if available
                if "fraud_score" in status_data:
                    AMLCheck.objects.create(
                        user=kyc.user,
                        check_type="kyc_verification",
                        risk_score=status_data["fraud_score"] * 100,
                        risk_level=(
                            RiskLevel.HIGH
                            if status_data["fraud_score"] > 0.7
                            else RiskLevel.LOW
                        ),
                        passed=status_data.get("result") == "clear",
                        fraud_score=status_data["fraud_score"] * 100,
                        provider=kyc.provider_name,
                        provider_reference=provider_reference_id,
                        provider_response=status_data,
                    )

            kyc.save()

            logger.info(
                f"KYC {kyc.kyc_id} updated via webhook from {old_status} to {kyc.status}"
            )
            return True

        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return False

    def manual_review_required(self, kyc: KYCVerification, reason: str) -> None:
        """Mark KYC for manual review"""

        kyc.status = KYCStatus.UNDER_REVIEW
        kyc.verification_method = "manual"
        kyc.notes = f"Manual review required: {reason}"
        kyc.save()

        logger.info(f"KYC {kyc.kyc_id} marked for manual review: {reason}")

    def approve_kyc(self, kyc: KYCVerification, reviewer, notes: str = "") -> None:
        """Manually approve KYC"""

        kyc.status = KYCStatus.APPROVED
        kyc.reviewed_by = reviewer
        kyc.reviewed_at = timezone.now()
        kyc.notes = notes
        kyc.save()

        logger.info(f"KYC {kyc.kyc_id} manually approved by {reviewer.email}")

    def reject_kyc(self, kyc: KYCVerification, reviewer, rejection_reason: str) -> None:
        """Manually reject KYC"""

        kyc.status = KYCStatus.REJECTED
        kyc.reviewed_by = reviewer
        kyc.reviewed_at = timezone.now()
        kyc.rejection_reason = rejection_reason
        kyc.save()

        logger.info(
            f"KYC {kyc.kyc_id} rejected by {reviewer.email}: {rejection_reason}"
        )
