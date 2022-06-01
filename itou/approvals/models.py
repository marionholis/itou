import datetime
import logging
import time

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeBoundary, RangeOperators
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from unidecode import unidecode

from itou.approvals import enums as approvals_enums
from itou.approvals.notifications import NewProlongationToAuthorizedPrescriberNotification
from itou.utils.models import DateRange
from itou.utils.urls import get_external_link_markup
from itou.utils.validators import alphanumeric


logger = logging.getLogger(__name__)


class CommonApprovalMixin(models.Model):
    """
    Abstract model for fields and methods common to both `Approval`
    and `PoleEmploiApproval` models.
    """

    # Default duration of an approval.
    DEFAULT_APPROVAL_YEARS = 2
    # `Période de carence` in French.
    # A period after expiry of an Approval during which a person cannot
    # obtain a new one except from an "authorized prescriber".
    WAITING_PERIOD_YEARS = 2

    start_at = models.DateField(verbose_name="Date de début", default=timezone.localdate, db_index=True)
    end_at = models.DateField(verbose_name="Date de fin", default=timezone.localdate, db_index=True)
    created_at = models.DateTimeField(verbose_name="Date de création", default=timezone.now)

    class Meta:
        abstract = True

    def is_valid(self, end_at=None):
        end_at = end_at or self.end_at
        now = timezone.now().date()
        return (self.start_at <= now <= end_at) or (self.start_at >= now)

    @property
    def is_in_progress(self):
        return self.start_at <= timezone.now().date() <= self.end_at

    @property
    def waiting_period_end(self):
        return self.end_at + relativedelta(years=self.WAITING_PERIOD_YEARS)

    @property
    def is_in_waiting_period(self):
        now = timezone.now().date()
        return self.end_at < now <= self.waiting_period_end

    @property
    def waiting_period_has_elapsed(self):
        now = timezone.now().date()
        return now > self.waiting_period_end

    @property
    def originates_from_itou(self):
        return self.number.startswith(Approval.ASP_ITOU_PREFIX)

    @property
    def is_pass_iae(self):
        """
        Returns True if the approval has been issued by Itou, False otherwise.
        """
        return isinstance(self, Approval)

    @property
    def duration(self):
        return self.end_at - self.start_at


class CommonApprovalQuerySet(models.QuerySet):
    """
    A QuerySet shared by both `Approval` and `PoleEmploiApproval` models.
    """

    @property
    def valid_lookup(self):
        now = timezone.now().date()
        return Q(start_at__lte=now, end_at__gte=now) | Q(start_at__gte=now)

    def valid(self):
        return self.filter(self.valid_lookup)

    def invalid(self):
        return self.exclude(self.valid_lookup)

    def starts_in_the_past(self):
        now = timezone.now().date()
        return self.filter(Q(start_at__lt=now))

    def starts_today(self):
        now = timezone.now().date()
        return self.filter(start_at=now)

    def starts_in_the_future(self):
        now = timezone.now().date()
        return self.filter(Q(start_at__gt=now))


class ApprovalAlreadyExistsError(Exception):
    pass


class PENotificationMixin(models.Model):
    pe_notification_status = models.CharField(
        verbose_name="Etat de la notification à PE",
        max_length=32,
        default=approvals_enums.PEApiNotificationStatus.PENDING,
        choices=approvals_enums.PEApiNotificationStatus.choices,
    )
    pe_notification_time = models.DateTimeField(verbose_name="Date de notification à PE", null=True, blank=True)
    pe_notification_endpoint = models.CharField(
        verbose_name="Dernier endpoint de l'API PE contacté",
        max_length=32,
        choices=approvals_enums.PEApiEndpoint.choices,
        blank=True,
        null=True,
    )
    pe_notification_exit_code = models.CharField(
        max_length=64,
        # remember that those choices are mostly for documentation purposes but do not
        # constrain the code to actually be among those, which is fortunate since
        # we don't want the app to break if PE suddenly adds a code.
        choices=list(approvals_enums.PEApiRechercheIndividuExitCode.choices)
        + list(approvals_enums.PEApiMiseAJourPassExitCode.choices),
        verbose_name="Dernier code de sortie constaté",
        blank=True,
        null=True,
    )

    class Meta:
        abstract = True

    def _pe_notification_update(self, status, at=None, endpoint=None, exit_code=None):
        """A helper method to update the fields of the mixin:
        - whatever the destination class (Approval, PoleEmploiApproval)
        - without triggering the model's save() method which usually is quite computation intensive

        This will become useless when we will stop managing the PoleEmploiApproval that much.
        """
        update_dict = {
            "pe_notification_status": status,
            "pe_notification_time": at if at else timezone.now(),
            "pe_notification_endpoint": endpoint,
            "pe_notification_exit_code": exit_code,
        }
        queryset = self.__class__.objects.filter(pk=self.pk)
        queryset.update(**{key: value for key, value in update_dict.items() if value})

    def pe_save_error(self, endpoint, exit_code, at=None):
        self._pe_notification_update(approvals_enums.PEApiNotificationStatus.ERROR, at, endpoint, exit_code)

    def pe_save_should_retry(self, at=None):
        self._pe_notification_update(approvals_enums.PEApiNotificationStatus.SHOULD_RETRY, at)

    def pe_save_success(self, at=None):
        self._pe_notification_update(approvals_enums.PEApiNotificationStatus.SUCCESS, at)


