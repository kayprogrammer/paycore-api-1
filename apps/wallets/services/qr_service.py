from decimal import Decimal
from uuid import UUID
from django.utils import timezone
from typing import List, Dict, Any

from apps.accounts.models import User
from apps.wallets.models import Wallet, QRCode, WalletStatus
from apps.common.exceptions import NotFoundError, RequestError, ErrorCode
from apps.wallets.services.wallet_operations import WalletOperations


class QRCodeService:
    """Service for managing QR code payments"""

    @staticmethod
    async def create_qr_code(
        user: User,
        wallet_id: str,
        amount: Decimal = None,
        description: str = None,
        is_single_use: bool = False,
        is_amount_fixed: bool = False,
        expires_at: timezone.datetime = None,
    ) -> QRCode:
        """Create a new QR code for receiving payments"""

        # Get wallet
        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError("Wallet not found")

        if wallet.status != WalletStatus.ACTIVE:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Cannot create QR code for inactive wallet",
                status_code=400,
            )

        # Validate amount if provided
        if amount is not None and amount <= 0:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR,
                err_msg="Amount must be positive",
                status_code=400,
            )

        # Create QR code
        qr_code = QRCode(
            wallet=wallet,
            amount=amount,
            description=description,
            is_single_use=is_single_use,
            is_amount_fixed=is_amount_fixed,
            expires_at=expires_at,
            is_active=True,
        )

        # Generate QR code image
        qr_code.generate_qr_code()
        await qr_code.asave()

        return qr_code

    @staticmethod
    async def get_user_qr_codes(
        user: User, wallet_id: UUID = None, active_only: bool = True
    ) -> List[QRCode]:
        """Get user's QR codes"""

        filters = {"wallet__user": user}
        if wallet_id:
            filters["wallet__wallet_id"] = wallet_id
        if active_only:
            filters["is_active"] = True

        qr_codes = []
        async for qr_code in QRCode.objects.filter(**filters).select_related("wallet"):
            qr_codes.append(qr_code)

        return qr_codes

    @staticmethod
    async def get_qr_code(qr_id: UUID) -> QRCode:
        """Get a QR code by ID (public method for payments)"""

        qr_code = await QRCode.objects.select_related(
            "wallet", "wallet__user", "wallet__currency"
        ).aget_or_none(qr_id=qr_id)
        if not qr_code:
            raise NotFoundError("QR code not found")
        return qr_code

    @staticmethod
    async def get_user_qr_code(user: User, qr_id: UUID) -> QRCode:
        """Get a user's QR code"""

        qr_code = await QRCode.objects.select_related("wallet").aget_or_none(
            qr_id=qr_id, wallet__user=user
        )
        if not qr_code:
            raise NotFoundError("QR code not found")
        return qr_code

    @staticmethod
    async def update_qr_code(
        user: User,
        qr_id: UUID,
        description: str = None,
        expires_at: timezone.datetime = None,
        is_active: bool = None,
    ) -> QRCode:
        """Update QR code settings"""

        qr_code = await QRCodeService.get_user_qr_code(user, qr_id)

        if description is not None:
            qr_code.description = description
        if expires_at is not None:
            qr_code.expires_at = expires_at
        if is_active is not None:
            qr_code.is_active = is_active

        await qr_code.asave()
        return qr_code

    @staticmethod
    async def deactivate_qr_code(user: User, qr_id: str) -> QRCode:
        """Deactivate a QR code"""

        qr_code = await QRCodeService.get_user_qr_code(user, qr_id)
        qr_code.is_active = False
        await qr_code.asave()

        return qr_code

    @staticmethod
    async def validate_qr_payment(
        qr_id: UUID, amount: Decimal = None, payer_user: User = None
    ) -> tuple[QRCode, str]:
        """Validate a QR code payment"""

        qr_code = await QRCodeService.get_qr_code(qr_id)

        # Check if QR code can be used
        can_use, error_msg = qr_code.can_be_used()
        if not can_use:
            return None, error_msg

        # Check wallet status
        if qr_code.wallet.status != WalletStatus.ACTIVE:
            return None, "Recipient wallet is not active"

        # Validate amount
        if qr_code.is_amount_fixed:
            if not qr_code.amount:
                return None, "QR code has no fixed amount set"
            if amount and amount != qr_code.amount:
                return (
                    None,
                    f"Amount must be exactly {qr_code.amount} {qr_code.wallet.currency.code}",
                )
            amount = qr_code.amount
        else:
            if not amount or amount <= 0:
                return None, "Valid payment amount required"

        # Check if payer is trying to pay themselves
        if payer_user and payer_user.id == qr_code.wallet.user.id:
            return None, "Cannot pay yourself"

        return qr_code, None

    @staticmethod
    async def process_qr_payment(
        qr_id: str,
        payer_user: User,
        from_wallet_id: UUID,
        amount: Decimal = None,
        pin: str = None,
    ) -> Dict[str, Any]:
        """Process a QR code payment"""

        # Validate QR payment
        qr_code, error_msg = await QRCodeService.validate_qr_payment(
            qr_id, amount, payer_user
        )
        if not qr_code:
            raise RequestError(
                err_code=ErrorCode.VALIDATION_ERROR, err_msg=error_msg, status_code=400
            )

        # Use the amount from QR code if fixed, otherwise use provided amount
        payment_amount = qr_code.amount if qr_code.is_amount_fixed else amount

        # Process transfer
        transfer_result = await WalletOperations.transfer_between_wallets(
            from_user=payer_user,
            from_wallet_id=from_wallet_id,
            to_wallet_id=qr_code.wallet.wallet_id,
            amount=payment_amount,
            description=f"QR Payment: {qr_code.description or 'Payment via QR code'}",
            pin=pin,
            reference=f"QR_{qr_code.qr_id}",
        )

        # Update QR code usage
        qr_code.times_used += 1
        qr_code.total_received += payment_amount
        qr_code.last_used_at = timezone.now()

        # Deactivate if single use
        if qr_code.is_single_use:
            qr_code.is_active = False

        await qr_code.asave()

        return {
            "payment_id": transfer_result["transfer_id"],
            "qr_id": qr_code.qr_id,
            "amount": payment_amount,
            "currency": qr_code.wallet.currency.code,
            "recipient": {
                "name": qr_code.wallet.user.full_name,
                "wallet_name": qr_code.wallet.name,
            },
            "description": qr_code.description,
            "timestamp": timezone.now().isoformat(),
            "qr_deactivated": qr_code.is_single_use,
        }

    @staticmethod
    async def get_qr_code_details(
        qr_id: UUID, include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Get QR code details for display or payment"""

        qr_code = await QRCodeService.get_qr_code(qr_id)

        qr_data = {
            "qr_id": str(qr_code.qr_id),
            "recipient": {
                "name": qr_code.wallet.user.full_name,
                "wallet_name": qr_code.wallet.name,
            },
            "currency": {
                "code": qr_code.wallet.currency.code,
                "symbol": qr_code.wallet.currency.symbol,
                "name": qr_code.wallet.currency.name,
            },
            "amount": qr_code.amount,
            "description": qr_code.description,
            "is_amount_fixed": qr_code.is_amount_fixed,
            "is_single_use": qr_code.is_single_use,
            "expires_at": (
                qr_code.expires_at.isoformat() if qr_code.expires_at else None
            ),
            "is_active": qr_code.is_active,
            "is_expired": qr_code.is_expired(),
            "times_used": qr_code.times_used,
            "created_at": qr_code.created_at.isoformat(),
        }

        # Include sensitive data if requested (for QR code owner)
        if include_sensitive:
            qr_data.update(
                {
                    "wallet_id": qr_code.wallet.wallet_id,
                    "total_received": qr_code.total_received,
                    "last_used_at": (
                        qr_code.last_used_at.isoformat()
                        if qr_code.last_used_at
                        else None
                    ),
                    "qr_image_url": qr_code.qr_image.url if qr_code.qr_image else None,
                }
            )

        return qr_data

    @staticmethod
    async def get_qr_payment_history(user: User, qr_id: UUID) -> List[Dict[str, Any]]:
        """Get payment history for a QR code"""

        qr_code = await QRCodeService.get_user_qr_code(user, qr_id)

        # This would typically query a transactions table
        # For now, return a placeholder structure based on QR code usage
        return [
            {
                "payment_id": f"qr_payment_{i}",
                "amount": qr_code.total_received / max(qr_code.times_used, 1),
                "payer": "Anonymous",  # In real implementation, would show payer details
                "timestamp": (
                    qr_code.last_used_at.isoformat() if qr_code.last_used_at else None
                ),
                "status": "completed",
                "description": qr_code.description,
            }
            for i in range(min(qr_code.times_used, 10))  # Show last 10 payments
        ]

    @staticmethod
    async def get_qr_analytics(user: User, wallet_id: UUID = None) -> Dict[str, Any]:
        """Get QR code analytics for user"""

        filters = {"wallet__user": user}
        if wallet_id:
            filters["wallet__wallet_id"] = wallet_id

        total_qr_codes = await QRCode.objects.filter(**filters).acount()
        active_qr_codes = await QRCode.objects.filter(
            **filters, is_active=True
        ).acount()

        # Aggregate statistics
        total_received = Decimal("0")
        total_uses = 0

        async for qr_code in QRCode.objects.filter(**filters):
            total_received += qr_code.total_received
            total_uses += qr_code.times_used

        return {
            "total_qr_codes": total_qr_codes,
            "active_qr_codes": active_qr_codes,
            "total_received": total_received,
            "total_uses": total_uses,
            "average_per_qr": total_received / max(total_qr_codes, 1),
            "average_per_use": total_received / max(total_uses, 1),
        }

    @staticmethod
    async def regenerate_qr_image(user: User, qr_id: UUID) -> QRCode:
        """Regenerate QR code image"""

        qr_code = await QRCodeService.get_user_qr_code(user, qr_id)

        qr_code.generate_qr_code()
        await qr_code.asave()
        return qr_code

    @staticmethod
    async def bulk_deactivate_qr_codes(user: User, wallet_id: UUID = None) -> int:
        """Bulk deactivate QR codes"""

        filters = {"wallet__user": user, "is_active": True}
        if wallet_id:
            filters["wallet__wallet_id"] = wallet_id

        count = await QRCode.objects.filter(**filters).aupdate(is_active=False)
        return count
