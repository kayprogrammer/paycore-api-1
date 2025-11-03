from django.core.management.base import BaseCommand
from django.db import transaction
from apps.support.models import FAQ, TicketCategory


class Command(BaseCommand):
    help = "Seed FAQs (Frequently Asked Questions) using bulk operations"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Seeding FAQs..."))

        with transaction.atomic():
            # Prepare FAQ data
            faqs_data = self._get_faqs_data()

            # Bulk upsert FAQs
            self._bulk_upsert_faqs(faqs_data)

        # Summary
        faq_count = FAQ.objects.count()
        published_count = FAQ.objects.filter(is_published=True).count()

        self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully seeded FAQs!"))
        self.stdout.write(self.style.SUCCESS(f"   Total FAQs: {faq_count}"))
        self.stdout.write(self.style.SUCCESS(f"   Published: {published_count}"))
        self.stdout.write(
            self.style.WARNING(
                f"\n⚠️  Note: Customize answers based on your business policies and procedures."
            )
        )

    def _get_faqs_data(self):
        """Get all FAQ data"""
        faqs = []

        # ============ ACCOUNT FAQS ============
        faqs.extend(
            [
                {
                    "question": "How do I create an account?",
                    "answer": "To create an account:\n1. Click 'Sign Up' on our app or website\n2. Enter your email address and phone number\n3. Verify your email via the OTP sent\n4. Complete your profile information\n5. Set up your security PIN\n\nYour account will be created instantly and you can start using our services.",
                    "category": TicketCategory.ACCOUNT,
                    "order": 1,
                    "tags": ["registration", "signup", "new user"],
                },
                {
                    "question": "How do I reset my password?",
                    "answer": "To reset your password:\n1. Click 'Forgot Password' on the login screen\n2. Enter your registered email address\n3. Check your email for the password reset link\n4. Click the link and create a new password\n5. Confirm your new password\n\nYour password will be updated immediately. If you don't receive the email within 5 minutes, check your spam folder.",
                    "category": TicketCategory.ACCOUNT,
                    "order": 2,
                    "tags": ["password", "reset", "forgot password"],
                },
                {
                    "question": "How can I update my profile information?",
                    "answer": "To update your profile:\n1. Log in to your account\n2. Go to 'Settings' or 'Profile'\n3. Click 'Edit Profile'\n4. Update your information (name, phone, address, etc.)\n5. Click 'Save Changes'\n\nNote: Some changes like email or phone number may require verification.",
                    "category": TicketCategory.ACCOUNT,
                    "order": 3,
                    "tags": ["profile", "edit", "update information"],
                },
                {
                    "question": "How do I delete my account?",
                    "answer": "To delete your account:\n1. Go to Settings > Account Settings\n2. Scroll down to 'Delete Account'\n3. Read the information about account deletion\n4. Click 'Delete My Account'\n5. Confirm by entering your password\n\nIMPORTANT:\n• This action is permanent and cannot be undone\n• Withdraw all funds before deleting your account\n• Close all active loans and investments\n• Download your transaction history if needed\n\nAlternatively, contact our support team for assistance.",
                    "category": TicketCategory.ACCOUNT,
                    "order": 4,
                    "tags": ["delete account", "close account", "deactivate"],
                },
            ]
        )

        # ============ WALLET & BALANCE FAQS ============
        faqs.extend(
            [
                {
                    "question": "How do I add money to my wallet?",
                    "answer": "You can add money to your wallet using several methods:\n\n1. Bank Transfer:\n   • Go to 'Add Money' in your wallet\n   • Select 'Bank Transfer'\n   • Choose your payment method\n   • Enter amount and confirm\n   • Complete payment through your bank\n\n2. Card Payment:\n   • Select 'Add Money'\n   • Choose 'Card Payment'\n   • Enter card details or use saved card\n   • Enter amount and confirm\n\n3. Mobile Money (where available):\n   • Select 'Mobile Money'\n   • Choose your provider\n   • Follow the prompts\n\nFunds are usually credited within minutes.",
                    "category": TicketCategory.WALLET,
                    "order": 1,
                    "tags": ["deposit", "add money", "fund wallet", "top up"],
                },
                {
                    "question": "How long does it take for deposits to reflect?",
                    "answer": "Deposit times vary by payment method:\n\n• Bank Transfer: 5-30 minutes\n• Card Payment: Instant to 5 minutes\n• Mobile Money: Instant to 10 minutes\n• USSD: 5-15 minutes\n\nIf your deposit hasn't reflected after the expected time:\n1. Check your payment confirmation\n2. Verify the transaction was successful with your bank\n3. Contact support with your transaction reference\n\nNote: Deposits may take longer during weekends or public holidays.",
                    "category": TicketCategory.WALLET,
                    "order": 2,
                    "tags": ["deposit time", "pending deposit", "waiting"],
                },
                {
                    "question": "How do I withdraw money from my wallet?",
                    "answer": "To withdraw funds:\n1. Go to your wallet\n2. Click 'Withdraw'\n3. Select withdrawal method (Bank Transfer)\n4. Enter or select your bank account details\n5. Enter withdrawal amount\n6. Verify with your PIN\n7. Confirm withdrawal\n\nWithdrawal Processing Times:\n• Same bank: Instant to 1 hour\n• Other banks: 1-3 hours\n• Weekends/Holidays: Next business day\n\nMinimum withdrawal amount varies by currency. Check the app for current limits.",
                    "category": TicketCategory.WALLET,
                    "order": 3,
                    "tags": ["withdraw", "cash out", "bank transfer"],
                },
                {
                    "question": "What are the wallet transaction limits?",
                    "answer": "Transaction limits vary by account tier:\n\nTier 1 (Basic - Unverified):\n• Daily deposit: $1,000\n• Daily withdrawal: $500\n• Maximum balance: $5,000\n\nTier 2 (Verified - KYC Level 1):\n• Daily deposit: $10,000\n• Daily withdrawal: $5,000\n• Maximum balance: $50,000\n\nTier 3 (Premium - KYC Level 2):\n• Daily deposit: $50,000\n• Daily withdrawal: $25,000\n• Maximum balance: $250,000\n\nTo increase your limits, complete KYC verification in Settings > Verification.",
                    "category": TicketCategory.WALLET,
                    "order": 4,
                    "tags": ["limits", "maximum", "transaction limit"],
                },
                {
                    "question": "Can I have multiple wallets?",
                    "answer": "Yes! You can create multiple wallets for different purposes:\n\n• Main Wallet (default)\n• Savings Wallet\n• Business Wallet\n• Investment Wallet\n• Custom named wallets\n\nEach wallet can hold different currencies. To create a new wallet:\n1. Go to 'Wallets'\n2. Click 'Create New Wallet'\n3. Choose wallet type and currency\n4. Name your wallet\n5. Set optional PIN protection\n\nYou can transfer money between your wallets instantly and for free.",
                    "category": TicketCategory.WALLET,
                    "order": 5,
                    "tags": ["multiple wallets", "create wallet", "new wallet"],
                },
            ]
        )

        # ============ TRANSACTION FAQS ============
        faqs.extend(
            [
                {
                    "question": "How can I track my transaction history?",
                    "answer": "To view your transaction history:\n1. Go to 'Transactions' or 'Activity'\n2. Use filters to narrow down:\n   • Date range\n   • Transaction type (deposit, withdrawal, transfer)\n   • Status (completed, pending, failed)\n   • Amount range\n3. Click on any transaction to see full details\n4. Export your history to PDF or CSV if needed\n\nTransaction details include:\n• Transaction reference number\n• Date and time\n• Amount and fees\n• Status\n• Recipient/sender information\n• Balance before and after",
                    "category": TicketCategory.TRANSACTION,
                    "order": 1,
                    "tags": ["history", "transactions", "statement"],
                },
                {
                    "question": "What should I do if a transaction failed?",
                    "answer": "If a transaction failed:\n\n1. Check the failure reason in transaction details\n2. Common reasons and solutions:\n   • Insufficient balance: Add funds and retry\n   • Invalid account details: Verify recipient info\n   • Network error: Check internet and retry\n   • Daily limit exceeded: Wait 24 hours or upgrade tier\n   • Bank rejection: Contact your bank\n\n3. If money was debited:\n   • Wait 24-48 hours for automatic reversal\n   • Contact support if not reversed within 48 hours\n\n4. Keep your transaction reference for support inquiries.",
                    "category": TicketCategory.TRANSACTION,
                    "order": 2,
                    "tags": ["failed transaction", "error", "unsuccessful"],
                },
                {
                    "question": "How do I cancel a pending transaction?",
                    "answer": "Transaction cancellation depends on status:\n\nPending Transactions:\n• Most pending transactions cannot be manually canceled\n• They will auto-expire after 24 hours if not completed\n• Exception: Scheduled transactions can be canceled\n\nTo cancel a scheduled transaction:\n1. Go to 'Transactions'\n2. Filter by 'Scheduled'\n3. Select the transaction\n4. Click 'Cancel Transaction'\n5. Confirm cancellation\n\nCompleted Transactions:\n• Cannot be canceled\n• Must be reversed through dispute process\n• Contact support for assistance\n\nFor urgent matters, contact our support team immediately.",
                    "category": TicketCategory.TRANSACTION,
                    "order": 3,
                    "tags": ["cancel", "pending", "stop transaction"],
                },
                {
                    "question": "How do I dispute a transaction?",
                    "answer": "To dispute a transaction:\n\n1. Go to the transaction in your history\n2. Click 'Report Issue' or 'Dispute'\n3. Select dispute reason:\n   • Unauthorized transaction\n   • Wrong amount\n   • Service not received\n   • Duplicate charge\n   • Other\n4. Provide detailed explanation\n5. Upload supporting evidence (screenshots, receipts)\n6. Submit dispute\n\nDispute Process:\n• Acknowledgment: Immediate\n• Investigation: 5-10 business days\n• Resolution: 10-30 business days\n\nNote: Disputes must be filed within 30 days of the transaction date.",
                    "category": TicketCategory.TRANSACTION,
                    "order": 4,
                    "tags": ["dispute", "report", "unauthorized", "chargeback"],
                },
            ]
        )

        # ============ CARD SERVICES FAQS ============
        faqs.extend(
            [
                {
                    "question": "How do I request a virtual card?",
                    "answer": "To request a virtual debit/credit card:\n\n1. Go to 'Cards' section\n2. Click 'Request Virtual Card'\n3. Choose card type:\n   • Virtual Naira Card (NGN)\n   • Virtual Dollar Card (USD)\n4. Select funding wallet\n5. Set spending limits (optional)\n6. Confirm request\n\nYour virtual card will be created instantly and you'll receive:\n• Card number\n• CVV\n• Expiry date\n• Card nickname\n\nUse it immediately for online shopping and subscriptions worldwide.",
                    "category": TicketCategory.CARD,
                    "order": 1,
                    "tags": ["virtual card", "request card", "new card"],
                },
                {
                    "question": "How do I fund my card?",
                    "answer": "To fund your card:\n\n1. Go to 'Cards'\n2. Select the card you want to fund\n3. Click 'Fund Card'\n4. Choose funding source:\n   • From wallet balance\n   • Bank transfer\n   • Card payment\n5. Enter amount\n6. Confirm with PIN\n\nFunding is usually instant. The amount will be available on your card within seconds.\n\nTips:\n• Set up auto-funding for convenience\n• Fund before making purchases\n• Check daily/monthly limits",
                    "category": TicketCategory.CARD,
                    "order": 2,
                    "tags": ["fund card", "load card", "top up card"],
                },
                {
                    "question": "What do I do if my card is declined?",
                    "answer": "If your card transaction is declined:\n\n1. Check card balance:\n   • Ensure sufficient funds\n   • Add money if needed\n\n2. Verify card details:\n   • Correct card number\n   • Valid expiry date\n   • Correct CVV\n\n3. Check if card is active:\n   • Go to Cards section\n   • Ensure card status is 'Active'\n   • Unfreeze if frozen\n\n4. Common decline reasons:\n   • Insufficient balance\n   • Card frozen/blocked\n   • Merchant restrictions\n   • Daily limit exceeded\n   • Expired card\n   • 3D Secure authentication failed\n\n5. If issue persists:\n   • Try a different payment method\n   • Contact merchant support\n   • Reach out to our support team",
                    "category": TicketCategory.CARD,
                    "order": 3,
                    "tags": ["declined", "card failed", "transaction denied"],
                },
                {
                    "question": "How do I freeze or unfreeze my card?",
                    "answer": "To freeze/unfreeze your card:\n\n**Freeze Card:**\n1. Go to 'Cards'\n2. Select the card\n3. Click 'Freeze Card'\n4. Confirm action\n\nWhen frozen:\n• No transactions will be authorized\n• Card details remain the same\n• Existing balance is safe\n• Can be unfrozen anytime\n\n**Unfreeze Card:**\n1. Go to 'Cards'\n2. Select frozen card\n3. Click 'Unfreeze Card'\n4. Verify with PIN\n5. Card is immediately active\n\nUse freeze/unfreeze for:\n• Lost phone security\n• Suspicious activity\n• Temporary payment pause\n• Budget control",
                    "category": TicketCategory.CARD,
                    "order": 4,
                    "tags": ["freeze", "unfreeze", "lock card", "block"],
                },
            ]
        )

        # ============ KYC/VERIFICATION FAQS ============
        faqs.extend(
            [
                {
                    "question": "Why do I need to verify my account?",
                    "answer": "Account verification (KYC - Know Your Customer) is required for:\n\n**Regulatory Compliance:**\n• Legal requirement in most countries\n• Prevents fraud and money laundering\n• Protects all users\n\n**Increased Benefits:**\n• Higher transaction limits\n• Access to premium features\n• Loans and investments\n• Better exchange rates\n• Priority support\n\n**Account Security:**\n• Adds extra layer of protection\n• Easier account recovery\n• Fraud prevention\n\nVerification is quick, secure, and only done once.",
                    "category": TicketCategory.KYC,
                    "order": 1,
                    "tags": ["verification", "kyc", "identity"],
                },
                {
                    "question": "What documents do I need for KYC verification?",
                    "answer": "Documents needed vary by verification level:\n\n**Level 1 Verification (Basic):**\n• Valid government-issued ID:\n  - National ID Card\n  - International Passport\n  - Driver's License\n  - Voter's Card\n• Selfie photo\n\n**Level 2 Verification (Advanced):**\nAll Level 1 documents, plus:\n• Proof of address (issued within last 3 months):\n  - Utility bill (electricity, water, gas)\n  - Bank statement\n  - Rent agreement\n  - Government correspondence\n\n**For Business Accounts:**\n• Business registration certificate\n• Tax identification number\n• Company bank statement\n• Director's identification\n\nAll documents must be:\n• Clear and readable\n• Valid and not expired\n• In color (not black and white)\n• Full document visible",
                    "category": TicketCategory.KYC,
                    "order": 2,
                    "tags": ["documents", "id", "proof", "requirements"],
                },
                {
                    "question": "How long does verification take?",
                    "answer": "Verification times:\n\n**Instant Verification (Automated):**\n• ID verification: 2-5 minutes\n• Selfie matching: 1-2 minutes\n• Success rate: ~85%\n\n**Manual Review:**\n• If automated verification fails\n• Processing time: 24-48 hours\n• Working days only (Mon-Fri)\n• May require additional documents\n\n**Status Updates:**\n• Check verification status in Settings\n• Email notifications sent at each stage\n• Push notifications for approval/rejection\n\nTips for faster verification:\n• Upload clear, high-quality photos\n• Ensure all document edges are visible\n• Use good lighting\n• Documents should match your profile info\n• Avoid blurry or cropped images",
                    "category": TicketCategory.KYC,
                    "order": 3,
                    "tags": ["time", "duration", "how long", "waiting"],
                },
            ]
        )

        # ============ LOAN SERVICES FAQS ============
        faqs.extend(
            [
                {
                    "question": "How do I apply for a loan?",
                    "answer": "To apply for a loan:\n\n1. Ensure you're eligible:\n   • Verified account (KYC complete)\n   • Account age: minimum 30 days\n   • Good credit score\n   • Active transaction history\n\n2. Application process:\n   • Go to 'Loans' section\n   • Click 'Apply for Loan'\n   • Choose loan product\n   • Enter loan amount and duration\n   • Provide employment details\n   • Submit required documents\n   • Review loan terms\n   • Accept terms and submit\n\n3. Approval:\n   • Instant decision for qualified users\n   • Manual review: 24-48 hours\n   • Notification via email/SMS\n\n4. Disbursement:\n   • Funds sent to your wallet\n   • Usually within 1 hour of approval",
                    "category": TicketCategory.LOAN,
                    "order": 1,
                    "tags": ["apply", "loan application", "borrow"],
                },
                {
                    "question": "What is the loan interest rate?",
                    "answer": "Interest rates vary by loan type:\n\n**Payday Loans:**\n• Interest: 15-25% annually\n• Duration: 1-3 months\n• No collateral required\n\n**Personal Loans:**\n• Interest: 10-18% annually\n• Duration: 6-36 months\n• Requires guarantor\n\n**Business Loans:**\n• Interest: 12-20% annually\n• Duration: 12-60 months\n• Collateral required\n\n**Factors affecting your rate:**\n• Credit score (higher = lower rate)\n• Loan amount and duration\n• Employment status\n• Repayment history\n• Account activity\n\n**Additional fees:**\n• Processing fee: 1-2.5%\n• Late payment: Variable\n• Early repayment: 0-3%\n\nCheck specific rates in the loan application before accepting.",
                    "category": TicketCategory.LOAN,
                    "order": 2,
                    "tags": ["interest", "rate", "APR", "cost"],
                },
                {
                    "question": "How do I repay my loan?",
                    "answer": "Loan repayment options:\n\n**1. Automatic Deduction:**\n• Set up auto-repay from your wallet\n• Deducts on due date automatically\n• Recommended to avoid late fees\n• Set up in Loan Details\n\n**2. Manual Repayment:**\n• Go to 'Loans' > Active Loans\n• Select loan\n• Click 'Make Payment'\n• Enter amount (minimum or full)\n• Confirm with PIN\n\n**3. Lump Sum Payment:**\n• Pay off entire loan early\n• May attract early repayment fee\n• Saves on interest\n\n**Repayment Schedule:**\n• View all installments\n• See due dates\n• Track payment history\n• Download statements\n\n**Important:**\n• Pay before due date to avoid penalties\n• Late payment affects credit score\n• Contact us if facing payment difficulties",
                    "category": TicketCategory.LOAN,
                    "order": 3,
                    "tags": ["repayment", "pay loan", "installment"],
                },
            ]
        )

        # ============ SECURITY FAQS ============
        faqs.extend(
            [
                {
                    "question": "How do I keep my account secure?",
                    "answer": "Follow these security best practices:\n\n**Password Security:**\n• Use strong, unique password\n• Mix letters, numbers, symbols\n• Minimum 8 characters\n• Don't share with anyone\n• Change regularly\n\n**PIN Protection:**\n• Don't use obvious PINs (1234, 0000)\n• Don't share your PIN\n• Change if compromised\n\n**Two-Factor Authentication:**\n• Enable 2FA in Security Settings\n• Use authenticator app\n• Verify all login attempts\n\n**Device Security:**\n• Use biometric login (fingerprint/face)\n• Set screen lock\n• Don't root/jailbreak device\n• Keep app updated\n\n**General Tips:**\n• Beware of phishing emails/SMS\n• Don't click suspicious links\n• Verify URLs before entering details\n• Log out on shared devices\n• Monitor account regularly\n• Report suspicious activity immediately",
                    "category": TicketCategory.SECURITY,
                    "order": 1,
                    "tags": ["security", "safety", "protection", "2fa"],
                },
                {
                    "question": "What if I suspect unauthorized activity?",
                    "answer": "If you suspect unauthorized access:\n\n**Immediate Actions:**\n1. Change your password immediately\n2. Freeze all your cards\n3. Enable 2FA if not already enabled\n4. Log out from all devices\n\n**Review Activity:**\n5. Check transaction history\n6. Review login history\n7. Check for unknown devices\n8. Verify recipient lists\n\n**Report to Us:**\n9. Contact support immediately\n10. Provide transaction details\n11. File a dispute for unauthorized transactions\n12. Request account review\n\n**Prevention:**\n• Change PIN and security questions\n• Update email and phone if compromised\n• Enable all security features\n• Monitor account regularly\n\n**We Will:**\n• Investigate immediately\n• Freeze suspicious transactions\n• Refund proven unauthorized transactions\n• Enhance your account security",
                    "category": TicketCategory.SECURITY,
                    "order": 2,
                    "tags": ["unauthorized", "hacked", "fraud", "suspicious"],
                },
            ]
        )

        # ============ BILL PAYMENT FAQS ============
        faqs.extend(
            [
                {
                    "question": "How do I pay bills through the app?",
                    "answer": "To pay bills:\n\n1. Go to 'Bill Payments'\n2. Select bill category:\n   • Airtime\n   • Data bundles\n   • Electricity\n   • Cable TV\n   • Internet\n3. Choose provider (MTN, DSTV, EKEDC, etc.)\n4. Enter details:\n   • Phone number / Account number\n   • Amount or package\n5. Select payment wallet\n6. Review and confirm\n7. Verify with PIN\n\n**Benefits:**\n• Instant delivery\n• Payment history tracking\n• Save beneficiaries\n• Schedule recurring payments\n• Cashback on select bills\n\n**Supported Services:**\n✓ All major telcos\n✓ All electricity providers\n✓ Cable TV subscriptions\n✓ Internet services",
                    "category": TicketCategory.BILL_PAYMENT,
                    "order": 1,
                    "tags": ["bills", "airtime", "data", "electricity", "cable"],
                },
            ]
        )

        # ============ TECHNICAL ISSUES FAQS ============
        faqs.extend(
            [
                {
                    "question": "The app is not loading. What should I do?",
                    "answer": "Troubleshooting steps:\n\n**1. Check Internet Connection:**\n• Switch between WiFi and mobile data\n• Test other apps/websites\n• Restart router if using WiFi\n\n**2. Restart the App:**\n• Force close the app completely\n• Clear from recent apps\n• Reopen\n\n**3. Clear App Cache:**\n• Android: Settings > Apps > PayCore > Clear Cache\n• iOS: Uninstall and reinstall\n\n**4. Update the App:**\n• Check for updates in App Store/Play Store\n• Install latest version\n\n**5. Restart Device:**\n• Turn off phone\n• Wait 30 seconds\n• Turn on and try again\n\n**6. Reinstall App:**\n• Uninstall app\n• Download fresh copy\n• Log in again\n\n**Still Not Working?**\n• Check our status page for outages\n• Contact support with:\n  - Device model\n  - OS version\n  - App version\n  - Screenshots of error",
                    "category": TicketCategory.TECHNICAL,
                    "order": 1,
                    "tags": ["not loading", "app crash", "technical problem"],
                },
            ]
        )

        return faqs

    def _bulk_upsert_faqs(self, faqs_data):
        """Bulk create or update FAQs"""
        # Get existing FAQs by (question) - assuming questions are unique
        existing_faqs = {faq.question: faq for faq in FAQ.objects.all()}

        faqs_to_create = []
        faqs_to_update = []

        for data in faqs_data:
            question = data["question"]

            if question in existing_faqs:
                # Update existing FAQ
                existing_faq = existing_faqs[question]
                for field, value in data.items():
                    setattr(existing_faq, field, value)
                faqs_to_update.append(existing_faq)
                self.stdout.write(f"↻ Updated: {question[:60]}...")
            else:
                # Prepare for bulk creation
                faqs_to_create.append(FAQ(**data))

        # Bulk update existing FAQs
        if faqs_to_update:
            FAQ.objects.bulk_update(
                faqs_to_update,
                [
                    "answer",
                    "category",
                    "order",
                    "is_published",
                    "tags",
                ],
            )

        # Bulk create new FAQs
        if faqs_to_create:
            created = FAQ.objects.bulk_create(faqs_to_create, ignore_conflicts=True)
            for faq in created:
                self.stdout.write(f"✓ Created: {faq.question[:60]}...")