class Approval(PENotificationMixin, CommonApprovalMixin):
    """
    Store "PASS IAE" whose former name was "approval" ("agréments" in French)
    issued by Itou.

    A number starting with `ASP_ITOU_PREFIX` means it has been created by Itou.

    Otherwise, it was previously created by Pôle emploi (and initially found
    in `PoleEmploiApproval`) and re-issued by Itou as a PASS IAE.
    """

    # This prefix is used by the ASP system to identify itou as the issuer of a number.
    ASP_ITOU_PREFIX = settings.ASP_ITOU_PREFIX

    # The period of time during which it is possible to prolong a PASS IAE.
    IS_OPEN_TO_PROLONGATION_BOUNDARIES_MONTHS = 3

    # Error messages.
    ERROR_PASS_IAE_SUSPENDED_FOR_USER = (
        "Votre PASS IAE est suspendu. Vous ne pouvez pas postuler pendant la période de suspension."
    )
    ERROR_PASS_IAE_SUSPENDED_FOR_PROXY = (
        "Le PASS IAE du candidat est suspendu. Vous ne pouvez pas postuler "
        "pour lui pendant la période de suspension."
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Demandeur d'emploi",
        on_delete=models.CASCADE,
        related_name="approvals",
    )
    number = models.CharField(
        verbose_name="Numéro",
        max_length=12,
        help_text="12 caractères alphanumériques.",
        validators=[alphanumeric, MinLengthValidator(12)],
        unique=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Créé par", null=True, blank=True, on_delete=models.SET_NULL
    )

    objects = models.Manager.from_queryset(CommonApprovalQuerySet)()

    class Meta:
        verbose_name = "PASS IAE"
        verbose_name_plural = "PASS IAE"
        ordering = ["-created_at"]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        self.clean()
        if not self.number:
            # `get_next_number` will lock rows until the end of the transaction.
            self.number = self.get_next_number()
        super().save(*args, **kwargs)

    def clean(self):
        try:
            if self.end_at <= self.start_at:
                raise ValidationError("La date de fin doit être postérieure à la date de début.")
        except TypeError:
            # This can happen if `end_at` or `start_at` are empty or malformed
            # (e.g. when data comes from a form).
            pass
        already_exists = bool(self.pk)
        if not already_exists and hasattr(self, "user") and self.user.approvals.valid().exists():
            raise ValidationError(
                (
                    f"Un agrément dans le futur ou en cours de validité existe déjà "
                    f"pour {self.user.get_full_name()} ({self.user.email})."
                )
            )
        super().clean()

    @property
    def number_with_spaces(self):
        """
        Insert spaces to format the number.
        """
        return f"{self.number[:5]} {self.number[5:7]} {self.number[7:]}"

    @cached_property
    def can_be_deleted(self):
        state_accepted = self.jobapplication_set.model.state.STATE_ACCEPTED

        job_applications = self.jobapplication_set
        if job_applications.count() != 1:
            return False
        return self.jobapplication_set.get().state == state_accepted

    @cached_property
    def is_last_for_user(self):
        """
        Returns True if the current Approval is the most recent for the user, False otherwise.
        """
        return self == self.user.approvals.order_by("start_at").last()

    # Suspension.

    @cached_property
    def is_suspended(self):
        return self.suspension_set.in_progress().exists()

    @cached_property
    def suspensions_by_start_date_asc(self):
        return self.suspension_set.all().order_by("start_at")

    def last_old_suspension(self, exclude_pk=None):
        return self.suspensions_by_start_date_asc.exclude(pk=exclude_pk).old().last()

    @cached_property
    def can_be_suspended(self):
        return self.is_in_progress and not self.is_suspended

    @property
    def is_from_ai_stock(self):
        """On November 30th, 2021, AI were delivered approvals without a diagnosis.
        See itou.users.management.commands.import_ai_employees.
        """
        # Avoid a circular import.
        user_manager = self.user._meta.model.objects
        developer_qs = user_manager.filter(email=settings.AI_EMPLOYEES_STOCK_DEVELOPER_EMAIL)
        if not developer_qs:
            return False
        developer = developer_qs.first()
        return (
            self.created_by == developer and self.created_at.date() == settings.AI_EMPLOYEES_STOCK_IMPORT_DATE.date()
        )

    def can_be_suspended_by_siae(self, siae):
        # Only the SIAE currently hiring the job seeker can suspend a PASS IAE.
        return self.can_be_suspended and self.user.last_hire_was_made_by_siae(siae)

    @cached_property
    def last_in_progress_suspension(self):
        return self.suspension_set.in_progress().order_by("start_at").last()

    @cached_property
    def can_be_unsuspended(self):
        if self.is_suspended:
            return self.last_in_progress_suspension.reason in Suspension.REASONS_TO_UNSUSPEND
        return False

    def unsuspend(self, hiring_start_at):
        """
        When a job application is accepted, the approval is "unsuspended":
        we do it by setting its end_date to JobApplication.hiring_start_at - 1 day.
        """
        active_suspension = self.last_in_progress_suspension
        if active_suspension and self.can_be_unsuspended:
            active_suspension.end_at = hiring_start_at - relativedelta(days=1)
            active_suspension.save()

    # Postpone start date.

    @property
    def can_postpone_start_date(self):
        return self.start_at > timezone.now().date()

    def update_start_date(self, new_start_date):
        """
        An SIAE can postpone the start date of a job application if the contract has not begun yet.
        In this case, the approval start date must be updated with the start date of the hiring.

        Returns True if date has been updated, False otherwise
        """
        # Only approvals which are not started yet can be postponed.
        if self.can_postpone_start_date:
            self.start_at = new_start_date
            # At first, we computed the end date applying a delay like this:
            # delay = new_start_date - self.start_at
            # self.end_at = self.end_at + delay
            # But this is error-prone on leap years!
            # Instead, set the default end date.
            self.end_at = self.get_default_end_date(new_start_date)
            self.save()
            return True
        return False

    # Prolongation.

    @cached_property
    def prolongations_by_start_date_asc(self):
        return self.prolongation_set.all().select_related("validated_by").order_by("start_at")

    @property
    def is_open_to_prolongation(self):
        now = timezone.now().date()
        lower_bound = self.end_at - relativedelta(months=self.IS_OPEN_TO_PROLONGATION_BOUNDARIES_MONTHS)
        upper_bound = self.end_at + relativedelta(months=self.IS_OPEN_TO_PROLONGATION_BOUNDARIES_MONTHS)
        return lower_bound <= now <= upper_bound

    @cached_property
    def can_be_prolonged(self):
        # Since it is possible to prolong even 3 months after the end of a PASS IAE,
        # it is possible that another one has been issued in the meantime. Thus we
        # have to ensure that the current PASS IAE is the most recent for the user
        # before allowing a prolongation.
        return self.is_last_for_user and self.is_open_to_prolongation and not self.is_suspended

    def can_be_prolonged_by_siae(self, siae):
        return self.user.last_hire_was_made_by_siae(siae) and self.can_be_prolonged

    @staticmethod
    def get_next_number():
        """
        Find next "PASS IAE" number.

        Numbering scheme for a 12 chars "PASS IAE" number:
            - ASP_ITOU_PREFIX (5 chars) + NUMBER (7 chars)

        Old numbering scheme for PASS IAE <= `99999.21.35866`:
            - ASP_ITOU_PREFIX (5 chars) + YEAR WITHOUT CENTURY (2 chars) + NUMBER (5 chars)
            - YEAR WITHOUT CENTURY is equal to the start year of the `JobApplication.hiring_start_at`
            - A max of 99999 approvals could be issued by year
            - We would have gone beyond, we would never have thought we could go that far
        """
        # Lock the table's first row until the end of the transaction, effectively acting as a
        # poor man's semaphore.
        Approval.objects.order_by("pk").select_for_update().first()
        # Now we can do a whole new SELECT that will take into account eventual new rows.
        last_itou_approval = (
            Approval.objects.filter(number__startswith=Approval.ASP_ITOU_PREFIX).order_by("number").last()
        )
        if last_itou_approval:
            raw_number = last_itou_approval.number.removeprefix(Approval.ASP_ITOU_PREFIX)
            next_number = int(raw_number) + 1
            if next_number > 9999999:
                raise RuntimeError("The maximum number of PASS IAE has been reached.")
            return f"{Approval.ASP_ITOU_PREFIX}{next_number:07d}"
        return f"{Approval.ASP_ITOU_PREFIX}0000001"

    @staticmethod
    def get_default_end_date(start_at):
        return start_at + relativedelta(years=Approval.DEFAULT_APPROVAL_YEARS) - relativedelta(days=1)

    @classmethod
    def get_or_create_from_valid(cls, approvals_wrapper):
        """
        Returns an existing valid Approval or create a new entry from
        a pre-existing valid PoleEmploiApproval by copying its data.
        """
        approval = approvals_wrapper.latest_approval
        if not approval.is_valid() or not isinstance(approval, (cls, PoleEmploiApproval)):
            raise RuntimeError("Invalid approval.")
        if isinstance(approval, cls):
            return approval
        if Approval.objects.filter(number=approval.number).exists():
            raise ApprovalAlreadyExistsError()
        approval_from_pe = cls(
            start_at=approval.start_at,
            end_at=approval.end_at,
            user=approvals_wrapper.user,
            number=approval.number,
        )
        approval_from_pe.save()
        return approval_from_pe


