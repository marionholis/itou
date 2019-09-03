from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from itou.utils.address.models import AddressMixin
from itou.utils.validators import validate_siret


class Prescriber(AddressMixin):  # Do not forget the mixin!
    """
    Prescripteurs-orienteurs (Pôle emploi, missions locales, Cap emploi, PJJ,
    SPIP, ASE, PLIE, voire structures d’hébergement, etc.).
    """

    siret = models.CharField(
        verbose_name=_("Siret"),
        max_length=14,
        validators=[validate_siret],
        primary_key=True,
    )
    name = models.CharField(verbose_name=_("Nom"), max_length=255, blank=True)
    phone = models.CharField(verbose_name=_("Téléphone"), max_length=10, blank=True)
    email = models.EmailField(verbose_name=_("E-mail"), blank=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Membres"),
        through="PrescriberMembership",
        blank=True,
    )

    class Meta:
        verbose_name = _("Structure d'accompagnement")
        verbose_name_plural = _("Structures d'accompagnement")

    def __str__(self):
        return f"{self.siret} {self.name}"

    @property
    def display_name(self):
        return self.name.title()


class PrescriberMembership(models.Model):
    """Intermediary model between `User` and `Prescriber`."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    prescriber = models.ForeignKey(Prescriber, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(
        verbose_name=_("Date d'adhésion"), default=timezone.now
    )
    is_prescriber_admin = models.BooleanField(
        verbose_name=_("Administrateur de la structure d'accompagnement"), default=False
    )
