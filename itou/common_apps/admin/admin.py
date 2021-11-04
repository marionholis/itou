from django.contrib import admin

from itou.common_apps.admin.models import LoggingAdminHistoryAbstract


HISTORIZATION_ADMIN_FIELD = "historization_admin"


class BaseAdmin(admin.ModelAdmin):
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj and issubclass(obj.__class__, LoggingAdminHistoryAbstract):
            fieldsets_historization = (
                (
                    "Historique (admins)",
                    {
                        "fields": (HISTORIZATION_ADMIN_FIELD,),
                    },
                ),
            )
            fieldsets += fieldsets_historization
        return fieldsets

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj and "fields" in kwargs and issubclass(obj.__class__, LoggingAdminHistoryAbstract):
            kwargs["fields"] = kwargs["fields"] if kwargs["fields"] else []
            kwargs["fields"].append(HISTORIZATION_ADMIN_FIELD)
            return super().get_form(request, obj, change, **kwargs)
