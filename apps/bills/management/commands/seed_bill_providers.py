from django.core.management.base import BaseCommand
from apps.bills.models import BillProvider, BillPackage, BillCategory
from decimal import Decimal


class Command(BaseCommand):
    help = "Seed bill payment providers and packages"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Seeding bill payment providers..."))

        # ============================================================================
        # AIRTIME PROVIDERS
        # ============================================================================

        mtn_airtime, _ = BillProvider.objects.get_or_create(
            provider_code="BIL099",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {mtn_airtime.name}")

        airtel_airtime, _ = BillProvider.objects.get_or_create(
            provider_code="BIL102",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {airtel_airtime.name}")

        glo_airtime, _ = BillProvider.objects.get_or_create(
            provider_code="BIL103",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {glo_airtime.name}")

        mobile9_airtime, _ = BillProvider.objects.get_or_create(
            provider_code="BIL104",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {mobile9_airtime.name}")

        # ============================================================================
        # DATA PROVIDERS WITH PACKAGES
        # ============================================================================

        mtn_data, _ = BillProvider.objects.get_or_create(
            provider_code="BIL122",
            defaults={
                "name": "MTN Data",
                "slug": "mtn-data",
                "category": BillCategory.DATA,
                "supports_amount_range": False,  # Predefined packages only
                "fee_type": "flat",
                "fee_amount": Decimal("20.00"),
                "is_active": True,
                "is_available": True,
                "description": "Buy MTN data bundles",
            },
        )
        self.stdout.write(f"✓ Created: {mtn_data.name}")

        # MTN Data Packages
        mtn_packages = [
            {
                "name": "1GB Daily",
                "code": "MTN-1GB-D",
                "amount": Decimal("300"),
                "validity": "1 day",
                "is_popular": False,
            },
            {
                "name": "2GB Weekly",
                "code": "MTN-2GB-W",
                "amount": Decimal("500"),
                "validity": "7 days",
                "is_popular": True,
            },
            {
                "name": "5GB Monthly",
                "code": "MTN-5GB-M",
                "amount": Decimal("1500"),
                "validity": "30 days",
                "is_popular": True,
            },
            {
                "name": "10GB Monthly",
                "code": "MTN-10GB-M",
                "amount": Decimal("2500"),
                "validity": "30 days",
                "is_popular": True,
            },
            {
                "name": "20GB Monthly",
                "code": "MTN-20GB-M",
                "amount": Decimal("4000"),
                "validity": "30 days",
                "is_popular": False,
            },
            {
                "name": "40GB Monthly",
                "code": "MTN-40GB-M",
                "amount": Decimal("10000"),
                "validity": "30 days",
                "is_popular": False,
            },
        ]

        for idx, pkg in enumerate(mtn_packages):
            BillPackage.objects.get_or_create(
                provider=mtn_data,
                code=pkg["code"],
                defaults={
                    "name": pkg["name"],
                    "amount": pkg["amount"],
                    "validity_period": pkg["validity"],
                    "is_popular": pkg["is_popular"],
                    "display_order": idx,
                    "is_active": True,
                },
            )

        airtel_data, _ = BillProvider.objects.get_or_create(
            provider_code="BIL108",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {airtel_data.name}")

        # ============================================================================
        # ELECTRICITY PROVIDERS
        # ============================================================================

        ekedc_prepaid, _ = BillProvider.objects.get_or_create(
            provider_code="BIL119",
            defaults={
                "name": "EKEDC Prepaid",
                "slug": "ekedc-prepaid",
                "category": BillCategory.ELECTRICITY,
                "supports_amount_range": True,
                "min_amount": Decimal("500.00"),
                "max_amount": Decimal("500000.00"),
                "fee_type": "percentage",
                "fee_amount": Decimal("1.00"),  # 1%
                "fee_cap": Decimal("100.00"),
                "requires_customer_validation": True,
                "is_active": True,
                "is_available": True,
                "description": "Buy EKEDC prepaid electricity units",
            },
        )
        self.stdout.write(f"✓ Created: {ekedc_prepaid.name}")

        ikedc_prepaid, _ = BillProvider.objects.get_or_create(
            provider_code="BIL121",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {ikedc_prepaid.name}")

        aedc_prepaid, _ = BillProvider.objects.get_or_create(
            provider_code="BIL123",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {aedc_prepaid.name}")

        # ============================================================================
        # CABLE TV PROVIDERS WITH PACKAGES
        # ============================================================================

        dstv, _ = BillProvider.objects.get_or_create(
            provider_code="BIL114",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {dstv.name}")

        # DSTV Packages
        dstv_packages = [
            {
                "name": "DSTV Padi",
                "code": "DSTV-PADI",
                "amount": Decimal("2500"),
                "validity": "1 month",
                "is_popular": False,
            },
            {
                "name": "DSTV Yanga",
                "code": "DSTV-YANGA",
                "amount": Decimal("3500"),
                "validity": "1 month",
                "is_popular": False,
            },
            {
                "name": "DSTV Confam",
                "code": "DSTV-CONFAM",
                "amount": Decimal("5300"),
                "validity": "1 month",
                "is_popular": True,
            },
            {
                "name": "DSTV Compact",
                "code": "DSTV-COMPACT",
                "amount": Decimal("10500"),
                "validity": "1 month",
                "is_popular": True,
            },
            {
                "name": "DSTV Compact Plus",
                "code": "DSTV-COMPACT-PLUS",
                "amount": Decimal("16600"),
                "validity": "1 month",
                "is_popular": True,
            },
            {
                "name": "DSTV Premium",
                "code": "DSTV-PREMIUM",
                "amount": Decimal("24500"),
                "validity": "1 month",
                "is_popular": False,
            },
        ]

        for idx, pkg in enumerate(dstv_packages):
            BillPackage.objects.get_or_create(
                provider=dstv,
                code=pkg["code"],
                defaults={
                    "name": pkg["name"],
                    "amount": pkg["amount"],
                    "validity_period": pkg["validity"],
                    "is_popular": pkg["is_popular"],
                    "display_order": idx,
                    "is_active": True,
                },
            )

        gotv, _ = BillProvider.objects.get_or_create(
            provider_code="BIL115",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {gotv.name}")

        # GOtv Packages
        gotv_packages = [
            {
                "name": "GOtv Smallie",
                "code": "GOTV-SMALLIE",
                "amount": Decimal("1100"),
                "validity": "1 month",
                "is_popular": False,
            },
            {
                "name": "GOtv Jinja",
                "code": "GOTV-JINJA",
                "amount": Decimal("2250"),
                "validity": "1 month",
                "is_popular": True,
            },
            {
                "name": "GOtv Jolli",
                "code": "GOTV-JOLLI",
                "amount": Decimal("3300"),
                "validity": "1 month",
                "is_popular": True,
            },
            {
                "name": "GOtv Max",
                "code": "GOTV-MAX",
                "amount": Decimal("4850"),
                "validity": "1 month",
                "is_popular": False,
            },
        ]

        for idx, pkg in enumerate(gotv_packages):
            BillPackage.objects.get_or_create(
                provider=gotv,
                code=pkg["code"],
                defaults={
                    "name": pkg["name"],
                    "amount": pkg["amount"],
                    "validity_period": pkg["validity"],
                    "is_popular": pkg["is_popular"],
                    "display_order": idx,
                    "is_active": True,
                },
            )

        startimes, _ = BillProvider.objects.get_or_create(
            provider_code="BIL116",
            defaults={
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
        )
        self.stdout.write(f"✓ Created: {startimes.name}")

        # ============================================================================
        # SUMMARY
        # ============================================================================

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
