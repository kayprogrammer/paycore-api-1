from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any


class BaseWithdrawalProvider(ABC):
    """Abstract base class for withdrawal providers"""

    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode

    @abstractmethod
    async def initiate_withdrawal(
        self,
        user_email: str,
        user_first_name: str,
        user_last_name: str,
        amount: Decimal,
        currency_code: str,
        reference: str,
        account_details: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Initiate a withdrawal transaction.

        Args:
            user_email: User's email address
            user_first_name: User's first name
            user_last_name: User's last name
            amount: Amount to withdraw
            currency_code: Currency code (NGN, USD, etc.)
            reference: Unique transaction reference
            account_details: Bank account details (account_number, bank_code, etc.)
            **kwargs: Additional provider-specific parameters

        Returns:
            dict: {
                "reference": str,
                "provider_reference": str,
                "status": str,  # "pending", "processing", "completed", "failed"
                "amount": Decimal,
                "currency": str,
                "recipient": dict,  # account details
                "transfer_code": str (optional),
                "estimated_completion": str (optional),
                "metadata": dict
            }
        """
        pass

    @abstractmethod
    async def verify_withdrawal(self, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Verify withdrawal transaction status.

        Args:
            reference: Transaction reference or provider reference
            **kwargs: Additional provider-specific parameters

        Returns:
            dict: {
                "reference": str,
                "provider_reference": str,
                "status": str,  # "success", "failed", "pending", "processing"
                "amount": Decimal,
                "currency": str,
                "completed_at": float (optional, timestamp),
                "failure_reason": str (optional),
                "metadata": dict
            }
        """
        pass

    @abstractmethod
    async def get_banks(self, currency_code: str = None) -> list:
        """
        Get list of supported banks for withdrawals.

        Args:
            currency_code: Optional currency filter

        Returns:
            list: [{"name": str, "code": str, "currency": str}, ...]
        """
        pass

    @abstractmethod
    async def verify_account_number(
        self, account_number: str, bank_code: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Verify bank account number and get account name.

        Args:
            account_number: Bank account number
            bank_code: Bank code
            **kwargs: Additional provider-specific parameters

        Returns:
            dict: {
                "account_number": str,
                "account_name": str,
                "bank_code": str,
                "bank_name": str
            }
        """
        pass
