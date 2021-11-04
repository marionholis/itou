from django.contrib import admin

from itou.common_apps.admin import admin as admin_common
from itou.external_data import models


@admin.register(models.ExternalDataImport)
class ExternalDataImportAdmin(admin_common.BaseAdmin):
    raw_id_fields = ("user",)
    list_display = ("pk", "source", "status", "created_at")
    list_filter = ("source", "status")


@admin.register(models.JobSeekerExternalData)
class JobSeekerExternalDataAdmin(admin_common.BaseAdmin):
    raw_id_fields = ("user",)
    list_display = ("pk", "data_import", "created_at")


@admin.register(models.RejectedEmailEventData)
class RejectedEmailEventDataAdmin(admin_common.BaseAdmin):
    list_filter = ("reason",)
    list_display = ("pk", "recipient", "reason", "created_at")
