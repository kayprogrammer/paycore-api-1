from uuid import UUID
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from typing import Dict, Any
import hashlib

from apps.accounts.models import User
from apps.accounts.auth import Authentication
from apps.wallets.models import Wallet
from apps.common.exceptions import (
    NotFoundError,
    RequestError,
    ErrorCode,
    BodyValidationError,
)


class WalletSecurityService:
    """Service for wallet security operations"""

    @staticmethod
    async def verify_transaction_auth(
        user: User,
        wallet_id: UUID,
        amount: float,
        pin: str = None,
        biometric_token: str = None,
        device_id: str = None,
    ) -> Dict[str, Any]:
        """Verify user authorization for wallet transaction"""

        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError("Wallet not found")

        auth_methods_used = []

        # Check PIN if required or provided
        if wallet.requires_pin or pin:
            if not pin:
                raise BodyValidationError("pin", "PIN is required for this wallet")

            if not wallet.pin_hash or not check_password(pin, wallet.pin_hash):
                raise BodyValidationError("pin", "Invalid PIN")
            auth_methods_used.append("pin")

        # Check biometric authentication if required or provided
        if wallet.requires_biometric or biometric_token:
            if not biometric_token or not device_id:
                raise BodyValidationError(
                    "biometric_token",
                    "Biometric token and device ID are required for this wallet",
                )

            auth_user, _ = await Authentication.validate_trust_token(
                user.email, biometric_token, device_id
            )

            if not auth_user or auth_user.id != user.id:
                raise BodyValidationError("biometric_token", "Invalid biometric token")
            auth_methods_used.append("biometric")

        # Generate transaction authorization token
        auth_token = WalletSecurityService._generate_transaction_token(
            user, wallet, amount
        )

        return {
            "authorized": True,
            "auth_methods": auth_methods_used,
            "auth_token": auth_token,
            "expires_at": (timezone.now() + timezone.timedelta(minutes=5)).isoformat(),
        }

    @staticmethod
    def _generate_transaction_token(user: User, wallet: Wallet, amount: float) -> str:
        """Generate a short-lived transaction authorization token"""

        timestamp = str(int(timezone.now().timestamp()))
        data = f"{user.id}:{wallet.wallet_id}:{amount}:{timestamp}"
        token = hashlib.sha256(data.encode()).hexdigest()[:16]

        return f"txn_{token}_{timestamp}"

    @staticmethod
    async def validate_transaction_token(
        user: User, wallet_id: str, amount: float, auth_token: str
    ) -> bool:
        """Validate a transaction authorization token"""

        if not auth_token.startswith("txn_"):
            return False

        try:
            parts = auth_token.split("_")
            if len(parts) != 3:
                return False

            token_hash = parts[1]
            timestamp = int(parts[2])

            # Check if token is expired (5 minutes)
            if timezone.now().timestamp() - timestamp > 300:
                return False

            # Regenerate expected token
            expected_data = f"{user.id}:{wallet_id}:{amount}:{timestamp}"
            expected_token = hashlib.sha256(expected_data.encode()).hexdigest()[:16]

            return token_hash == expected_token

        except (ValueError, IndexError):
            return False

    @staticmethod
    async def enable_wallet_security(
        user: User,
        wallet_id: UUID,
        pin: str = None,
        enable_biometric: bool = False,
    ) -> Dict[str, Any]:
        """Enable security features for a wallet"""

        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError(err_msg="Wallet not found")

        security_features = []

        # Set PIN if provided
        if pin:
            wallet.pin_hash = make_password(str(pin))
            wallet.requires_pin = True
            security_features.append("pin")

        # Enable biometric if requested
        if enable_biometric:
            if not user.biometrics_enabled:
                raise RequestError(
                    err_code=ErrorCode.NOT_ALLOWED,
                    err_msg="Biometrics not enabled for user account",
                    status_code=400,
                )

            wallet.requires_biometric = True
            security_features.append("biometric")

        await wallet.asave()

        return {
            "wallet_id": wallet.wallet_id,
            "requires_pin": wallet.requires_pin,
            "requires_biometric": wallet.requires_biometric,
            "has_pin_set": bool(wallet.pin_hash),
            "user_biometric_enabled": user.biometrics_enabled,
            "security_level": WalletSecurityService._calculate_security_level(
                wallet, user
            ),
        }

    @staticmethod
    async def disable_wallet_security(
        user: User,
        wallet_id: UUID,
        current_pin: str = None,
        disable_pin: bool = False,
        disable_biometric: bool = False,
    ) -> Dict[str, Any]:
        """Disable security features for a wallet"""

        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError("Wallet not found")

        # Verify current PIN if disabling PIN or if PIN is currently required
        if wallet.requires_pin and (disable_pin or disable_biometric):
            if not current_pin:
                raise BodyValidationError(
                    "current_pin", "Current PIN required to modify security settings"
                )

            if not check_password(current_pin, wallet.pin_hash):
                raise BodyValidationError("current_pin", "Invalid current PIN")
        security_features_disabled = []

        # Disable PIN
        if disable_pin:
            wallet.pin_hash = None
            wallet.requires_pin = False
            security_features_disabled.append("pin")

        # Disable biometric
        if disable_biometric:
            wallet.requires_biometric = False
            security_features_disabled.append("biometric")
        await wallet.asave()

        return {
            "wallet_id": wallet.wallet_id,
            "requires_pin": wallet.requires_pin,
            "requires_biometric": wallet.requires_biometric,
            "has_pin_set": bool(wallet.pin_hash),
            "user_biometric_enabled": user.biometrics_enabled,
            "security_level": WalletSecurityService._calculate_security_level(
                wallet, user
            ),
        }

    @staticmethod
    async def change_wallet_pin(
        user: User, wallet_id: str, current_pin: str, new_pin: str
    ) -> Dict[str, Any]:
        """Change wallet PIN"""

        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError(err_msg="Wallet not found")

        # Verify PINS
        if not wallet.pin_hash or not check_password(current_pin, wallet.pin_hash):
            raise BodyValidationError("current_pin", "Invalid current PIN")

        if current_pin == new_pin:
            raise BodyValidationError(
                "new_pin", "New PIN must be different from current PIN"
            )

        wallet.pin_hash = make_password(str(new_pin))
        await wallet.asave()

        return {"wallet_id": wallet.wallet_id, "message": "PIN changed successfully"}

    @staticmethod
    async def get_wallet_security_status(user: User, wallet_id: UUID) -> Dict[str, Any]:
        """Get wallet security configuration"""

        wallet = await Wallet.objects.aget_or_none(wallet_id=wallet_id, user=user)
        if not wallet:
            raise NotFoundError(err_msg="Wallet not found")

        return {
            "wallet_id": wallet.wallet_id,
            "requires_pin": wallet.requires_pin,
            "requires_biometric": wallet.requires_biometric,
            "has_pin_set": bool(wallet.pin_hash),
            "user_biometric_enabled": user.biometrics_enabled,
            "security_level": WalletSecurityService._calculate_security_level(
                wallet, user
            ),
        }

    @staticmethod
    def _calculate_security_level(wallet: Wallet, user: User) -> str:
        """Calculate wallet security level"""

        score = 0

        if wallet.requires_pin and wallet.pin_hash:
            score += 1

        if wallet.requires_biometric and user.biometrics_enabled:
            score += 2

        if score == 0:
            return "basic"
        elif score == 1:
            return "medium"
        elif score >= 2:
            return "high"
        else:
            return "basic"
