from decimal import Decimal
from typing import Optional, Dict, Any
from django.utils import timezone
from uuid import UUID

from apps.accounts.models import User
from apps.common.schemas import PaginationQuerySchema
from apps.transactions.models import (
    Transaction,
    TransactionStatus,
    TransactionDispute,
    DisputeType,
    DisputeStatus,
)
from apps.common.exceptions import RequestError, ErrorCode, NotFoundError
from django.db.models import Q
from apps.common.paginators import Paginator


class DisputeService:
    """Service for handling transaction disputes"""

    @staticmethod
    async def create_dispute(
        user: User,
        transaction_id: UUID,
        dispute_type: DisputeType,
        reason: str,
        disputed_amount: Optional[Decimal] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        transaction = await Transaction.objects.select_related(
            "from_user", "to_user"
        ).aget_or_none(transaction_id=transaction_id)
        if not transaction:
            raise NotFoundError("Transaction not found")

        # Verify user is part of the transaction
        if transaction.from_user_id != user.id and transaction.to_user_id != user.id:
            raise RequestError(
                ErrorCode.INVALID_OWNER,
                "You don't have permission to dispute this transaction",
                403,
            )

        # Check if transaction can be disputed
        if transaction.status != TransactionStatus.COMPLETED:
            raise RequestError(
                ErrorCode.NOT_ALLOWED,
                "Only completed transactions can be disputed",
                400,
            )

        # Check if already disputed
        existing_dispute = await TransactionDispute.objects.filter(
            transaction=transaction
        ).aexists()

        if existing_dispute:
            raise RequestError(
                ErrorCode.NOT_ALLOWED,
                "This transaction already has an active dispute",
                400,
            )

        # Check dispute window (30 days)
        days_since_completion = (timezone.now() - transaction.completed_at).days
        if days_since_completion > 30:
            raise RequestError(
                ErrorCode.NOT_ALLOWED,
                "Dispute window has expired (30 days after transaction)",
                400,
            )

        # Use transaction amount if not specified
        disputed_amount = (
            transaction.amount if disputed_amount is None else disputed_amount
        )

        # Validate disputed amount
        if disputed_amount > transaction.amount:
            raise RequestError(
                ErrorCode.INVALID_ENTRY,
                "Disputed amount cannot exceed transaction amount",
                400,
            )

        # Create dispute
        dispute = await TransactionDispute.objects.acreate(
            transaction=transaction,
            status=DisputeStatus.OPENED,
            dispute_type=dispute_type,
            reason=reason,
            disputed_amount=disputed_amount,
            initiated_by=user,
            evidence=evidence or {},
        )

        return dispute

    @staticmethod
    async def get_dispute_detail(user: User, dispute_id: UUID) -> Dict[str, Any]:
        dispute = await TransactionDispute.objects.select_related(
            "transaction", "initiated_by"
        ).aget_or_none(dispute_id=dispute_id)
        if not dispute:
            raise NotFoundError("Dispute not found")

        # Verify user has access
        if (
            dispute.transaction.from_user_id != user.id
            and dispute.transaction.to_user_id != user.id
            and dispute.initiated_by_id != user.id
        ):
            raise RequestError(
                ErrorCode.INVALID_OWNER,
                "You don't have access to this dispute",
                403,
            )
        return dispute

    @staticmethod
    async def list_user_disputes(
        user: User,
        status: Optional[DisputeStatus] = None,
        page_params: PaginationQuerySchema = None,
    ) -> Dict[str, Any]:

        filters = (
            Q(initiated_by=user)
            | Q(transaction__from_user=user)
            | Q(transaction__to_user=user)
        )

        if status:
            filters &= Q(status=status)

        disputes = (
            TransactionDispute.objects.filter(filters)
            .select_related("initiated_by")
            .order_by("-created_at")
        )
        paginated_data = await Paginator.paginate_queryset(
            disputes, page_params.page, page_params.limit
        )
        return paginated_data

    @staticmethod
    async def update_dispute_status(
        dispute_id: UUID,
        new_status: DisputeStatus,
        resolved_by: User,
        resolution_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update dispute status (admin function)"""

        try:
            dispute = await TransactionDispute.objects.select_related(
                "transaction", "initiated_by"
            ).aget(dispute_id=dispute_id)
        except TransactionDispute.DoesNotExist:
            raise NotFoundError("Dispute not found")

        dispute.status = new_status

        if new_status in [DisputeStatus.RESOLVED, DisputeStatus.CLOSED]:
            dispute.resolved_at = timezone.now()
            dispute.resolved_by = resolved_by
            dispute.resolution_notes = resolution_notes

        await dispute.asave()

        return {
            "dispute_id": dispute.dispute_id,
            "status": dispute.status,
            "resolved_at": dispute.resolved_at,
            "resolution_notes": dispute.resolution_notes,
        }

    @staticmethod
    async def add_evidence_to_dispute(
        user: User, dispute_id: UUID, evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        dispute = await TransactionDispute.objects.select_related(
            "transaction"
        ).aget_or_none(dispute_id=dispute_id)
        if not dispute:
            raise NotFoundError("Dispute not found")

        # Verify user is part of the dispute
        if (
            dispute.initiated_by_id != user.id
            and dispute.transaction.from_user_id != user.id
            and dispute.transaction.to_user_id != user.id
        ):
            raise RequestError(
                ErrorCode.INVALID_OWNER,
                "You don't have permission to add evidence to this dispute",
                403,
            )

        # Check if dispute is still open
        if dispute.status in [DisputeStatus.RESOLVED, DisputeStatus.CLOSED]:
            raise RequestError(
                ErrorCode.NOT_ALLOWED,
                "Cannot add evidence to a resolved or closed dispute",
                400,
            )

        # Add timestamp to evidence
        evidence["submitted_at"] = timezone.now().isoformat()
        evidence["submitted_by"] = user.email

        # Append to existing evidence
        if not dispute.evidence:
            dispute.evidence = {}

        if "submissions" not in dispute.evidence:
            dispute.evidence["submissions"] = []

        dispute.evidence["submissions"].append(evidence)

        await dispute.asave()

        return {
            "dispute_id": dispute.dispute_id,
            "evidence_count": len(dispute.evidence.get("submissions", [])),
        }
