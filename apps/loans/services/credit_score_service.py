from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, DecimalField

from apps.accounts.models import User
from apps.loans.models import (
    CreditScore,
    LoanApplication,
    LoanRepayment,
    LoanRepaymentSchedule,
    LoanStatus,
    RepaymentStatus,
)


class CreditScoreService:
    """Service for calculating and managing user credit scores"""

    # Score weights
    PAYMENT_HISTORY_WEIGHT = 0.35  # 35%
    CREDIT_UTILIZATION_WEIGHT = 0.30  # 30%
    ACCOUNT_AGE_WEIGHT = 0.15  # 15%
    LOAN_HISTORY_WEIGHT = 0.20  # 20%

    @staticmethod
    async def calculate_credit_score(user: User) -> CreditScore:
        """
        Score range: 300-850 (following FICO model)
        """
        loans_queryset = LoanApplication.objects.filter(user=user).select_related(
            "wallet__currency"
        )

        total_loans = await loans_queryset.acount()
        active_loans = await loans_queryset.filter(status=LoanStatus.ACTIVE).acount()
        completed_loans = await loans_queryset.filter(status=LoanStatus.PAID).acount()
        defaulted_loans = await loans_queryset.filter(
            status=LoanStatus.DEFAULTED
        ).acount()

        payment_stats = await CreditScoreService._calculate_payment_history(user)
        on_time_payments = payment_stats["on_time"]
        late_payments = payment_stats["late"]
        missed_payments = payment_stats["missed"]

        financial_stats = await CreditScoreService._calculate_financial_metrics(user)
        total_borrowed = financial_stats["total_borrowed"]
        total_repaid = financial_stats["total_repaid"]
        current_debt = financial_stats["current_debt"]

        account_age_days = (timezone.now().date() - user.created_at.date()).days

        # Calculate component scores (each out of 850)
        payment_history_score = (
            await CreditScoreService._calculate_payment_history_score(
                on_time_payments, late_payments, missed_payments, total_loans
            )
        )

        credit_utilization_score = (
            await CreditScoreService._calculate_credit_utilization_score(
                active_loans, defaulted_loans, current_debt, total_borrowed
            )
        )

        account_age_score = await CreditScoreService._calculate_account_age_score(
            account_age_days
        )

        loan_history_score = await CreditScoreService._calculate_loan_history_score(
            total_loans, completed_loans, defaulted_loans
        )

        # Calculate weighted total score
        score = int(
            (payment_history_score * CreditScoreService.PAYMENT_HISTORY_WEIGHT)
            + (credit_utilization_score * CreditScoreService.CREDIT_UTILIZATION_WEIGHT)
            + (account_age_score * CreditScoreService.ACCOUNT_AGE_WEIGHT)
            + (loan_history_score * CreditScoreService.LOAN_HISTORY_WEIGHT)
        )

        # Ensure score is within valid range
        score = max(300, min(850, score))
        score_band = CreditScore.get_score_band(score)

        risk_level = CreditScoreService._determine_risk_level(
            score, defaulted_loans, active_loans
        )

        recommendations = CreditScoreService._generate_recommendations(
            score,
            on_time_payments,
            late_payments,
            missed_payments,
            active_loans,
            defaulted_loans,
            account_age_days,
        )

        # Create detailed factors
        factors = {
            "payment_history": {
                "score": payment_history_score,
                "weight": f"{int(CreditScoreService.PAYMENT_HISTORY_WEIGHT * 100)}%",
                "on_time_payments": on_time_payments,
                "late_payments": late_payments,
                "missed_payments": missed_payments,
            },
            "credit_utilization": {
                "score": credit_utilization_score,
                "weight": f"{int(CreditScoreService.CREDIT_UTILIZATION_WEIGHT * 100)}%",
                "active_loans": active_loans,
                "defaulted_loans": defaulted_loans,
            },
            "account_age": {
                "score": account_age_score,
                "weight": f"{int(CreditScoreService.ACCOUNT_AGE_WEIGHT * 100)}%",
                "days": account_age_days,
            },
            "loan_history": {
                "score": loan_history_score,
                "weight": f"{int(CreditScoreService.LOAN_HISTORY_WEIGHT * 100)}%",
                "total_loans": total_loans,
                "completed_loans": completed_loans,
            },
        }

        credit_score = await CreditScore.objects.acreate(
            user=user,
            score=score,
            score_band=score_band,
            payment_history_score=payment_history_score,
            credit_utilization_score=credit_utilization_score,
            account_age_score=account_age_score,
            loan_history_score=loan_history_score,
            total_loans=total_loans,
            active_loans=active_loans,
            completed_loans=completed_loans,
            defaulted_loans=defaulted_loans,
            on_time_payments=on_time_payments,
            late_payments=late_payments,
            missed_payments=missed_payments,
            total_borrowed=total_borrowed,
            total_repaid=total_repaid,
            current_debt=current_debt,
            risk_level=risk_level,
            account_age_days=account_age_days,
            factors=factors,
            recommendations=recommendations,
        )

        return credit_score

    @staticmethod
    async def _calculate_payment_history(user: User) -> dict:
        schedules_q = LoanRepaymentSchedule.objects.filter(loan__user=user)

        on_time = await schedules_q.filter(status=RepaymentStatus.PAID).acount()
        overdue = await schedules_q.filter(status=RepaymentStatus.OVERDUE).acount()
        missed = await schedules_q.filter(status=RepaymentStatus.MISSED).acount()
        late = (
            overdue + await schedules_q.filter(status=RepaymentStatus.PARTIAL).acount()
        )

        return {
            "on_time": on_time,
            "late": late,
            "missed": missed,
        }

    @staticmethod
    async def _calculate_financial_metrics(user: User) -> dict:
        # Total borrowed (sum of all disbursed loans)
        loans_data = await LoanApplication.objects.filter(
            user=user,
            status__in=[
                LoanStatus.DISBURSED,
                LoanStatus.ACTIVE,
                LoanStatus.OVERDUE,
                LoanStatus.PAID,
            ],
        ).aaggregate(
            total_borrowed=Sum("approved_amount"),
        )

        total_borrowed = loans_data["total_borrowed"] or Decimal("0")

        # Total repaid
        repayments_data = await LoanRepayment.objects.filter(
            loan__user=user
        ).aaggregate(total_repaid=Sum("amount"))

        total_repaid = repayments_data["total_repaid"] or Decimal("0")

        # Current debt (sum of outstanding amounts from active loans)
        current_debt = await LoanApplication.objects.filter(
            user=user,
            status__in=[LoanStatus.ACTIVE, LoanStatus.OVERDUE],
            repayment_schedules__status__in=[
                RepaymentStatus.PENDING,
                RepaymentStatus.OVERDUE,
                RepaymentStatus.PARTIAL,
            ],
        ).aaggregate(
            total_debt=Sum(
                "repayment_schedules__outstanding_amount", output_field=DecimalField()
            )
        )

        current_debt = current_debt["total_debt"] or Decimal("0")

        return {
            "total_borrowed": total_borrowed,
            "total_repaid": total_repaid,
            "current_debt": current_debt,
        }

    @staticmethod
    async def _calculate_payment_history_score(
        on_time: int, late: int, missed: int, total_loans: int
    ) -> int:
        """
        Calculate payment history score (0-850)
        Payment history is the most important factor
        """
        if total_loans == 0:
            # New users start at 650 (fair)
            return 650

        total_payments = on_time + late + missed

        if total_payments == 0:
            return 650

        on_time_ratio = on_time / total_payments if total_payments > 0 else 0

        # Calculate penalties
        late_penalty = late * 50  # Each late payment reduces score by 50
        missed_penalty = missed * 100  # Each missed payment reduces score by 100

        # Base score with on-time ratio
        base_score = 300 + int(on_time_ratio * 550)  # Range: 300-850

        # Apply penalties
        score = base_score - late_penalty - missed_penalty
        return max(300, min(850, score))

    @staticmethod
    async def _calculate_credit_utilization_score(
        active_loans: int,
        defaulted_loans: int,
        current_debt: Decimal,
        total_borrowed: Decimal,
    ) -> int:
        """
        Calculate credit utilization score (0-850)
        Lower active loans and no defaults = better score
        """
        base_score = 650

        # Penalty for too many active loans
        if active_loans > 3:
            base_score -= (active_loans - 3) * 50

        # Heavy penalty for defaults
        base_score -= defaulted_loans * 150

        # Utilization ratio (current debt vs total borrowing capacity)
        if total_borrowed > 0:
            utilization_ratio = float(current_debt / total_borrowed)
            # Lower utilization is better
            if utilization_ratio < 0.3:
                base_score += 100
            elif utilization_ratio > 0.7:
                base_score -= 100

        return max(300, min(850, base_score))

    @staticmethod
    async def _calculate_account_age_score(account_age_days: int) -> int:
        """
        Calculate account age score (0-850)
        Older accounts = better score
        """
        # Score increases with account age
        if account_age_days < 30:
            return 300  # Very new account
        elif account_age_days < 90:
            return 450  # New account (1-3 months)
        elif account_age_days < 180:
            return 550  # Established (3-6 months)
        elif account_age_days < 365:
            return 650  # Good age (6-12 months)
        elif account_age_days < 730:
            return 750  # Great age (1-2 years)
        else:
            return 850  # Excellent age (2+ years)

    @staticmethod
    async def _calculate_loan_history_score(
        total_loans: int, completed_loans: int, defaulted_loans: int
    ) -> int:
        """
        Calculate loan history score (0-850)
        More completed loans = better score
        """
        if total_loans == 0:
            return 650  # Neutral for new users

        completion_ratio = completed_loans / total_loans if total_loans > 0 else 0
        base_score = 300 + int(completion_ratio * 550)

        # Bonus for having loan history
        if total_loans >= 1:
            base_score += 50
        if total_loans >= 3:
            base_score += 50

        # Penalty for defaults
        base_score -= defaulted_loans * 200
        return max(300, min(850, base_score))

    @staticmethod
    def _determine_risk_level(
        score: int, defaulted_loans: int, active_loans: int
    ) -> str:
        """Determine risk level based on score and other factors"""
        if defaulted_loans > 0:
            return "very_high"

        if score >= 750:
            return "low"
        elif score >= 700:
            return "low" if active_loans <= 2 else "medium"
        elif score >= 650:
            return "medium"
        elif score >= 600:
            return "high"
        else:
            return "very_high"

    @staticmethod
    def _generate_recommendations(
        score: int,
        on_time: int,
        late: int,
        missed: int,
        active_loans: int,
        defaulted_loans: int,
        account_age_days: int,
    ) -> list:
        """Generate personalized recommendations to improve credit score"""
        recommendations = []
        if score < 650:
            recommendations.append(
                "Your credit score is below average. Focus on making timely payments."
            )
        if late > 0 or missed > 0:
            recommendations.append(
                "Make all future loan payments on time to improve your payment history."
            )
        if missed > 0:
            recommendations.append(
                "Missed payments significantly impact your score. Set up payment reminders."
            )
        if active_loans > 2:
            recommendations.append(
                "Consider reducing the number of active loans for better credit utilization."
            )
        if defaulted_loans > 0:
            recommendations.append(
                "Defaulted loans severely impact your score. Resolve outstanding defaults if possible."
            )
        if account_age_days < 90:
            recommendations.append(
                "Continue using your account responsibly. Account age improves over time."
            )
        if on_time > 0 and late == 0 and missed == 0:
            recommendations.append(
                "Excellent payment history! Keep making payments on time."
            )
        if score >= 750:
            recommendations.append(
                "Great credit score! You qualify for our best loan products and interest rates."
            )
        if not recommendations:
            recommendations.append(
                "Maintain your current payment behavior to preserve your credit score."
            )
        return recommendations

    @staticmethod
    async def get_latest_credit_score(user: User) -> CreditScore:
        credit_score = (
            await CreditScore.objects.filter(user=user).order_by("-created_at").afirst()
        )
        if not credit_score:
            credit_score = await CreditScoreService.calculate_credit_score(user)
        return credit_score

    @staticmethod
    async def check_eligibility(user: User, min_score: int) -> tuple[bool, str]:
        credit_score = await CreditScoreService.get_latest_credit_score(user)
        if credit_score.score >= min_score:
            return True, ""
        return (
            False,
            f"Your credit score ({credit_score.score}) is below the minimum requirement ({min_score})",
        )
