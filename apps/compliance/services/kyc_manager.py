from django.utils import timezone
from typing import Optional

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.exceptions import (
    BodyValidationError,
    NotFoundError,
    RequestError,
    ErrorCode,
)
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
from apps.profiles.models import Country
from apps.wallets.services.wallet_manager import WalletManager
from apps.wallets.schemas import CreateWalletSchema
from apps.notifications.services.dispatcher import (
    UnifiedNotificationDispatcher,
    NotificationChannel,
    NotificationEventType,
)
from apps.notifications.models import NotificationPriority


class KYCManager:
    """Service for managing KYC verifications"""

    @staticmethod
    @aatomic
    async def submit_kyc(
        user: User, data: CreateKYCSchema, id_document, selfie, proof_of_address=None
    ) -> KYCVerification:
        # Validate country
        country = await Country.objects.aget_or_none(id=data.country_id)
        if not country:
            raise BodyValidationError("country_id", "Country not found")

        document_issuing_country = await Country.objects.aget_or_none(
            id=data.document_issuing_country_id
        )
        if not document_issuing_country:
            raise BodyValidationError(
                "document_issuing_country_id", "Document issuing country not found"
            )

        existing_kyc = await KYCVerification.objects.filter(
            user=user,
            level=data.level,
            status=[KYCStatus.PENDING, KYCStatus.UNDER_REVIEW, KYCStatus.APPROVED],
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

        data_to_create = data.model_dump(
            exclude_unset=True, exclude=["country_id", "document_issuing_country_id"]
        )
        # Create KYC verification
        kyc = await KYCVerification.objects.acreate(
            user=user,
            country=country,
            document_issuing_country=document_issuing_country,
            selfie_image=selfie,
            **data_to_create,
        )

        # Create KYC documents in bulk
        documents_to_create = [
            # 1. ID Document
            KYCDocument(
                kyc_verification=kyc,
                document_type=data.document_type,
                file=id_document,
                file_name=id_document.name,
                file_size=id_document.size,
            ),
        ]

        # 2. Proof of Address (optional)
        if proof_of_address:
            documents_to_create.append(
                KYCDocument(
                    kyc_verification=kyc,
                    document_type="utility_bill",  # Default to utility bill for proof of address
                    file=proof_of_address,
                    file_name=proof_of_address.name,
                    file_size=proof_of_address.size,
                )
            )

        await KYCDocument.objects.abulk_create(documents_to_create)

        user.first_name = kyc.first_name
        user.last_name = kyc.last_name
        user.dob = kyc.date_of_birth
        await user.asave()

        kyc = (
            await KYCVerification.objects.select_related("user")
            .prefetch_related("documents")
            .aget(kyc_id=kyc.kyc_id)
        )
        return kyc

    @staticmethod
    async def get_kyc(user: User, kyc_id) -> KYCVerification:
        kyc = (
            await KYCVerification.objects.select_related("user")
            .prefetch_related("documents")
            .aget_or_none(kyc_id=kyc_id, user=user)
        )
        if not kyc:
            raise NotFoundError("KYC verification not found")
        return kyc

    @staticmethod
    async def list_user_kyc(
        user: User,
        status: Optional[str] = None,
    ):
        queryset = KYCVerification.objects.filter(user=user).select_related("user")
        if status:
            queryset = queryset.filter(status__icontains=status)
        kycs = await sync_to_async(list)(queryset.order_by("-created_at"))
        return kycs

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
        kyc = (
            await KYCVerification.objects.select_related("user")
            .prefetch_related("documents")
            .aget_or_none(kyc_id=kyc_id)
        )
        if not kyc:
            raise NotFoundError("KYC verification not found")
        if data.status == KYCStatus.REJECTED and not data.rejection_reason:
            raise BodyValidationError(
                "rejection_reason", "Rejection reason is required when rejecting KYC"
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

        # Automatically create NGN wallet when KYC is approved
        if data.status == KYCStatus.APPROVED:
            # Check if user already has an NGN wallet
            existing_ngn_wallets = await WalletManager.get_user_wallets(
                user=kyc.user, currency_code="NGN"
            )

            if not existing_ngn_wallets:
                # Create NGN wallet for the user
                wallet_data = CreateWalletSchema(
                    currency_code="NGN",
                    name="NGN Wallet",
                    wallet_type="main",
                    is_default=True,
                    description="Auto-created upon KYC approval for fiat transactions",
                )
                await WalletManager.create_wallet(user=kyc.user, data=wallet_data)

        # Send KYC status notification (in-app, push, email)
        notification_map = {
            KYCStatus.APPROVED: {
                "event_type": NotificationEventType.KYC_APPROVED,
                "title": "KYC Verification Approved!",
                "message": f"Your {kyc.level} KYC verification has been approved",
                "priority": NotificationPriority.HIGH,
            },
            KYCStatus.REJECTED: {
                "event_type": NotificationEventType.KYC_REJECTED,
                "title": "KYC Verification Rejected",
                "message": f"Your {kyc.level} KYC verification was rejected. Reason: {kyc.rejection_reason}",
                "priority": NotificationPriority.HIGH,
            },
            KYCStatus.PENDING: {
                "event_type": NotificationEventType.KYC_PENDING,
                "title": "KYC Under Review",
                "message": f"Your {kyc.level} KYC verification is under review",
                "priority": NotificationPriority.MEDIUM,
            },
        }

        if data.status in notification_map:
            notif_data = notification_map[data.status]
            await sync_to_async(UnifiedNotificationDispatcher.dispatch)(
                user=kyc.user,
                event_type=notif_data["event_type"],
                channels=[
                    NotificationChannel.IN_APP,
                    NotificationChannel.PUSH,
                    NotificationChannel.EMAIL,
                ],
                title=notif_data["title"],
                message=notif_data["message"],
                context_data={"kyc_id": str(kyc.kyc_id)},
                priority=notif_data["priority"],
                related_object_type="KYCVerification",
                related_object_id=str(kyc.kyc_id),
                action_url="/settings/kyc",
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
        return await Paginator.paginate_queryset(
            queryset.order_by("-created_at"), page_params.page, page_params.limit
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
