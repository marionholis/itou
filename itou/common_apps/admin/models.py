from django.conf import settings
from django.db import models
from django.utils import timezone


class LoggingAdminHistoryAbstract(models.Model):
    """
    Base model for Siae, Prescriber Organization and Institution models.
    """

    historization_admin = models.TextField(verbose_name="Commentaires des admins", blank=True)

    class Meta:
        abstract = True