class SuspensionQuerySet(models.QuerySet):
    @property
    def in_progress_lookup(self):
        now = timezone.now().date()
        return models.Q(start_at__lte=now, end_at__gte=now)

    def in_progress(self):
        return self.filter(self.in_progress_lookup)

    def not_in_progress(self):
        return self.exclude(self.in_progress_lookup)

    def old(self):
        now = timezone.now().date()
        return self.filter(end_at__lt=now)


class Suspension(models.Model):
    """
    A PASS IAE (or approval) issued by Itou can be directly suspended by an SIAE,
    without intervention of a prescriber or a posteriori control.

    When a suspension is saved/edited/deleted, the end date of its approval is
    automatically pushed back or forth with a PostgreSQL trigger:
    `trigger_update_approval_end_at`.
    """

    # Min duration: none.
    # Max duration: 12 months (could be adjusted according to user feedback).
    # 12-months suspensions can be consecutive and there can be any number of them.
    MAX_DURATION_MONTHS = 12
    # Temporary update for support team needs. operated on march. Target value should be 30.
    # More information on https://github.com/betagouv/itou/pull/1163
    MAX_RETROACTIVITY_DURATION_DAYS = 365

    class Reason(models.TextChoices):
        # Displayed choices
        SUSPENDED_CONTRACT = "CONTRACT_SUSPENDED", "Contrat de travail suspendu depuis plus de 15 jours"
        BROKEN_CONTRACT = "CONTRACT_BROKEN", "Contrat de travail rompu"
        FINISHED_CONTRACT = "FINISHED_CONTRACT", "Contrat de travail terminé"
        APPROVAL_BETWEEN_CTA_MEMBERS = (
            "APPROVAL_BETWEEN_CTA_MEMBERS",
            "Situation faisant l'objet d'un accord entre les acteurs membres du CTA (Comité technique d'animation)",
        )
        # The following choice must only be available for EI and ACI SIAE kinds
        CONTRAT_PASSERELLE = (
            "CONTRAT_PASSERELLE",
            "Bascule dans l'expérimentation contrat passerelle",
        )

        # Old reasons kept for history. See cls.displayed_choices
        SICKNESS = "SICKNESS", "Arrêt pour longue maladie"
        MATERNITY = "MATERNITY", "Congé de maternité"
        INCARCERATION = "INCARCERATION", "Incarcération"
        TRIAL_OUTSIDE_IAE = (
            "TRIAL_OUTSIDE_IAE",
            "Période d'essai auprès d'un employeur ne relevant pas de l'insertion par l'activité économique",
        )
        DETOXIFICATION = "DETOXIFICATION", "Période de cure pour désintoxication"
        FORCE_MAJEURE = (
            "FORCE_MAJEURE",
            (
                "Raison de force majeure conduisant le salarié à quitter son emploi ou toute autre "
                "situation faisant l'objet d'un accord entre les acteurs membres du CTA"
            ),
        )

        @staticmethod
        def displayed_choices_for_siae(siae):
            """
            Old reasons are not showed anymore but kept to let users still see
            a nice label in their dashboard instead of just the enum stored in the DB.
            If the given SIAE is an ACI or EI, it can now use the 'CONTRAT_PASSERELLE' suspension reason.
            """
            reasons = [
                Suspension.Reason.SUSPENDED_CONTRACT,
                Suspension.Reason.BROKEN_CONTRACT,
                Suspension.Reason.FINISHED_CONTRACT,
                Suspension.Reason.APPROVAL_BETWEEN_CTA_MEMBERS,
            ]
            if siae.kind in [siae.KIND_ACI, siae.KIND_EI]:
                reasons.append(Suspension.Reason.CONTRAT_PASSERELLE)
            return [(reason.value, reason.label) for reason in reasons]

    REASONS_TO_UNSUSPEND = [
        Reason.BROKEN_CONTRACT.value,
        Reason.FINISHED_CONTRACT.value,
        Reason.APPROVAL_BETWEEN_CTA_MEMBERS.value,
        Reason.CONTRAT_PASSERELLE.value,
    ]

    approval = models.ForeignKey(Approval, verbose_name="PASS IAE", on_delete=models.CASCADE)
    start_at = models.DateField(verbose_name="Date de début", default=timezone.localdate, db_index=True)
    end_at = models.DateField(verbose_name="Date de fin", default=timezone.localdate, db_index=True)
    siae = models.ForeignKey(
        "siaes.Siae",
        verbose_name="SIAE",
        null=True,
        on_delete=models.SET_NULL,
        related_name="approvals_suspended",
    )
    reason = models.CharField(
        verbose_name="Motif", max_length=30, choices=Reason.choices, default=Reason.SUSPENDED_CONTRACT
    )
    reason_explanation = models.TextField(verbose_name="Explications supplémentaires", blank=True)
    created_at = models.DateTimeField(verbose_name="Date de création", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        null=True,
        on_delete=models.SET_NULL,
        related_name="approvals_suspended_set",
    )
    updated_at = models.DateTimeField(verbose_name="Date de modification", blank=True, null=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Mis à jour par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    objects = models.Manager.from_queryset(SuspensionQuerySet)()

    class Meta:
        verbose_name = "Suspension"
        verbose_name_plural = "Suspensions"
        ordering = ["-start_at"]
        # Use an exclusion constraint to prevent overlapping date ranges.
        # This requires the btree_gist extension on PostgreSQL.
        # See "Tip of the Week" https://postgresweekly.com/issues/289
        # https://docs.djangoproject.com/en/3.1/ref/contrib/postgres/constraints/
        constraints = [
            ExclusionConstraint(
                name="exclude_overlapping_suspensions",
                expressions=(
                    (
                        DateRange("start_at", "end_at", RangeBoundary(inclusive_lower=True, inclusive_upper=True)),
                        RangeOperators.OVERLAPS,
                    ),
                    ("approval", RangeOperators.EQUAL),
                ),
            ),
        ]

    def __str__(self):
        return f"{self.pk} {self.start_at.strftime('%d/%m/%Y')} - {self.end_at.strftime('%d/%m/%Y')}"

    def save(self, *args, **kwargs):
        """
        The related Approval's end date is automatically pushed back/forth
        with a PostgreSQL trigger: `trigger_update_approval_end_at`.
        """
        if self.pk:
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def clean(self):
        if self.reason == self.Reason.FORCE_MAJEURE and not self.reason_explanation:
            raise ValidationError({"reason_explanation": "En cas de force majeure, veuillez préciser le motif."})

        # This can happen in forms when no default/end date is entered
        if not self.end_at:
            raise ValidationError({"end_at": "La date de fin de la suspension est obligatoire."})

        # No min duration: a suspension may last only 1 day.
        if self.end_at < self.start_at:
            raise ValidationError({"end_at": "La date de fin doit être postérieure à la date de début."})

        # A suspension cannot be in the future.
        if self.start_in_future:
            raise ValidationError({"start_at": "La suspension ne peut pas commencer dans le futur."})

        # A suspension cannot exceed max duration.
        max_end_at = self.get_max_end_at(self.start_at)
        if self.end_at > max_end_at:
            raise ValidationError(
                {
                    "end_at": (
                        f"La durée totale ne peut excéder {self.MAX_DURATION_MONTHS} mois. "
                        f"Date de fin maximum: {max_end_at.strftime('%d/%m/%Y')}."
                    )
                }
            )

        if hasattr(self, "approval"):
            # The start of a suspension must be contained in its approval boundaries.
            if not self.start_in_approval_boundaries:
                raise ValidationError(
                    {
                        "start_at": (
                            f"La suspension ne peut pas commencer en dehors des limites du PASS IAE "
                            f"{self.approval.start_at.strftime('%d/%m/%Y')} - "
                            f"{self.approval.end_at.strftime('%d/%m/%Y')}."
                        )
                    }
                )

            referent_date = self.created_at.date() if self.pk else None
            next_min_start_at = self.next_min_start_at(self.approval, self.pk, referent_date, False)
            if next_min_start_at and self.start_at < next_min_start_at:
                raise ValidationError(
                    {"start_at": (f"La date de début minimum est : {next_min_start_at.strftime('%d/%m/%Y')}.")}
                )

            # A suspension cannot overlap another one for the same SIAE.
            # This check is enforced by a constraint at the database level but
            # still required here to avoid a 500 server error "IntegrityError"
            # during form validation.
            if self.get_overlapping_suspensions().exists():
                overlap = self.get_overlapping_suspensions().first()
                raise ValidationError(
                    {
                        "start_at": (
                            f"La période chevauche une suspension déjà existante pour ce PASS IAE "
                            f"{overlap.start_at.strftime('%d/%m/%Y')} - {overlap.end_at.strftime('%d/%m/%Y')}."
                        )
                    }
                )

    @property
    def duration(self):
        return self.end_at - self.start_at

    @property
    def is_in_progress(self):
        return self.start_at <= timezone.now().date() <= self.end_at

    @property
    def start_in_future(self):
        return self.start_at > timezone.now().date()

    @property
    def start_in_approval_boundaries(self):
        return self.approval.start_at <= self.start_at <= self.approval.end_at

    def get_overlapping_suspensions(self):
        args = {
            "end_at__gte": self.start_at,
            "start_at__lte": self.end_at,
            "approval": self.approval,
        }
        return self._meta.model.objects.exclude(pk=self.pk).filter(**args)

    def can_be_handled_by_siae(self, siae):
        """
        Only the SIAE currently hiring the job seeker can handle a suspension.
        """
        cached_result = getattr(self, "_can_be_handled_by_siae_cache", None)
        if cached_result:
            return cached_result
        self._can_be_handled_by_siae_cache = self.is_in_progress and self.approval.user.last_hire_was_made_by_siae(
            siae
        )
        return self._can_be_handled_by_siae_cache

    @staticmethod
    def get_max_end_at(start_at):
        """
        Returns the maximum date on which a suspension can end.
        """
        return start_at + relativedelta(months=Suspension.MAX_DURATION_MONTHS) - relativedelta(days=1)

    @staticmethod
    def next_min_start_at(approval, pk_suspension=None, referent_date=None, with_retroactivity_limitation=True):
        """
        Returns the minimum date on which a suspension can begin.
        """
        if referent_date is None:
            referent_date = datetime.date.today()

        # Default starting date. Can be empty, see below.
        start_at = approval.user.last_accepted_job_application.hiring_start_at

        # Start at overrides to handle edge cases.
        if approval.last_old_suspension(pk_suspension):
            start_at = approval.last_old_suspension(pk_suspension).end_at + relativedelta(days=1)

        if with_retroactivity_limitation:
            start_at_threshold = referent_date - datetime.timedelta(days=Suspension.MAX_RETROACTIVITY_DURATION_DAYS)
            # At this point, `start_at` can be undefined if:
            # - hiring start date has not been filled in last accepted job application,
            # - there is no previous suspension for this approval.
            # Hence a more defensive approach.
            if not start_at or start_at < start_at_threshold:
                return start_at_threshold

        # FIXME: at this point start_at can still be undefined if `with_retroactivity_limitation` is `False`
        return start_at


class ProlongationQuerySet(models.QuerySet):
    @property
    def in_progress_lookup(self):
        now = timezone.now().date()
        return models.Q(start_at__lte=now, end_at__gte=now)

    def in_progress(self):
        return self.filter(self.in_progress_lookup)

    def not_in_progress(self):
        return self.exclude(self.in_progress_lookup)


class ProlongationManager(models.Manager):
    def get_cumulative_duration_for(self, approval, reason=None):
        """
        Returns the total duration of all prolongations of the given approval
        for the given reason (if any).
        """
        kwargs = {"approval": approval}
        if reason:
            kwargs["reason"] = reason
        duration = datetime.timedelta(0)
        for prolongation in self.filter(**kwargs):
            duration += prolongation.duration
        return duration


class Prolongation(models.Model):
    """
    Stores a prolongation made by an SIAE for a PASS IAE.

    It is assumed that an authorized prescriber has validated the prolongation
    beforehand because a self-validated prolongation made by an SIAE would
    increase the risk of staying on insertion for a candidate.

    When a prolongation is saved/edited/deleted, the end date of its approval
    is automatically pushed back or forth with a PostgreSQL trigger:
    `trigger_update_approval_end_at_for_prolongation`.
    """

    # Max duration: 10 years but it depends on the `reason` field, see `get_max_end_at`.
    # The addition of 0.25 day per year makes it possible to better manage leap years.
    MAX_DURATION = datetime.timedelta(days=365.25 * 10)

    class Reason(models.TextChoices):
        SENIOR_CDI = "SENIOR_CDI", "CDI conclu avec une personne de plus de 57 ans"
        COMPLETE_TRAINING = "COMPLETE_TRAINING", "Fin d'une formation"
        RQTH = "RQTH", "RQTH"
        SENIOR = "SENIOR", "50 ans et plus"
        PARTICULAR_DIFFICULTIES = (
            "PARTICULAR_DIFFICULTIES",
            "Difficultés particulières qui font obstacle à l'insertion durable dans l’emploi",
        )
        HEALTH_CONTEXT = "HEALTH_CONTEXT", "Contexte sanitaire"

    MAX_CUMULATIVE_DURATION = {
        Reason.SENIOR_CDI.value: {
            "duration": datetime.timedelta(days=365.25 * 10),  # 10 years
            "label": "10 ans",
        },
        Reason.COMPLETE_TRAINING.value: {
            "duration": datetime.timedelta(days=365.25 * 2),  # 2 years
            "label": "2 ans",
        },
        Reason.RQTH.value: {
            "duration": datetime.timedelta(days=365.25 * 3),  # 3 years
            "label": "3 ans",
        },
        Reason.SENIOR.value: {
            "duration": datetime.timedelta(days=365.25 * 5),  # 5 years
            "label": "5 ans",
        },
        Reason.PARTICULAR_DIFFICULTIES.value: {
            "duration": datetime.timedelta(days=365.25 * 3),  # 3 years
            "label": "12 mois, reconductibles dans la limite de 5 ans de parcours",
        },
        Reason.HEALTH_CONTEXT.value: {
            "duration": datetime.timedelta(days=365),  # one year
            "label": "12 mois",
        },
    }

    REASONS_NOT_NEED_PRESCRIBER_OPINION = (
        Reason.SENIOR_CDI,
        Reason.COMPLETE_TRAINING,
    )

    approval = models.ForeignKey(Approval, verbose_name="PASS IAE", on_delete=models.CASCADE)
    start_at = models.DateField(verbose_name="Date de début", default=timezone.localdate, db_index=True)
    end_at = models.DateField(verbose_name="Date de fin", default=timezone.localdate, db_index=True)
    reason = models.CharField(
        verbose_name="Motif", max_length=30, choices=Reason.choices, default=Reason.COMPLETE_TRAINING
    )
    reason_explanation = models.TextField(verbose_name="Explications supplémentaires", blank=True)

    declared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Déclarée par",
        null=True,
        on_delete=models.SET_NULL,
        related_name="approvals_prolongation_declared_set",
    )
    declared_by_siae = models.ForeignKey(
        "siaes.Siae",
        verbose_name="SIAE du déclarant",
        null=True,
        on_delete=models.SET_NULL,
    )

    # It is assumed that an authorized prescriber has validated the prolongation beforehand.
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Prescripteur habilité qui a autorisé cette prolongation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approvals_prolongations_validated_set",
    )

    # `created_at` can be different from `validated_by` when created in admin.
    created_at = models.DateTimeField(verbose_name="Date de création", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        null=True,
        on_delete=models.SET_NULL,
        related_name="approvals_prolongations_created_set",
    )
    updated_at = models.DateTimeField(verbose_name="Date de modification", blank=True, null=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Mis à jour par",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    objects = ProlongationManager.from_queryset(ProlongationQuerySet)()

    class Meta:
        verbose_name = "Prolongation"
        verbose_name_plural = "Prolongations"
        ordering = ["-start_at"]
        # Use an exclusion constraint to prevent overlapping date ranges.
        # This requires the btree_gist extension on PostgreSQL.
        # See "Tip of the Week" https://postgresweekly.com/issues/289
        # https://docs.djangoproject.com/en/3.1/ref/contrib/postgres/constraints/
        constraints = [
            ExclusionConstraint(
                name="exclude_overlapping_prolongations",
                expressions=(
                    (
                        # [start_at, end_at) (inclusive start, exclusive end).
                        # For prolongations: upper bound of preceding interval is the lower bound of the next.
                        DateRange("start_at", "end_at", RangeBoundary(inclusive_lower=True, inclusive_upper=False)),
                        RangeOperators.OVERLAPS,
                    ),
                    ("approval", RangeOperators.EQUAL),
                ),
            ),
        ]

    def __str__(self):
        return f"{self.pk} {self.start_at.strftime('%d/%m/%Y')} - {self.end_at.strftime('%d/%m/%Y')}"

    def save(self, *args, **kwargs):
        """
        The related Approval's end date is automatically pushed back/forth with
        a PostgreSQL trigger: `trigger_update_approval_end_at_for_prolongation`.
        """
        if self.pk:
            self.updated_at = timezone.now()
        else:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    def clean(self):

        # Min duration == 1 day.
        if self.end_at <= self.start_at:
            raise ValidationError({"end_at": "La durée minimale doit être d'au moins un jour."})

        # A prolongation cannot exceed max duration.
        max_end_at = self.get_max_end_at(self.start_at, self.reason)
        if self.end_at > max_end_at:
            raise ValidationError(
                {
                    "end_at": (
                        f"La durée totale est trop longue pour le motif « {self.get_reason_display()} ». "
                        f"Date de fin maximum : {max_end_at.strftime('%d/%m/%Y')}."
                    )
                }
            )

        if self.reason == self.Reason.PARTICULAR_DIFFICULTIES.value:
            if not self.declared_by_siae or self.declared_by_siae.kind not in [
                self.declared_by_siae.KIND_AI,
                self.declared_by_siae.KIND_ACI,
                self.declared_by_siae.KIND_ACIPHC,
            ]:
                raise ValidationError(f"Le motif « {self.get_reason_display()} » est réservé aux AI et ACI.")

        if (
            hasattr(self, "validated_by")
            and self.validated_by
            and not self.validated_by.is_prescriber_with_authorized_org
        ):
            raise ValidationError("Cet utilisateur n'est pas un prescripteur habilité.")

        if hasattr(self, "approval"):

            # Avoid blocking updates in admin by limiting this check to only new instances.
            if not self.pk and self.start_at != self.get_start_at(self.approval):
                raise ValidationError(
                    "La date de début doit être la même que la date de fin du PASS IAE "
                    f"« {self.approval.end_at.strftime('%d/%m/%Y')} »."
                )

            # A prolongation cannot overlap another one for the same SIAE.
            # This check is enforced by a constraint at the database level but
            # still required here to avoid a 500 server error "IntegrityError"
            # during form validation.
            if self.get_overlapping_prolongations().exists():
                overlap = self.get_overlapping_prolongations().first()
                raise ValidationError(
                    (
                        f"La période chevauche une prolongation déjà existante pour ce PASS IAE "
                        f"{overlap.start_at.strftime('%d/%m/%Y')} - {overlap.end_at.strftime('%d/%m/%Y')}."
                    )
                )

            if self.has_reached_max_cumulative_duration(additional_duration=self.duration):
                raise ValidationError(
                    (
                        f"Vous ne pouvez pas cumuler des prolongations pendant plus de "
                        f'{self.MAX_CUMULATIVE_DURATION[self.reason]["label"]} '
                        f'pour le motif "{self.get_reason_display()}".'
                    )
                )

    @property
    def duration(self):
        return self.end_at - self.start_at

    @property
    def is_in_progress(self):
        return self.start_at <= timezone.now().date() <= self.end_at

    def notify_authorized_prescriber(self):
        NewProlongationToAuthorizedPrescriberNotification(self).send()

    def has_reached_max_cumulative_duration(self, additional_duration=None):
        if self.reason not in [self.Reason.COMPLETE_TRAINING.value, self.Reason.PARTICULAR_DIFFICULTIES.value]:
            return False

        cumulative_duration = Prolongation.objects.get_cumulative_duration_for(self.approval, reason=self.reason)
        if additional_duration:
            cumulative_duration += additional_duration

        return cumulative_duration > self.MAX_CUMULATIVE_DURATION[self.reason]["duration"]

    def get_overlapping_prolongations(self):
        filter_args = {
            "start_at__lte": self.end_at,  # Inclusive start.
            "end_at__gt": self.start_at,  # Exclusive end.
            "approval": self.approval,
        }
        return self._meta.model.objects.exclude(pk=self.pk).filter(**filter_args)

    @staticmethod
    def get_start_at(approval):
        """
        Returns the start date of the prolongation.
        """
        return approval.end_at

    @staticmethod
    def get_max_end_at(start_at, reason=None):
        """
        Returns the maximum date on which a prolongation can end.
        """
        max_duration = Prolongation.MAX_DURATION
        if reason == Prolongation.Reason.PARTICULAR_DIFFICULTIES.value:
            # 12 months renewable up to 3 years for this reason
            max_duration = relativedelta(months=12)
        elif reason in Prolongation.MAX_CUMULATIVE_DURATION:
            max_duration = Prolongation.MAX_CUMULATIVE_DURATION[reason]["duration"]
        return start_at + max_duration - relativedelta(days=1)


class PoleEmploiApprovalManager(models.Manager):
    def get_import_dates(self):
        """
        Return a list of import dates.
        [
            datetime.date(2020, 2, 23),
            datetime.date(2020, 4, 8),
            …
        ]

        It used to be used in the admin but it slowed it down.
        It's still used from time to time in django-admin shell.
        """
        return list(
            self
            # Remove default `Meta.ordering` to avoid an extra field being added to the GROUP BY clause.
            .order_by()
            .annotate(import_date=TruncDate("created_at"))
            .values_list("import_date", flat=True)
            .annotate(c=Count("id"))
        )

    def find_for(self, user):
        """
        Find existing Pôle emploi's approvals for the given user.

        We were told to check on `first_name` + `last_name` + `birthdate`
        but it's far from ideal:

        - the character encoding format is different between databases
        - there are no accents in the PE database
            => `format_name_as_pole_emploi()` is required to harmonize the formats
        - input errors in names are possible on both sides
        - there can be an inversion of first and last name fields
        - imported data can be poorly structured (first and last names in the same field)

        In many cases, we can identify the user based on its NIR number, when the PoleEmploiApproval
        has this information (which is the case 90% of the time) and we also have it.

        We'll also return the PE Approvals based on the combination of `pole_emploi_id`
        (non-unique but it is assumed that every job seeker knows his number) and `birthdate`.

        Their input formats can be checked to limit the risk of errors.
        """
        filter_expression = Q(pk=None)  # no match
        if user.nir:
            # Allow duplicated NIR within PE approvals, but that will most probably change with the
            # ApprovalsWrapper code revamp later on. For now there is no unicity constraint on this column.
            filter_expression |= Q(nir=user.nir)
        if user.pole_emploi_id and user.birthdate:
            filter_expression |= Q(pole_emploi_id=user.pole_emploi_id, birthdate=user.birthdate)
        return self.filter(filter_expression).order_by("-start_at")

    def without_nir_ntt_or_nia(self):
        return self.filter(Q(nir=None) & Q(ntt_nia=None))


class PoleEmploiApproval(PENotificationMixin, CommonApprovalMixin):
    """
    Store consolidated approvals (`agréments` in French) delivered by Pôle emploi.

    Two approval's delivering systems co-exist. Pôle emploi's approvals
    are issued in parallel.

    Thus, before Itou can deliver an approval, we have to check this table
    to ensure that there isn't already a valid Pôle emploi's approval.

    This table is populated and updated through the `import_pe_approvals`
    admin command on a regular basis with data shared by Pôle emploi.

    If a valid Pôle emploi's approval is found, it's copied in the `Approval`
    at the time of issuance. See Approval model's code for more information.
    """

    # Matches prescriber_organization.code_safir_pole_emploi.
    pe_structure_code = models.CharField("Code structure Pôle emploi", max_length=5)

    # - first 5 digits = code SAFIR of the PE agency of the consultant creating the approval
    # - next 2 digits = 2-digit year of delivery
    # - next 5 digits = decision number with autonomous increment per PE agency, e.g.: 75631 14 10001
    #     - decisions are starting with 1
    #     - decisions starting with 0 are reserved for "Reprise des décisions", e.g.: 75631 14 00001
    number = models.CharField(verbose_name="Numéro", max_length=12, unique=True)

    pole_emploi_id = models.CharField("Identifiant Pôle emploi", max_length=8)
    first_name = models.CharField("Prénom", max_length=150)
    last_name = models.CharField("Nom", max_length=150)
    birth_name = models.CharField("Nom de naissance", max_length=150)
    birthdate = models.DateField(verbose_name="Date de naissance", default=timezone.localdate)
    nir = models.CharField(verbose_name="NIR", max_length=15, null=True, blank=True)
    # Some people have no NIR. They can have a temporary NIA or NTT instead:
    # https://www.net-entreprises.fr/astuces/identification-des-salaries%E2%80%AF-nir-nia-et-ntt/
    # NTT max length = 40 chars, max duration = 3 months
    ntt_nia = models.CharField(verbose_name="NTT ou NIA", max_length=40, null=True, blank=True)

    objects = PoleEmploiApprovalManager.from_queryset(CommonApprovalQuerySet)()

    class Meta:
        verbose_name = "Agrément Pôle emploi"
        verbose_name_plural = "Agréments Pôle emploi"
        ordering = ["-start_at"]
        indexes = [models.Index(fields=["pole_emploi_id", "birthdate"], name="pe_id_and_birthdate_idx")]

    def __str__(self):
        return self.number

    def is_valid(self):
        return super().is_valid(end_at=self.end_at)

    @staticmethod
    def format_name_as_pole_emploi(name):
        """
        Format `name` in the same way as it is in the Pôle emploi export file:
        Upper-case ASCII transliterations of Unicode text.
        """
        return unidecode(name.strip()).upper()

    @property
    def number_with_spaces(self):
        return f"{self.number[:5]} {self.number[5:7]} {self.number[7:]}"


class OriginalPoleEmploiApproval(CommonApprovalMixin):
    """
    This table contains the original, "unmerged" PEApprovals: in particular it may have
    several lines for a single person, one being actually a suspension, others an Approval
    and some others, a prolongation.

    The merged PE Approvals that we generated are present in the "PoleEmploiApproval" model and
    have been merged using a one-time command (merge_pe_approvals) on March 18th, 2022.

    This table is kept for reference and historical reasons. It does not contain any import
    later than March 18th, 2022; in particular the one that has been done on March 30th 2022
    only has been made to the PoleEmploiApproval table.
    """

    # The normal length of a number is 12 chars.
    # Sometimes the number ends with an extension ('A01', 'E02', 'P03', 'S04' etc.) that
    # increases the length to 15 chars.
    # Suffixes meaning in French:
    class Suffix(models.TextChoices):
        # `P`: Prolongation = la personne a besoin d'encore quelques mois
        P = "prolongation", "Prolongation"
        # `E`: Extension = la personne est passée d'une structure à une autre
        E = "extension", "Extension"
        # `A`: Interruption = la personne ne s'est pas présentée
        A = "interruption", "Interruption"
        # `S`: Suspension = creux pendant la période justifié dans un cadre légal (incarcération, arrêt maladie etc.)
        S = "suspension", "Suspension"

    # All those fields are copied from PoleEmploiApproval
    pe_structure_code = models.CharField("Code structure Pôle emploi", max_length=5)

    # Parts of an "original" PE Approval number:
    #     - first 5 digits = code SAFIR of the PE agency of the consultant creating the approval
    #     - next 2 digits = 2-digit year of delivery
    #     - next 5 digits = decision number with autonomous increment per PE agency, e.g.: 75631 14 10001
    #         - decisions are starting with 1
    #         - decisions starting with 0 are reserved for "Reprise des décisions", e.g.: 75631 14 00001
    #     - next 3 chars (optional suffix) = status change, e.g.: 75631 14 10001 E01
    #         - first char = kind of amendment:
    #             - E for "Extension"
    #             - S for "Suspension"
    #             - P for "Prolongation"
    #             - A for "Interruption"
    #         - next 2 digits = refer to the act number (e.g. E02 = second extension)
    # An Approval number is not modifiable, there is a new entry for each new status change.
    # Suffixes are not taken into account in Itou.
    number = models.CharField(verbose_name="Numéro", max_length=15, unique=True)

    pole_emploi_id = models.CharField("Identifiant Pôle emploi", max_length=8)
    first_name = models.CharField("Prénom", max_length=150)
    last_name = models.CharField("Nom", max_length=150)
    birth_name = models.CharField("Nom de naissance", max_length=150)
    birthdate = models.DateField(verbose_name="Date de naissance", default=timezone.localdate)
    nir = models.CharField(verbose_name="NIR", max_length=15, null=True, blank=True)
    ntt_nia = models.CharField(verbose_name="NTT ou NIA", max_length=40, null=True, blank=True)

    class Meta:
        # the table name is misleading but is called "merged" for historical reasons.
        # actually, the table contains original, **unmerged** approvals (after tables were swapped
        # in production on March 18th, 2022)
        db_table = "merged_approvals_poleemploiapproval"
        verbose_name = "Agrément Pôle emploi original"
        verbose_name_plural = "Agréments Pôle emploi originaux"
        ordering = ["-start_at"]
        indexes = [models.Index(fields=["pole_emploi_id", "birthdate"], name="merged_pe_id_and_birthdate_idx")]


class ApprovalsWrapper:
    """
    Wrapper that manipulates both `Approval` and `PoleEmploiApproval` models.

    This should be the only way to access approvals for a given job seeker.

    Pôle emploi is the historical issuing authority for approvals.
    At the end of 2019, Itou began to issue approvals (called PASS IAE) in
    parallel.
    During 2021, Itou should become the new sole issuing authority.
    But for the time being, 2 systems coexist.

    When a candidate applies for a job, it is necessary to:
        - check if Itou has already issued a PASS IAE
        - or check if Pôle emploi has already issued an approval

    Moreover, the status must be checked to be able to block applications
    in case of waiting period, suspension etc.

    This wrapper encapsulates all this logic for use in views and templates
    without having to manually search in two different tables.

    (Maybe a Manager would've been a better place for this logic).
    """

    # Status codes.
    NONE_FOUND = "NONE_FOUND"
    VALID = "VALID"
    IN_WAITING_PERIOD = "IN_WAITING_PERIOD"

    # Error messages.
    WAITING_PERIOD_DOC_LINK = get_external_link_markup(
        url=f"{settings.ITOU_COMMUNITY_URL }/doc/emplois/derogation-au-delai-de-carence/",
        text="En savoir plus sur la dérogation du délai de carence",
    )
    ERROR_CANNOT_OBTAIN_NEW_FOR_USER = mark_safe(
        (
            "Vous avez terminé un parcours il y a moins de deux ans.<br>"
            "Pour prétendre à nouveau à un parcours en structure d'insertion "
            "par l'activité économique vous devez rencontrer un prescripteur "
            "habilité : Pôle emploi, Mission Locale, CAP Emploi, etc."
        )
    )
    ERROR_CANNOT_OBTAIN_NEW_FOR_PROXY = mark_safe(
        (
            "Le candidat a terminé un parcours il y a moins de deux ans.<br>"
            "Pour prétendre à nouveau à un parcours en structure d'insertion "
            "par l'activité économique il doit rencontrer un prescripteur "
            "habilité : Pôle emploi, Mission Locale, CAP Emploi, etc."
            f"<br>{WAITING_PERIOD_DOC_LINK}"  # Display doc link only for proxies.
        )
    )

    def __init__(self, user=None, number=None):

        self.user = user
        self.number = number
        self.latest_approval = None
        if user:
            self.merged_approvals = self._merge_approvals_for_user()
        elif number:
            self.merged_approvals = self._merge_approvals_for_number()
        else:
            raise KeyError("A user or a number is required.")

        if not self.merged_approvals:
            self.status = self.NONE_FOUND
        else:
            self.latest_approval = self.merged_approvals[0]
            if self.latest_approval.is_valid():
                self.status = self.VALID
            elif self.latest_approval.waiting_period_has_elapsed:
                # The `Période de carence` is over. A job seeker can get a new Approval.
                self.latest_approval = None
                self.status = self.NONE_FOUND
            else:
                self.status = self.IN_WAITING_PERIOD

        # Only one of the following attributes can be True at a time.
        self.has_valid = self.status == self.VALID
        self.has_in_waiting_period = self.status == self.IN_WAITING_PERIOD

    def _merge_approvals_for_user(self):
        """
        Returns a list of merged unique `Approval` and `PoleEmploiApproval` objects.
        """
        approvals = Approval.objects.filter(user=self.user).order_by("-start_at")

        # If an ongoing PASS IAE exists, consider it's the latest valid approval
        # even if a PoleEmploiApproval is more recent.
        if approvals.valid().exists():
            return approvals

        today = datetime.date.today()
        approvals_numbers = [approval.number for approval in approvals] if approvals else []

        pe_approvals = (
            PoleEmploiApproval.objects.find_for(self.user)
            .filter(start_at__lte=today)
            .exclude(number__in=approvals_numbers)
        )

        merged_approvals = list(approvals) + list(pe_approvals)
        return self.sort_approvals(merged_approvals)

    def _merge_approvals_for_number(self):
        """
        Returns a list of merged unique `Approval` and `PoleEmploiApproval` objects.
        """
        # Truncate the number to remove any 'S01' or 'P01' suffix because the
        # number is limited to 12 digits in Approval table.
        approvals = Approval.objects.filter(number=self.number[:12]).order_by("-start_at")

        # If a PASS IAE exists, consider it's the latest approval
        # even if a PoleEmploiApproval is more recent.
        # Return valid and expired approvals.
        if approvals.exists():
            return approvals

        today = datetime.date.today()
        pe_approvals = PoleEmploiApproval.objects.filter(number__startswith=self.number, start_at__lte=today)

        merged_approvals = list(approvals) + list(pe_approvals)
        return self.sort_approvals(merged_approvals)

    @property
    def has_valid_pole_emploi_eligibility_diagnosis(self):
        """
        The existence of a valid `PoleEmploiApproval` implies that a diagnosis
        has been made outside of Itou.
        """
        return self.has_valid and not self.latest_approval.originates_from_itou

    def cannot_bypass_waiting_period(self, siae, sender_prescriber_organization):
        """
        An approval in waiting period can only be bypassed if the prescriber is authorized
        or if the structure is not a SIAE.
        """
        is_sent_by_authorized_prescriber = (
            sender_prescriber_organization is not None and sender_prescriber_organization.is_authorized
        )

        # Only diagnoses made by authorized prescribers are taken into account.
        has_valid_diagnosis = self.user.has_valid_diagnosis()
        return (
            self.has_in_waiting_period
            and siae.is_subject_to_eligibility_rules
            and not (is_sent_by_authorized_prescriber or has_valid_diagnosis)
        )

    @staticmethod
    def sort_approvals(common_approvals):
        """
        Returns a list of sorted approvals. The first one is the longest and the most recent.
        ---
        common_approvals: Queryset or list of Approval or PoleEmploiApproval objects.
        """
        approvals = list(common_approvals)
        # Sort by the most distant `end_at`, then by the earliest `start_at`.
        # This allows to always choose the longest and most recent approval.
        # Dates are converted to timestamp so that the subtraction operator
        # can be used in the lambda.
        return sorted(
            approvals, key=lambda x: (-time.mktime(x.end_at.timetuple()), time.mktime(x.start_at.timetuple()))
        )
