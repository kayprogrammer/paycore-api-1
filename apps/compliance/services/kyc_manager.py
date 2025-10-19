from decimal import Decimal
from django.utils import timezone
from django.db.models import Q
from typing import Optional

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.exceptions import NotFoundError, RequestError, ErrorCode
from apps.compliance.models import (
    KYCVerification,
    KYCDocument,
    KYCStatus,
    KYCLevel,
)
from apps.compliance.schemas import CreateKYCSchema, UpdateKYCStatusSchema
from apps.common.schemas import PaginationQuerySchema
from apps.common.paginators import Paginator
from asgiref.sync import sync_to_async


class KYCManager:
    """Service for managing KYC verifications"""

    @staticmethod
    @aatomic
    async def submit_kyc(user: User, data: CreateKYCSchema) -> KYCVerification:
        existing_kyc = await KYCVerification.objects.filter(
            user=user,
            level=data.level,
            status__in=[KYCStatus.PENDING, KYCStatus.UNDER_REVIEW, KYCStatus.APPROVED],
        ).afirst()
        if existing_kyc:
            if existing_kyc.status == KYCStatus.APPROVED:
                raise RequestError(
                    ErrorCode.KYC_ALREADY_VERIFIED,
                    f"You already have an approved {data.level} verification",
                )
            else:
                raise RequestError(
                    ErrorCode.KYC_PENDING,
                    f"You already have a pending {data.level} verification",
                )

        # Create KYC verification
        kyc = await KYCVerification.objects.acreate(
            user=user,
            level=data.level,
            status=KYCStatus.PENDING,
            first_name=data.first_name,
            last_name=data.last_name,
            middle_name=data.middle_name or "",
            date_of_birth=data.date_of_birth,
            nationality=data.nationality,
            address_line_1=data.address_line_1,
            address_line_2=data.address_line_2 or "",
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            country=data.country,
            document_type=data.document_type,
            document_number=data.document_number,
            document_expiry_date=data.document_expiry_date,
            document_issuing_country=data.document_issuing_country,
            notes=data.notes or "",
        )

        return kyc

    @staticmethod
    async def get_kyc(user: User, kyc_id) -> KYCVerification:
        kyc = await KYCVerification.objects.select_related("user").aget_or_none(
            kyc_id=kyc_id, user=user
        )
        if not kyc:
            raise NotFoundError("KYC verification not found")
        return kyc

    @staticmethod
    async def list_user_kyc(
        user: User,
        status: Optional[str] = None,
        page_params: PaginationQuerySchema = None,
    ):
        queryset = KYCVerification.objects.filter(user=user).select_related("user")
        if status:
            queryset = queryset.filter(status=status)
        queryset = queryset.order_by("-created_at")
        return await Paginator.paginate_queryset(
            queryset, page_params.page, page_params.limit
        )

    @staticmethod
    async def get_user_current_kyc_level(user: User) -> Optional[str]:
        kyc = (
            await KYCVerification.objects.filter(user=user, status=KYCStatus.APPROVED)
            .order_by("-level")
            .afirst()
        )
        return kyc.level if kyc else None

    @staticmethod
    @aatomic
    async def update_kyc_status(
        admin_user: User, kyc_id, data: UpdateKYCStatusSchema
    ) -> KYCVerification:
        kyc = await KYCVerification.objects.select_related("user").aget_or_none(
            kyc_id=kyc_id
        )
        if not kyc:
            raise NotFoundError("KYC verification not found")
        if data.status == KYCStatus.REJECTED and not data.rejection_reason:
            raise RequestError(
                ErrorCode.VALIDATION_ERROR,
                "Rejection reason is required when rejecting KYC",
            )

        kyc.status = data.status
        kyc.reviewed_by = admin_user
        kyc.reviewed_at = timezone.now()

        if data.rejection_reason:
            kyc.rejection_reason = data.rejection_reason

        if data.expires_at:
            kyc.expires_at = data.expires_at

        await kyc.asave(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
                "expires_at",
                "updated_at",
            ]
        )
        return kyc

    @staticmethod
    async def list_all_kyc(
        status: Optional[str] = None,
        level: Optional[str] = None,
        page_params: PaginationQuerySchema = None,
    ):
        queryset = KYCVerification.objects.select_related("user")
        if status:
            queryset = queryset.filter(status=status)
        if level:
            queryset = queryset.filter(level=level)
        queryset = queryset.order_by("-created_at")
        return await Paginator.paginate_queryset(
            queryset, page_params.page, page_params.limit
        )

    @staticmethod
    async def check_kyc_requirement(user: User, required_level: str) -> bool:
        kyc_levels = {
            KYCLevel.TIER_1: 1,
            KYCLevel.TIER_2: 2,
            KYCLevel.TIER_3: 3,
        }
        user_level = await KYCManager.get_user_current_kyc_level(user)
        if not user_level:
            return False
        user_level_value = kyc_levels.get(user_level, 0)
        required_level_value = kyc_levels.get(required_level, 0)
        return user_level_value >= required_level_value

    @staticmethod
    @aatomic
    async def upload_kyc_document(
        user: User, kyc_id, document_type: str, file, file_name: str, file_size: int
    ) -> KYCDocument:
        kyc = await KYCVerification.objects.aget_or_none(kyc_id=kyc_id, user=user)
        if not kyc:
            raise NotFoundError("KYC verification not found")
        if kyc.status not in [KYCStatus.PENDING, KYCStatus.UNDER_REVIEW]:
            raise RequestError(
                ErrorCode.KYC_INVALID_STATUS,
                "Cannot upload documents to KYC verification with status: "
                + kyc.status,
            )
        document = await KYCDocument.objects.acreate(
            kyc_verification=kyc,
            document_type=document_type,
            file=file,
            file_name=file_name,
            file_size=file_size,
        )
        return document

    @staticmethod
    async def get_kyc_documents(user: User, kyc_id):
        kyc = await KYCVerification.objects.aget_or_none(kyc_id=kyc_id, user=user)
        if not kyc:
            raise NotFoundError("KYC verification not found")
        documents = await sync_to_async(list)(
            KYCDocument.objects.filter(kyc_verification=kyc).order_by("-created_at")
        )
        return documents

    @staticmethod
    @aatomic
    async def verify_kyc_document(admin_user: User, document_id) -> KYCDocument:
        document = await KYCDocument.objects.select_related(
            "kyc_verification"
        ).aget_or_none(document_id=document_id)

        if not document:
            raise NotFoundError("KYC document not found")

        document.is_verified = True
        document.verified_at = timezone.now()
        await document.asave(update_fields=["is_verified", "verified_at", "updated_at"])
        return document
