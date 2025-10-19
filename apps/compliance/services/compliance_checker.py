from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Count
from typing import Optional, Dict
from uuid import UUID

from apps.accounts.models import User
from apps.common.decorators import aatomic
from apps.common.exceptions import NotFoundError, RequestError, ErrorCode
from apps.compliance.models import (
    AMLCheck,
    SanctionsScreening,
    TransactionMonitoring,
    ComplianceReport,
    RiskLevel,
)
from apps.compliance.schemas import (
    CreateAMLCheckSchema,
    UpdateAMLReviewSchema,
    CreateSanctionsScreeningSchema,
    UpdateSanctionsReviewSchema,
    ResolveMonitoringAlertSchema,
    CreateComplianceReportSchema,
)
from apps.common.schemas import PaginationQuerySchema
from apps.common.paginators import Paginator
from apps.transactions.models import Transaction
from apps.compliance.models import KYCVerification, KYCStatus


class ComplianceChecker:
    """Service for AML, sanctions, and transaction monitoring"""

    # ==================== AML CHECKS ====================

    @staticmethod
    @aatomic
    async def create_aml_check(data: CreateAMLCheckSchema) -> AMLCheck:
        user = await User.objects.aget_or_none(id=data.user_id)
        if not user:
            raise NotFoundError("User not found")

        # Simulate AML check (in production, integrate with external provider)
        risk_score = await ComplianceChecker._calculate_aml_risk_score(
            user, data.transaction_id
        )
        risk_level = await ComplianceChecker._determine_risk_level(risk_score)
        flagged_items = []

        # Check for high-risk indicators
        if risk_score > 70:
            flagged_items.append("High transaction volume")

        if risk_score > 85:
            flagged_items.append("Unusual transaction pattern")

        passed = risk_score < 50
        requires_manual_review = risk_score >= 70

        aml_check = await AMLCheck.objects.acreate(
            user=user,
            transaction_id=data.transaction_id,
            check_type=data.check_type,
            risk_score=risk_score,
            risk_level=risk_level,
            passed=passed,
            flagged_items=flagged_items,
            provider=data.provider or "Internal",
            requires_manual_review=requires_manual_review,
        )

        return aml_check

    @staticmethod
    async def _calculate_aml_risk_score(
        user: User, transaction_id: Optional[UUID] = None
    ) -> Decimal:
        """Calculate AML risk score (simplified for demo)"""

        # In production, this would integrate with external AML service
        # For now, return a simulated score based on user activity

        # Count user transactions
        transaction_count = await Transaction.objects.filter(user=user).acount()
        base_score = Decimal("20")

        # Increase score if very new user
        if transaction_count < 5:
            base_score += Decimal("15")

        if transaction_count > 100:
            base_score += Decimal("20")

        # Increase score if specific transaction is flagged
        if transaction_id:
            transaction = await Transaction.objects.aget_or_none(id=transaction_id)
            if transaction and transaction.amount > Decimal("10000"):
                base_score += Decimal("30")

        # Cap at 100
        return min(base_score, Decimal("100"))

    @staticmethod
    async def _determine_risk_level(risk_score: Decimal) -> str:
        if risk_score < 30:
            return RiskLevel.LOW
        elif risk_score < 60:
            return RiskLevel.MEDIUM
        elif risk_score < 85:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    @staticmethod
    async def get_aml_check(check_id) -> AMLCheck:
        aml_check = await AMLCheck.objects.select_related("user").aget_or_none(
            check_id=check_id
        )

        if not aml_check:
            raise NotFoundError("AML check not found")
        return aml_check

    @staticmethod
    async def list_aml_checks(
        user: Optional[User] = None,
        risk_level: Optional[str] = None,
        requires_review: Optional[bool] = None,
        page_params: PaginationQuerySchema = None,
    ):
        queryset = AMLCheck.objects.select_related("user")
        if user:
            queryset = queryset.filter(user=user)
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        if requires_review is not None:
            queryset = queryset.filter(requires_manual_review=requires_review)

        queryset = queryset.order_by("-created_at")
        return await Paginator.paginate_queryset(
            queryset, page_params.page, page_params.limit
        )

    @staticmethod
    @aatomic
    async def update_aml_review(
        admin_user: User, check_id, data: UpdateAMLReviewSchema
    ) -> AMLCheck:
        aml_check = await AMLCheck.objects.select_related("user").aget_or_none(
            check_id=check_id
        )

        if not aml_check:
            raise NotFoundError("AML check not found")

        aml_check.reviewed_by = admin_user
        aml_check.reviewed_at = timezone.now()
        aml_check.review_notes = data.review_notes

        await aml_check.asave(
            update_fields=["reviewed_by", "reviewed_at", "review_notes", "updated_at"]
        )
        return aml_check

    # ==================== SANCTIONS SCREENING ====================

    @staticmethod
    @aatomic
    async def create_sanctions_screening(
        data: CreateSanctionsScreeningSchema,
    ) -> SanctionsScreening:
        user = await User.objects.aget_or_none(id=data.user_id)
        if not user:
            raise NotFoundError("User not found")

        # Simulate sanctions screening (in production, integrate with external provider)
        is_match, match_score, matched_lists, match_details = (
            await ComplianceChecker._check_sanctions_lists(
                data.full_name, data.date_of_birth, data.nationality
            )
        )

        screening = await SanctionsScreening.objects.acreate(
            user=user,
            full_name=data.full_name,
            date_of_birth=data.date_of_birth,
            nationality=data.nationality or "",
            is_match=is_match,
            match_score=match_score,
            matched_lists=matched_lists,
            match_details=match_details,
            provider=data.provider or "Internal",
        )
        return screening

    @staticmethod
    async def _check_sanctions_lists(
        full_name: str, date_of_birth, nationality: Optional[str]
    ) -> tuple:
        # In production, integrate with OFAC, UN, EU sanctions lists
        # For now, simulate a check

        is_match = False
        match_score = None
        matched_lists = []
        match_details = {}

        # Simulate: check if name contains certain keywords
        suspicious_keywords = ["test", "sanction", "blocked"]
        name_lower = full_name.lower()

        for keyword in suspicious_keywords:
            if keyword in name_lower:
                is_match = True
                match_score = Decimal("85.5")
                matched_lists = ["OFAC SDN List", "UN Sanctions List"]
                match_details = {
                    "matched_name": full_name,
                    "match_reason": f"Name contains suspicious keyword: {keyword}",
                }
                break
        return is_match, match_score, matched_lists, match_details

    @staticmethod
    async def get_sanctions_screening(screening_id) -> SanctionsScreening:
        screening = await SanctionsScreening.objects.select_related(
            "user"
        ).aget_or_none(screening_id=screening_id)
        if not screening:
            raise NotFoundError("Sanctions screening not found")
        return screening

    @staticmethod
    async def list_sanctions_screenings(
        user: Optional[User] = None,
        is_match: Optional[bool] = None,
        page_params: PaginationQuerySchema = None,
    ):
        queryset = SanctionsScreening.objects.select_related("user")
        if user:
            queryset = queryset.filter(user=user)
        if is_match is not None:
            queryset = queryset.filter(is_match=is_match)
        queryset = queryset.order_by("-created_at")

        return await Paginator.paginate_queryset(
            queryset, page_params.page, page_params.limit
        )

    @staticmethod
    @aatomic
    async def update_sanctions_review(
        admin_user: User, screening_id, data: UpdateSanctionsReviewSchema
    ) -> SanctionsScreening:
        screening = await SanctionsScreening.objects.select_related(
            "user"
        ).aget_or_none(screening_id=screening_id)

        if not screening:
            raise NotFoundError("Sanctions screening not found")

        screening.reviewed_by = admin_user
        screening.reviewed_at = timezone.now()
        screening.false_positive = data.false_positive
        screening.review_notes = data.review_notes

        await screening.asave(
            update_fields=[
                "reviewed_by",
                "reviewed_at",
                "false_positive",
                "review_notes",
                "updated_at",
            ]
        )
        return screening

    # ==================== TRANSACTION MONITORING ====================

    @staticmethod
    @aatomic
    async def create_monitoring_alert(
        user: User,
        transaction_id: UUID,
        alert_type: str,
        description: str,
        triggered_rules: list,
        transaction_amount: Decimal,
        transaction_type: str,
    ) -> TransactionMonitoring:
        # Calculate risk score based on rules
        risk_score = Decimal(len(triggered_rules) * 25)  # Simplified calculation
        risk_level = await ComplianceChecker._determine_risk_level(risk_score)

        alert = await TransactionMonitoring.objects.acreate(
            user=user,
            transaction_id=transaction_id,
            alert_type=alert_type,
            risk_score=risk_score,
            risk_level=risk_level,
            description=description,
            triggered_rules=triggered_rules,
            transaction_amount=transaction_amount,
            transaction_type=transaction_type,
            transaction_date=timezone.now(),
        )

        return alert

    @staticmethod
    async def get_monitoring_alert(monitoring_id) -> TransactionMonitoring:
        alert = await TransactionMonitoring.objects.select_related("user").aget_or_none(
            monitoring_id=monitoring_id
        )
        if not alert:
            raise NotFoundError("Transaction monitoring alert not found")
        return alert

    @staticmethod
    async def list_monitoring_alerts(
        user: Optional[User] = None,
        risk_level: Optional[str] = None,
        is_resolved: Optional[bool] = None,
        page_params: PaginationQuerySchema = None,
    ):
        queryset = TransactionMonitoring.objects.select_related("user")

        if user:
            queryset = queryset.filter(user=user)

        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)

        if is_resolved is not None:
            queryset = queryset.filter(is_resolved=is_resolved)

        queryset = queryset.order_by("-created_at")
        return await Paginator.paginate_queryset(
            queryset, page_params.page, page_params.limit
        )

    @staticmethod
    @aatomic
    async def resolve_monitoring_alert(
        admin_user: User, monitoring_id, data: ResolveMonitoringAlertSchema
    ) -> TransactionMonitoring:
        alert = await TransactionMonitoring.objects.select_related("user").aget_or_none(
            monitoring_id=monitoring_id
        )

        if not alert:
            raise NotFoundError("Transaction monitoring alert not found")

        alert.is_resolved = True
        alert.resolution = data.resolution
        alert.resolved_by = admin_user
        alert.resolved_at = timezone.now()

        if data.is_reported:
            alert.is_reported = True
            alert.reported_at = timezone.now()

        await alert.asave(
            update_fields=[
                "is_resolved",
                "resolution",
                "resolved_by",
                "resolved_at",
                "is_reported",
                "reported_at",
                "updated_at",
            ]
        )

        return alert

    # ==================== COMPLIANCE REPORTS ====================

    @staticmethod
    @aatomic
    async def generate_compliance_report(
        admin_user: User, data: CreateComplianceReportSchema
    ) -> ComplianceReport:
        transactions = Transaction.objects.filter(
            created_at__date__gte=data.report_period_start,
            created_at__date__lte=data.report_period_end,
        )
        total_transactions = await transactions.acount()

        flagged_transactions = await TransactionMonitoring.objects.filter(
            transaction_date__date__gte=data.report_period_start,
            transaction_date__date__lte=data.report_period_end,
        ).acount()

        total_users_screened = await KYCVerification.objects.filter(
            created_at__date__gte=data.report_period_start,
            created_at__date__lte=data.report_period_end,
        ).acount()

        # Count high-risk users
        high_risk_users = (
            await AMLCheck.objects.filter(
                created_at__date__gte=data.report_period_start,
                created_at__date__lte=data.report_period_end,
                risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL],
            )
            .values("user")
            .distinct()
            .acount()
        )

        summary = f"""
            Compliance Report: {data.report_type}
            Period: {data.report_period_start} to {data.report_period_end}

            Total Transactions: {total_transactions}
            Flagged Transactions: {flagged_transactions} ({(flagged_transactions/total_transactions*100) if total_transactions > 0 else 0:.2f}%)

            Total Users Screened: {total_users_screened}
            High-Risk Users Identified: {high_risk_users}
        """.strip()

        # Create report
        report = await ComplianceReport.objects.acreate(
            report_type=data.report_type,
            report_period_start=data.report_period_start,
            report_period_end=data.report_period_end,
            summary=summary,
            total_transactions=total_transactions,
            flagged_transactions=flagged_transactions,
            total_users_screened=total_users_screened,
            high_risk_users=high_risk_users,
            generated_by=admin_user,
            data={
                "aml_checks": await AMLCheck.objects.filter(
                    created_at__date__gte=data.report_period_start,
                    created_at__date__lte=data.report_period_end,
                ).acount(),
                "sanctions_screenings": await SanctionsScreening.objects.filter(
                    created_at__date__gte=data.report_period_start,
                    created_at__date__lte=data.report_period_end,
                ).acount(),
            },
        )

        return report

    @staticmethod
    async def get_compliance_report(report_id) -> ComplianceReport:
        report = await ComplianceReport.objects.aget_or_none(report_id=report_id)

        if not report:
            raise NotFoundError("Compliance report not found")

        return report

    @staticmethod
    async def list_compliance_reports(
        report_type: Optional[str] = None, page_params: PaginationQuerySchema = None
    ):
        queryset = ComplianceReport.objects.all()

        if report_type:
            queryset = queryset.filter(report_type=report_type)

        queryset = queryset.order_by("-created_at")
        return await Paginator.paginate_queryset(
            queryset, page_params.page, page_params.limit
        )

    @staticmethod
    async def get_compliance_statistics() -> Dict:

        # KYC stats
        total_kyc = await KYCVerification.objects.acount()
        pending_kyc = await KYCVerification.objects.filter(
            status=KYCStatus.PENDING
        ).acount()
        approved_kyc = await KYCVerification.objects.filter(
            status=KYCStatus.APPROVED
        ).acount()
        rejected_kyc = await KYCVerification.objects.filter(
            status=KYCStatus.REJECTED
        ).acount()
        expired_kyc = await KYCVerification.objects.filter(
            status=KYCStatus.EXPIRED
        ).acount()

        # AML stats
        total_aml = await AMLCheck.objects.acount()
        high_risk_aml = await AMLCheck.objects.filter(
            risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL]
        ).acount()
        aml_requiring_review = await AMLCheck.objects.filter(
            requires_manual_review=True, reviewed_at__isnull=True
        ).acount()

        # Sanctions stats
        total_sanctions = await SanctionsScreening.objects.acount()
        sanctions_matches = await SanctionsScreening.objects.filter(
            is_match=True
        ).acount()
        false_positives = await SanctionsScreening.objects.filter(
            false_positive=True
        ).acount()

        # Transaction monitoring stats
        total_alerts = await TransactionMonitoring.objects.acount()
        unresolved_alerts = await TransactionMonitoring.objects.filter(
            is_resolved=False
        ).acount()
        high_risk_alerts = await TransactionMonitoring.objects.filter(
            risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL]
        ).acount()
        reported_alerts = await TransactionMonitoring.objects.filter(
            is_reported=True
        ).acount()

        return {
            "total_kyc_verifications": total_kyc,
            "pending_kyc_verifications": pending_kyc,
            "approved_kyc_verifications": approved_kyc,
            "rejected_kyc_verifications": rejected_kyc,
            "expired_kyc_verifications": expired_kyc,
            "total_aml_checks": total_aml,
            "high_risk_aml_checks": high_risk_aml,
            "aml_checks_requiring_review": aml_requiring_review,
            "total_sanctions_screenings": total_sanctions,
            "sanctions_matches": sanctions_matches,
            "false_positives": false_positives,
            "total_alerts": total_alerts,
            "unresolved_alerts": unresolved_alerts,
            "high_risk_alerts": high_risk_alerts,
            "reported_alerts": reported_alerts,
        }
