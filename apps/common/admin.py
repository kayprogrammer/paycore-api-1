from django.contrib import admin
from django.utils.safestring import mark_safe

# Register your models here.

admin.site.site_header = mark_safe(
    '<strong style="font-weight:bold;">PAYCORE ADMIN</strong>'
)
