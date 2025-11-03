from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.hashers import make_password
from datetime import date

from apps.accounts.models import User
from apps.compliance.models import KYCVerification, KYCStatus, KYCLevel, DocumentType
from apps.wallets.models import (
    Wallet,
    Currency,
    WalletType,
    WalletStatus,
    AccountProvider,
)
from apps.profiles.models import Country


class Command(BaseCommand):
    help = "Seeds test users with verified KYC and NGN wallets"

    def handle(self, *args, **options):
        self.stdout.write("Starting user seed...")

        try:
            with transaction.atomic():
                # Get Nigeria and NGN currency
                nigeria = Country.objects.filter(code="NG").first()
                if not nigeria:
                    self.stdout.write(
                        self.style.WARNING(
                            "Nigeria not found. Run 'python manage.py upsert_countries' first."
                        )
                    )
                    return

                ngn_currency = Currency.objects.filter(code="NGN").first()
                if not ngn_currency:
                    self.stdout.write(
                        self.style.WARNING("NGN currency not found. Creating...")
                    )
                    ngn_currency = Currency.objects.create(
                        name="Nigerian Naira",
                        code="NGN",
                        symbol="₦",
                        decimal_places=2,
                        is_crypto=False,
                        is_active=True,
                        exchange_rate_usd=0.0013,  # Approximate rate
                    )

                # User data
                users_data = [
                    {
                        "email": "test@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "phone": "+2348112345678",
                        "is_staff": False,
                        "is_email_verified": True,
                        "dob": date(1990, 5, 15),
                    },
                    {
                        "email": "test2@example.com",
                        "first_name": "Jane",
                        "last_name": "Smith",
                        "phone": "+2348087654321",
                        "is_staff": True,
                        "is_email_verified": True,
                        "dob": date(1988, 8, 22),
                    },
                ]

                created_count = 0
                updated_count = 0

                for user_data in users_data:
                    email = user_data["email"]

                    # Create or update user
                    user, created = User.objects.update_or_create(
                        email=email,
                        defaults={
                            "first_name": user_data["first_name"],
                            "last_name": user_data["last_name"],
                            "phone": user_data["phone"],
                            "is_staff": user_data["is_staff"],
                            "is_active": True,
                            "is_email_verified": user_data["is_email_verified"],
                            "dob": user_data["dob"],
                            "password": make_password(
                                "password123"
                            ),  # Default password
                        },
                    )

                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"✓ Created user: {user.email}")
                        )
                    else:
                        updated_count += 1
                        self.stdout.write(
                            self.style.WARNING(f"→ Updated user: {user.email}")
                        )

                    # Create or update KYC verification
                    kyc, kyc_created = KYCVerification.objects.update_or_create(
                        user=user,
                        defaults={
                            "level": KYCLevel.TIER_2,
                            "status": KYCStatus.APPROVED,
                            "first_name": user_data["first_name"],
                            "last_name": user_data["last_name"],
                            "middle_name": "",
                            "date_of_birth": user_data["dob"],
                            "nationality": "NG",
                            "phone_number": user_data["phone"],
                            "address_line_1": "123 Test Street",
                            "address_line_2": "Suite 456",
                            "city": "Lagos",
                            "state": "Lagos",
                            "postal_code": "100001",
                            "country": nigeria,
                            "document_type": DocumentType.NATIONAL_ID,
                            "document_number": f"NIN{user_data['phone'][-8:]}",
                            "document_expiry_date": date(2030, 1, 1),
                            "document_issuing_country_id": nigeria.id,
                        },
                    )

                    if kyc_created:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ Created KYC verification for {user.email}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  → Updated KYC verification for {user.email}"
                            )
                        )

                    # Create or update NGN wallet
                    wallet, wallet_created = Wallet.objects.update_or_create(
                        user=user,
                        currency=ngn_currency,
                        wallet_type=WalletType.MAIN,
                        defaults={
                            "name": "NGN Main Wallet",
                            "balance": 100000.00,  # 100k NGN starting balance
                            "status": WalletStatus.ACTIVE,
                            "account_provider": AccountProvider.INTERNAL,
                            "account_name": user.full_name,
                            "bank_name": "PayCore",
                            "is_default": True,
                            "pin_hash": make_password("1234"),  # Default PIN: 1234
                            "daily_limit": 1000000.00,  # 1M NGN
                        },
                    )

                    if wallet_created:
                        # Generate account number for new wallets
                        wallet.account_number = f"20{str(wallet.id.int)[:8]}"
                        wallet.save(update_fields=["account_number"])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ Created NGN wallet for {user.email} (Balance: ₦100,000)"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  → Updated NGN wallet for {user.email}"
                            )
                        )

                    self.stdout.write("")  # Blank line

                # Summary
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n{'='*60}\n"
                        f"✓ Seed completed successfully!\n"
                        f"  - Users created: {created_count}\n"
                        f"  - Users updated: {updated_count}\n"
                        f"  - Total users: {len(users_data)}\n"
                        f"\n"
                        f"Test Credentials:\n"
                        f"  Email: test@example.com | Password: password123 | PIN: 1234\n"
                        f"  Email: test2@example.com | Password: password123 | PIN: 1234 (Staff)\n"
                        f"{'='*60}"
                    )
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error during seed: {str(e)}"))
            raise
