from django.apps import AppConfig


class AuditLogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit_logs"

    def ready(self):
        """Import signals when app is ready"""
        import apps.audit_logs.signals
