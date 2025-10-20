from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from apps.audit_logs.services import AuditLogService
from apps.audit_logs.models import EventType, EventCategory, SeverityLevel

User = get_user_model()


# User Account Signals (Model-level changes not captured by middleware)


@receiver(post_save, sender=User)
def log_user_changes(sender, instance, created, **kwargs):
    """Log user account creation and updates"""
    if created:
        AuditLogService.log(
            event_type=EventType.ACCOUNT_CREATED,
            event_category=EventCategory.ACCOUNT,
            action=f"User account created: {instance.email}",
            user=instance,
            resource_type="User",
            resource_id=instance.id,
            is_compliance_event=True,
        )
    else:
        # Log significant account updates
        if instance.is_email_verified and not instance._state.adding:
            AuditLogService.log(
                event_type=EventType.EMAIL_VERIFIED,
                event_category=EventCategory.ACCOUNT,
                action=f"Email verified for user: {instance.email}",
                user=instance,
                resource_type="User",
                resource_id=instance.id,
                is_compliance_event=True,
            )


@receiver(pre_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """Log user account deletion"""
    AuditLogService.log(
        event_type=EventType.ACCOUNT_DELETED,
        event_category=EventCategory.ACCOUNT,
        action=f"User account deleted: {instance.email}",
        user=instance,
        resource_type="User",
        resource_id=instance.id,
        severity=SeverityLevel.WARNING,
        is_compliance_event=True,
    )
