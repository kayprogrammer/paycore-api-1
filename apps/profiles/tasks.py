import logging
from celery import shared_task
from typing import Dict, Any
from apps.profiles.models import KYC
from apps.profiles.services import KYCValidationService

logger = logging.getLogger(__name__)


class KYCTasks:
    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 3, "countdown": 60},
        name="profiles.process_kyc_verification",
        queue="kyc",
    )
    def process_kyc_verification(self, kyc_id: str):
        try:
            kyc = KYC.objects.get_or_none(id=kyc_id)
            if not kyc:
                logger.error(f"KYC {kyc_id} not found")
                return {"status": "failed", "error": "KYC record not found"}
    
            validation_service = KYCValidationService()
            
            document_files = {}
            if kyc.document_file:
                document_files["document_file"] = kyc.document_file
            if kyc.document_back_file:
                document_files["document_back_file"] = kyc.document_back_file
            if kyc.selfie_file:
                document_files["selfie_file"] = kyc.selfie_file
            
            # Submit for verification
            submission_success = validation_service.submit_kyc_for_verification(
                kyc, document_files
            )
            
            if not submission_success:
                logger.warning(f"KYC {kyc_id} submission failed, keeping as pending for manual review")
                return {
                    "status": "failed",
                    "kyc_id": kyc_id,
                    "message": "Automated submission failed, requires manual review"
                }
            
            logger.info(f"KYC {kyc_id} successfully submitted for verification")
            return {
                "status": "success", 
                "kyc_id": kyc_id,
                "provider_reference_id": kyc.provider_reference_id
            }
            
        except Exception as exc:
            logger.error(f"KYC verification task failed for {kyc_id}: {str(exc)}")
            raise self.retry(exc=exc)


class KYCWebhookTasks:
    @staticmethod
    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 5, "countdown": 30},
        name="profiles.process_kyc_webhook",
        queue="webhooks",
    )
    def process_kyc_webhook(self, webhook_data: Dict[str, Any]):
        try:
            validation_service = KYCValidationService()
            
            success = validation_service.process_webhook_update(webhook_data)
            
            if not success:
                logger.warning("Webhook processing failed, will retry")
                raise Exception("Webhook processing failed")
            
            logger.info("KYC webhook processed successfully")
            return {"status": "success", "webhook_processed": True}
            
        except Exception as exc:
            logger.error(f"KYC webhook processing failed: {str(exc)}")
            raise self.retry(exc=exc)

