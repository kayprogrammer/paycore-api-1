from django.core.management.base import BaseCommand
from django.db import transaction
from apps.bills.models import BillProvider, BillPackage, BillCategory
from decimal import Decimal


class Command(BaseCommand):
    help = "Seed bill payment providers and packages using bulk operations"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Seeding bill payment providers..."))

        with transaction.atomic():
            # Prepare all providers data
            providers_data = self._get_providers_data()

            # Bulk create/update providers
            providers = self._bulk_upsert_providers(providers_data)

            # Prepare all packages data
            packages_data = self._get_packages_data(providers)

            # Bulk create/update packages
            self._bulk_upsert_packages(packages_data)

        # Summary
        provider_count = BillProvider.objects.count()
        package_count = BillPackage.objects.count()

        self.stdout.write(
            self.style.SUCCESS(f"\n✅ Successfully seeded bill providers!")
        )
        self.stdout.write(self.style.SUCCESS(f"   Total Providers: {provider_count}"))
        self.stdout.write(self.style.SUCCESS(f"   Total Packages: {package_count}"))
        self.stdout.write(
            self.style.WARNING(
                f"\n⚠️  Note: These are sample providers using Flutterwave codes."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f"   Update provider_code values based on your payment gateway."
            )
        )

    def _get_providers_data(self):
        """Get all providers data as a list of dictionaries"""
        return [
            # ============ AIRTIME PROVIDERS ============
            {
                "provider_code": "BIL099",
                "name": "MTN Airtime",
                "slug": "mtn-airtime",
                "category": BillCategory.AIRTIME,
                "supports_amount_range": True,
                "min_amount": Decimal("50.00"),
                "max_amount": Decimal("50000.00"),
                "fee_type": "flat",
                "fee_amount": Decimal("20.00"),
                "is_active": True,
                "is_available": True,
                "description": "Buy MTN airtime instantly",
            },
            {
                "provider_code": "BIL102",
                "name": "Airtel Airtime",
                "slug": "airtel-airtime",
                "category": BillCategory.AIRTIME,
                "supports_amount_range": True,
                "min_amount": Decimal("50.00"),
                "max_amount": Decimal("50000.00"),
                "fee_type": "flat",
                "fee_amount": Decimal("20.00"),
                "is_active": True,
                "is_available": True,
                "description": "Buy Airtel airtime instantly",
            },
            {
                "provider_code": "BIL103",
                "name": "Glo Airtime",
                "slug": "glo-airtime",
                "category": BillCategory.AIRTIME,
                "supports_amount_range": True,
                "min_amount": Decimal("50.00"),
                "max_amount": Decimal("50000.00"),
                "fee_type": "flat",
                "fee_amount": Decimal("20.00"),
                "is_active": True,
                "is_available": True,
                "description": "Buy Glo airtime instantly",
            },
            {
                "provider_code": "BIL104",
                "name": "9mobile Airtime",
                "slug": "9mobile-airtime",
                "category": BillCategory.AIRTIME,
                "supports_amount_range": True,
                "min_amount": Decimal("50.00"),
                "max_amount": Decimal("50000.00"),
                "fee_type": "flat",
                "fee_amount": Decimal("20.00"),
                "is_active": True,
                "is_available": True,
                "description": "Buy 9mobile airtime instantly",
            },
            # ============ DATA PROVIDERS ============
            {
                "provider_code": "BIL122",
                "name": "MTN Data",
                "slug": "mtn-data",
                "category": BillCategory.DATA,
                "supports_amount_range": False,
                "fee_type": "flat",
                "fee_amount": Decimal("20.00"),
                "is_active": True,
                "is_available": True,
                "description": "Buy MTN data bundles",
            },
            {
                "provider_code": "BIL108",
                "name": "Airtel Data",
                "slug": "airtel-data",
                "category": BillCategory.DATA,
                "supports_amount_range": False,
                "fee_type": "flat",
                "fee_amount": Decimal("20.00"),
                "is_active": True,
                "is_available": True,
                "description": "Buy Airtel data bundles",
            },
            # ============ ELECTRICITY PROVIDERS ============
            {
                "provider_code": "BIL119",
                "name": "EKEDC Prepaid",
                "slug": "ekedc-prepaid",
                "category": BillCategory.ELECTRICITY,
                "supports_amount_range": True,
                "min_amount": Decimal("500.00"),
                "max_amount": Decimal("500000.00"),
                "fee_type": "percentage",
                "fee_amount": Decimal("1.00"),
                "fee_cap": Decimal("100.00"),
                "requires_customer_validation": True,
                "is_active": True,
                "is_available": True,
                "description": "Buy EKEDC prepaid electricity units",
            },
            {
                "provider_code": "BIL121",
                "name": "IKEDC Prepaid",
                "slug": "ikedc-prepaid",
                "category": BillCategory.ELECTRICITY,
                "supports_amount_range": True,
                "min_amount": Decimal("500.00"),
                "max_amount": Decimal("500000.00"),
                "fee_type": "percentage",
                "fee_amount": Decimal("1.00"),
                "fee_cap": Decimal("100.00"),
                "requires_customer_validation": True,
                "is_active": True,
                "is_available": True,
                "description": "Buy IKEDC prepaid electricity units",
            },
            {
                "provider_code": "BIL123",
                "name": "AEDC Prepaid",
                "slug": "aedc-prepaid",
                "category": BillCategory.ELECTRICITY,
                "supports_amount_range": True,
                "min_amount": Decimal("500.00"),
                "max_amount": Decimal("500000.00"),
                "fee_type": "percentage",
                "fee_amount": Decimal("1.00"),
                "fee_cap": Decimal("100.00"),
                "requires_customer_validation": True,
                "is_active": True,
                "is_available": True,
                "description": "Buy AEDC prepaid electricity units",
            },
            # ============ CABLE TV PROVIDERS ============
            {
                "provider_code": "BIL114",
                "name": "DSTV",
                "slug": "dstv",
                "category": BillCategory.CABLE_TV,
                "supports_amount_range": False,
                "fee_type": "percentage",
                "fee_amount": Decimal("1.00"),
                "fee_cap": Decimal("100.00"),
                "requires_customer_validation": True,
                "is_active": True,
                "is_available": True,
                "description": "Renew DSTV subscription",
            },
            {
                "provider_code": "BIL115",
                "name": "GOtv",
                "slug": "gotv",
                "category": BillCategory.CABLE_TV,
                "supports_amount_range": False,
                "fee_type": "percentage",
                "fee_amount": Decimal("1.00"),
                "fee_cap": Decimal("50.00"),
                "requires_customer_validation": True,
                "is_active": True,
                "is_available": True,
                "description": "Renew GOtv subscription",
            },
            {
                "provider_code": "BIL116",
                "name": "StarTimes",
                "slug": "startimes",
                "category": BillCategory.CABLE_TV,
                "supports_amount_range": False,
                "fee_type": "flat",
                "fee_amount": Decimal("50.00"),
                "requires_customer_validation": True,
                "is_active": True,
                "is_available": True,
                "description": "Renew StarTimes subscription",
            },
        ]

    def _bulk_upsert_providers(self, providers_data):
        """Bulk create or update providers"""
        # Get existing providers
        existing_codes = set(
            BillProvider.objects.values_list("provider_code", flat=True)
        )

        providers_to_create = []
        providers_to_update = []

        for data in providers_data:
            provider_code = data["provider_code"]

            if provider_code in existing_codes:
                # Update existing
                BillProvider.objects.filter(provider_code=provider_code).update(**data)
                self.stdout.write(f"↻ Updated: {data['name']}")
            else:
                # Prepare for bulk creation
                providers_to_create.append(BillProvider(**data))

        # Bulk create new providers
        if providers_to_create:
            created = BillProvider.objects.bulk_create(
                providers_to_create, ignore_conflicts=True
            )
            for provider in created:
                self.stdout.write(f"✓ Created: {provider.name}")

        # Return all providers as dict {provider_code: provider_object}
        return {
            p.provider_code: p
            for p in BillProvider.objects.filter(
                provider_code__in=[d["provider_code"] for d in providers_data]
            )
        }

    def _get_packages_data(self, providers):
        """Get all packages data"""
        packages = []

        # MTN Data Packages
        mtn_data_packages = [
            ("MTN-1GB-D", "1GB Daily", Decimal("300"), "1 day", False, 0),
            ("MTN-2GB-W", "2GB Weekly", Decimal("500"), "7 days", True, 1),
            ("MTN-5GB-M", "5GB Monthly", Decimal("1500"), "30 days", True, 2),
            ("MTN-10GB-M", "10GB Monthly", Decimal("2500"), "30 days", True, 3),
            ("MTN-20GB-M", "20GB Monthly", Decimal("4000"), "30 days", False, 4),
            ("MTN-40GB-M", "40GB Monthly", Decimal("10000"), "30 days", False, 5),
        ]

        if "BIL122" in providers:
            for code, name, amount, validity, is_popular, order in mtn_data_packages:
                packages.append(
                    {
                        "provider": providers["BIL122"],
                        "code": code,
                        "name": name,
                        "amount": amount,
                        "validity_period": validity,
                        "is_popular": is_popular,
                        "display_order": order,
                        "is_active": True,
                    }
                )

        # DSTV Packages
        dstv_packages = [
            ("DSTV-PADI", "DSTV Padi", Decimal("2500"), "1 month", False, 0),
            ("DSTV-YANGA", "DSTV Yanga", Decimal("3500"), "1 month", False, 1),
            ("DSTV-CONFAM", "DSTV Confam", Decimal("5300"), "1 month", True, 2),
            ("DSTV-COMPACT", "DSTV Compact", Decimal("10500"), "1 month", True, 3),
            (
                "DSTV-COMPACT-PLUS",
                "DSTV Compact Plus",
                Decimal("16600"),
                "1 month",
                True,
                4,
            ),
            ("DSTV-PREMIUM", "DSTV Premium", Decimal("24500"), "1 month", False, 5),
        ]

        if "BIL114" in providers:
            for code, name, amount, validity, is_popular, order in dstv_packages:
                packages.append(
                    {
                        "provider": providers["BIL114"],
                        "code": code,
                        "name": name,
                        "amount": amount,
                        "validity_period": validity,
                        "is_popular": is_popular,
                        "display_order": order,
                        "is_active": True,
                    }
                )

        # GOtv Packages
        gotv_packages = [
            ("GOTV-SMALLIE", "GOtv Smallie", Decimal("1100"), "1 month", False, 0),
            ("GOTV-JINJA", "GOtv Jinja", Decimal("2250"), "1 month", True, 1),
            ("GOTV-JOLLI", "GOtv Jolli", Decimal("3300"), "1 month", True, 2),
            ("GOTV-MAX", "GOtv Max", Decimal("4850"), "1 month", False, 3),
        ]

        if "BIL115" in providers:
            for code, name, amount, validity, is_popular, order in gotv_packages:
                packages.append(
                    {
                        "provider": providers["BIL115"],
                        "code": code,
                        "name": name,
                        "amount": amount,
                        "validity_period": validity,
                        "is_popular": is_popular,
                        "display_order": order,
                        "is_active": True,
                    }
                )

        return packages

    def _bulk_upsert_packages(self, packages_data):
        """Bulk create or update packages"""
        # Get existing packages (provider_id + code combination)
        existing_packages = {
            (p.provider_id, p.code): p
            for p in BillPackage.objects.select_related("provider").all()
        }

        packages_to_create = []
        packages_to_update = []

        for data in packages_data:
            provider_id = data["provider"].id
            code = data["code"]
            key = (provider_id, code)

            if key in existing_packages:
                # Update existing
                existing_pkg = existing_packages[key]
                for field, value in data.items():
                    if field != "provider":  # Don't update provider FK
                        setattr(existing_pkg, field, value)
                packages_to_update.append(existing_pkg)
                self.stdout.write(f"  ↻ Updated package: {data['name']}")
            else:
                # Prepare for bulk creation
                packages_to_create.append(BillPackage(**data))

        # Bulk update
        if packages_to_update:
            BillPackage.objects.bulk_update(
                packages_to_update,
                [
                    "name",
                    "amount",
                    "validity_period",
                    "is_popular",
                    "display_order",
                    "is_active",
                ],
            )

        # Bulk create
        if packages_to_create:
            created = BillPackage.objects.bulk_create(
                packages_to_create, ignore_conflicts=True
            )
            for package in created:
                self.stdout.write(f"  ✓ Created package: {package.name}")
