from dateutil.relativedelta import relativedelta
from django.core.management import BaseCommand
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from itou.siae_evaluations.models import EvaluatedAdministrativeCriteria, EvaluationCampaign
from itou.utils.emails import send_email_messages


class Command(BaseCommand):
    def handle(self, **options):
        today = timezone.localdate()
        campaigns = EvaluationCampaign.objects.filter(ended_at=None).select_related("institution")
        for campaign in campaigns.filter(
            evaluations_asked_at__date__range=[
                # Stop sending reminder after manual run of
                # EvaluationCampaign.transition_to_adversarial_phase
                today - EvaluationCampaign.ADVERSARIAL_STAGE_START_DELTA,
                today - relativedelta(days=30),
            ],
        ):
            emails = []
            evaluated_siaes = (
                campaign.evaluated_siaes.did_not_send_proof()
                .filter(reviewed_at=None, reminder_sent_at=None)
                .select_related("evaluation_campaign__institution", "siae__convention")
            )
            for evaluated_siae in evaluated_siaes:
                emails.append(evaluated_siae.get_email_to_siae_notify_before_adversarial_stage())
            if emails:
                send_email_messages(emails)
                evaluated_siaes.update(reminder_sent_at=timezone.now())
                self.stdout.write(
                    f"Emailed first reminders to {len(emails)} SIAE which did not submit proofs to {campaign}."
                )

        evaluations_asked_before = today - EvaluationCampaign.ADVERSARIAL_STAGE_START_DELTA - relativedelta(days=30)
        for campaign in campaigns.filter(evaluations_asked_at__date__lte=evaluations_asked_before):
            emails = []
            evaluated_siaes = (
                campaign.evaluated_siaes.exclude(
                    Exists(
                        EvaluatedAdministrativeCriteria.objects.filter(
                            evaluated_job_application__evaluated_siae=OuterRef("pk"),
                            submitted_at__gt=F("evaluated_job_application__evaluated_siae__reviewed_at"),
                        )
                    )
                )
                .filter(Q(reminder_sent_at=None) | Q(reminder_sent_at__lt=F("reviewed_at")))
                .select_related("evaluation_campaign__institution", "siae__convention")
            )
            for evaluated_siae in evaluated_siaes:
                emails.append(evaluated_siae.get_email_to_siae_notify_before_campaign_close())
            if emails:
                send_email_messages(emails)
                evaluated_siaes.update(reminder_sent_at=timezone.now())
                self.stdout.write(
                    f"Emailed second reminders to {len(emails)} SIAE which did not submit proofs to {campaign}."
                )
