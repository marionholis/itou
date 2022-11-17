from datetime import datetime

from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from itou.approvals.factories import ApprovalFactory
from itou.employee_record.enums import Status
from itou.employee_record.factories import EmployeeRecordFactory
from itou.institutions.factories import InstitutionMembershipFactory
from itou.job_applications.factories import (
    JobApplicationSentByAuthorizedPrescriberOrganizationFactory,
    JobApplicationSentByPrescriberFactory,
    JobApplicationWithApprovalFactory,
)
from itou.job_applications.notifications import (
    NewQualifiedJobAppEmployersNotification,
    NewSpontaneousJobAppEmployersNotification,
)
from itou.prescribers import factories as prescribers_factories
from itou.prescribers.enums import PrescriberOrganizationKind
from itou.siae_evaluations import enums as evaluation_enums
from itou.siae_evaluations.constants import CAMPAIGN_VIEWABLE_DURATION
from itou.siae_evaluations.factories import EvaluatedSiaeFactory, EvaluationCampaignFactory
from itou.siaes.enums import SiaeKind
from itou.siaes.factories import (
    SiaeAfterGracePeriodFactory,
    SiaeFactory,
    SiaeMembershipFactory,
    SiaePendingGracePeriodFactory,
    SiaeWithMembershipAndJobsFactory,
)
from itou.users.enums import IdentityProvider
from itou.users.factories import DEFAULT_PASSWORD, JobSeekerFactory, PrescriberFactory, SiaeStaffFactory
from itou.users.models import User
from itou.utils import constants as global_constants
from itou.utils.templatetags.format_filters import format_approval_number
from itou.www.dashboard.forms import EditUserEmailForm


class DashboardViewTest(TestCase):
    def test_dashboard(self):
        siae = SiaeFactory(with_membership=True)
        user = siae.members.first()
        self.client.force_login(user)

        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_user_with_inactive_siae_can_still_login_during_grace_period(self):
        siae = SiaePendingGracePeriodFactory()
        user = SiaeStaffFactory()
        siae.members.add(user)
        self.client.force_login(user)

        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_user_with_inactive_siae_cannot_login_after_grace_period(self):
        siae = SiaeAfterGracePeriodFactory()
        user = SiaeStaffFactory()
        siae.members.add(user)
        self.client.force_login(user)

        url = reverse("dashboard:index")
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        last_url = response.redirect_chain[-1][0]
        self.assertEqual(last_url, reverse("account_logout"))

        expected_message = "votre compte n'est malheureusement plus actif"
        self.assertContains(response, expected_message)

    def test_dashboard_eiti(self):
        siae = SiaeFactory(kind=SiaeKind.EITI, with_membership=True)
        user = siae.members.first()
        self.client.force_login(user)

        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_displays_asp_badge(self):
        siae = SiaeFactory(kind=SiaeKind.EI, with_membership=True)
        other_siae = SiaeFactory(kind=SiaeKind.ETTI, with_membership=True)
        last_siae = SiaeFactory(kind=SiaeKind.ETTI, with_membership=True)

        user = siae.members.first()
        user.siae_set.add(other_siae)
        user.siae_set.add(last_siae)

        self.client.force_login(user)

        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gérer mes fiches salarié")
        self.assertNotContains(response, "badge-danger")
        self.assertEqual(response.context["num_rejected_employee_records"], 0)

        # create rejected job applications
        job_application = JobApplicationWithApprovalFactory(to_siae=siae)
        EmployeeRecordFactory(job_application=job_application, status=Status.REJECTED)
        # You can't create 2 employee records with the same job application
        # Factories were allowing it until a recent fix was applied
        job_application = JobApplicationWithApprovalFactory(to_siae=siae)
        EmployeeRecordFactory(job_application=job_application, status=Status.REJECTED)

        other_job_application = JobApplicationWithApprovalFactory(to_siae=other_siae)
        EmployeeRecordFactory(job_application=other_job_application, status=Status.REJECTED)

        session = self.client.session

        # select the first SIAE's in the session
        session[global_constants.ITOU_SESSION_CURRENT_SIAE_KEY] = siae.pk
        session.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "badge-danger")
        self.assertEqual(response.context["num_rejected_employee_records"], 2)

        # select the second SIAE's in the session
        session[global_constants.ITOU_SESSION_CURRENT_SIAE_KEY] = other_siae.pk
        session.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "badge-danger")
        self.assertEqual(response.context["num_rejected_employee_records"], 1)

        # select the third SIAE's in the session
        session[global_constants.ITOU_SESSION_CURRENT_SIAE_KEY] = last_siae.pk
        session.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["num_rejected_employee_records"], 0)

    def test_dashboard_agreements_and_job_postings(self):
        for kind in [
            SiaeKind.AI,
            SiaeKind.EI,
            SiaeKind.EITI,
            SiaeKind.ACI,
            SiaeKind.ETTI,
        ]:
            with self.subTest(f"should display when siae_kind={kind}"):
                siae = SiaeFactory(kind=kind, with_membership=True)
                user = siae.members.first()
                self.client.force_login(user)

                response = self.client.get(reverse("dashboard:index"))
                self.assertContains(response, "Prolonger/suspendre un agrément émis par Pôle emploi")
                self.assertContains(response, "Déclarer une embauche")

        for kind in [SiaeKind.EA, SiaeKind.EATT, SiaeKind.GEIQ, SiaeKind.OPCS]:
            with self.subTest(f"should not display when siae_kind={kind}"):
                siae = SiaeFactory(kind=kind, with_membership=True)
                user = siae.members.first()
                self.client.force_login(user)

                response = self.client.get(reverse("dashboard:index"))
                self.assertNotContains(response, "Prolonger/suspendre un agrément émis par Pôle emploi")
                self.assertNotContains(response, "Déclarer une embauche")

    def test_dashboard_can_create_siae_antenna(self):
        for kind in SiaeKind:
            with self.subTest(kind=kind):
                siae = SiaeFactory(kind=kind, with_membership=True, membership__is_admin=True)
                user = siae.members.get()

                self.client.force_login(user)
                response = self.client.get(reverse("dashboard:index"))

                if user.can_create_siae_antenna(siae):
                    self.assertContains(response, "Créer/rejoindre une autre structure")
                else:
                    self.assertNotContains(response, "Créer/rejoindre une autre structure")

    def test_dashboard_siae_evaluations_institution_access(self):
        membershipfactory = InstitutionMembershipFactory()
        user = membershipfactory.user
        institution = membershipfactory.institution
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard:index"))
        self.assertNotContains(response, "Contrôle a posteriori")
        self.assertNotContains(response, reverse("siae_evaluations_views:samples_selection"))

        evaluation_campaign = EvaluationCampaignFactory(institution=institution)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Contrôle a posteriori")
        self.assertContains(response, reverse("siae_evaluations_views:samples_selection"))
        self.assertNotContains(
            response,
            reverse(
                "siae_evaluations_views:institution_evaluated_siae_list",
                kwargs={"evaluation_campaign_pk": evaluation_campaign.pk},
            ),
        )

        evaluation_campaign.evaluations_asked_at = timezone.now()
        evaluation_campaign.save(update_fields=["evaluations_asked_at"])
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Contrôle a posteriori")
        self.assertNotContains(response, reverse("siae_evaluations_views:samples_selection"))
        self.assertContains(
            response,
            reverse(
                "siae_evaluations_views:institution_evaluated_siae_list",
                kwargs={"evaluation_campaign_pk": evaluation_campaign.pk},
            ),
        )

        evaluation_campaign.ended_at = timezone.now()
        evaluation_campaign.save(update_fields=["ended_at"])
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Contrôle a posteriori")
        self.assertNotContains(response, reverse("siae_evaluations_views:samples_selection"))
        self.assertContains(
            response,
            reverse(
                "siae_evaluations_views:institution_evaluated_siae_list",
                kwargs={"evaluation_campaign_pk": evaluation_campaign.pk},
            ),
        )

        evaluation_campaign.ended_at = timezone.now() - CAMPAIGN_VIEWABLE_DURATION
        evaluation_campaign.save(update_fields=["ended_at"])
        response = self.client.get(reverse("dashboard:index"))
        self.assertNotContains(response, "Contrôle a posteriori")
        self.assertNotContains(response, reverse("siae_evaluations_views:samples_selection"))
        self.assertNotContains(
            response,
            reverse(
                "siae_evaluations_views:institution_evaluated_siae_list",
                kwargs={"evaluation_campaign_pk": evaluation_campaign.pk},
            ),
        )

    def test_dashboard_siae_evaluation_campaign_notifications(self):
        membership = SiaeMembershipFactory()
        evaluated_siae_with_final_decision = EvaluatedSiaeFactory(
            evaluation_campaign__name="Final decision reached",
            complete=True,
            job_app__criteria__review_state=evaluation_enums.EvaluatedJobApplicationsState.REFUSED_2,
            siae=membership.siae,
            notified_at=timezone.now(),
            notification_reason=evaluation_enums.EvaluatedSiaeNotificationReason.INVALID_PROOF,
            notification_text="A envoyé une photo de son chat. Séparé de son chat pendant une journée.",
        )
        EvaluatedSiaeFactory(
            evaluation_campaign__name="In progress",
            siae=membership.siae,
            evaluation_campaign__evaluations_asked_at=timezone.now(),
        )
        EvaluatedSiaeFactory(
            evaluation_campaign__name="Not notified",
            complete=True,
            job_app__criteria__review_state=evaluation_enums.EvaluatedJobApplicationsState.REFUSED_2,
            siae=membership.siae,
        )
        evaluated_siae_campaign_closed = EvaluatedSiaeFactory(
            evaluation_campaign__name="Just closed",
            complete=True,
            siae=membership.siae,
            evaluation_campaign__ended_at=timezone.now() - relativedelta(days=4),
            notified_at=timezone.now(),
            notification_reason=evaluation_enums.EvaluatedSiaeNotificationReason.MISSING_PROOF,
            notification_text="Journée de formation.",
        )
        # Long closed.
        EvaluatedSiaeFactory(
            evaluation_campaign__name="Long closed",
            complete=True,
            siae=membership.siae,
            evaluation_campaign__ended_at=timezone.now() - CAMPAIGN_VIEWABLE_DURATION,
            notified_at=timezone.now(),
            notification_reason=evaluation_enums.EvaluatedSiaeNotificationReason.INVALID_PROOF,
            notification_text="A envoyé une photo de son chat.",
        )

        self.client.force_login(membership.user)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(
            response,
            "Contrôle a posteriori "
            '<span class="badge badge-pill badge-sm badge-important text-primary">Nouveau</span>',
            count=1,
        )
        self.assertContains(
            response,
            f"""
            <li class="card-text mb-3">
                <a href="/siae_evaluation/evaluated_siae_sanction/{evaluated_siae_with_final_decision.pk}/">
                    Voir le résultat du contrôle “Final decision reached”
                </a>
            </li>
            """,
            html=True,
            count=1,
        )
        self.assertContains(
            response,
            f"""
            <li class="card-text mb-3">
                <a href="/siae_evaluation/evaluated_siae_sanction/{evaluated_siae_campaign_closed.pk}/">
                    Voir le résultat du contrôle “Just closed”
                </a>
            </li>
            """,
            html=True,
            count=1,
        )
        self.assertNotContains(response, "Long closed")
        self.assertNotContains(response, "Not notified")
        self.assertNotContains(response, "In progress")

    def test_dashboard_siae_evaluations_siae_access(self):
        # preset for incoming new pages
        siae = SiaeFactory(with_membership=True)
        user = siae.members.first()
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard:index"))
        self.assertNotContains(response, "Contrôle a posteriori")

        fake_now = timezone.now()
        EvaluatedSiaeFactory(siae=siae, evaluation_campaign__evaluations_asked_at=fake_now)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Contrôle a posteriori")

    def test_dashboard_prescriber_suspend_link(self):

        user = JobSeekerFactory()
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:index"))
        self.assertNotContains(response, "Suspendre un PASS IAE")

        siae = SiaeFactory(with_membership=True)
        user = siae.members.first()
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:index"))
        self.assertNotContains(response, "Suspendre un PASS IAE")

        membershipfactory = InstitutionMembershipFactory()
        user = membershipfactory.user
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:index"))
        self.assertNotContains(response, "Suspendre un PASS IAE")

        prescriber_org = prescribers_factories.PrescriberOrganizationWithMembershipFactory(
            kind=PrescriberOrganizationKind.CAP_EMPLOI
        )
        prescriber = prescriber_org.members.first()
        self.client.force_login(prescriber)
        response = self.client.get(reverse("dashboard:index"))
        self.assertNotContains(response, "Suspendre un PASS IAE")

        prescriber_org_pe = prescribers_factories.PrescriberOrganizationWithMembershipFactory(
            kind=PrescriberOrganizationKind.PE
        )
        prescriber_pe = prescriber_org_pe.members.first()
        self.client.force_login(prescriber_pe)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Suspendre un PASS IAE")

    @freeze_time("2022-09-15")
    def test_dashboard_access_by_a_jobseeker(self):
        approval = ApprovalFactory(start_at=datetime(2022, 6, 21), end_at=datetime(2022, 12, 6))
        self.client.force_login(approval.user)
        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertContains(response, "PASS IAE (agrément) disponible :")
        self.assertContains(response, format_approval_number(approval))
        self.assertContains(response, "Valide du 21/06/2022 au 06/12/2022")
        self.assertContains(response, "Délivrance : le 21/06/2022")

    @override_settings(TALLY_URL="http://tally.fake")
    def test_prescriber_with_authorization_pending_dashboard_must_contain_tally_link(self):
        prescriber_org = prescribers_factories.PrescriberOrganizationWithMembershipFactory(
            kind=PrescriberOrganizationKind.OTHER,
            with_pending_authorization=True,
        )

        prescriber = prescriber_org.members.first()
        self.client.force_login(prescriber)
        response = self.client.get(reverse("dashboard:index"))

        self.assertContains(
            response,
            f"http://tally.fake/r/wgDzz1?"
            f"idprescriber={prescriber_org.pk}"
            f"&iduser={prescriber.pk}"
            f"&source={settings.ITOU_ENVIRONMENT}",
        )


class EditUserInfoViewTest(TestCase):
    def test_edit(self):
        user = JobSeekerFactory()
        self.client.force_login(user)
        url = reverse("dashboard:edit_user_info")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # There's a specific view to edit the email so we don't show it here
        self.assertNotContains(response, "Adresse électronique")

        post_data = {
            "email": "bob@saintclar.net",
            "first_name": "Bob",
            "last_name": "Saint Clar",
            "birthdate": "20/12/1978",
            "phone": "0610203050",
            "lack_of_pole_emploi_id_reason": user.REASON_NOT_REGISTERED,
            "address_line_1": "10, rue du Gué",
            "address_line_2": "Sous l'escalier",
            "post_code": "35400",
            "city": "Saint-Malo",
        }
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(id=user.id)
        self.assertEqual(user.first_name, post_data["first_name"])
        self.assertEqual(user.last_name, post_data["last_name"])
        self.assertEqual(user.phone, post_data["phone"])
        self.assertEqual(user.birthdate.strftime("%d/%m/%Y"), post_data["birthdate"])
        self.assertEqual(user.address_line_1, post_data["address_line_1"])
        self.assertEqual(user.address_line_2, post_data["address_line_2"])
        self.assertEqual(user.post_code, post_data["post_code"])
        self.assertEqual(user.city, post_data["city"])

        # Ensure that the job seeker cannot edit email here.
        self.assertNotEqual(user.email, post_data["email"])

    def test_edit_sso(self):
        user = JobSeekerFactory(identity_provider=IdentityProvider.FRANCE_CONNECT)
        self.client.force_login(user)
        url = reverse("dashboard:edit_user_info")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Adresse électronique")

        post_data = {
            "email": "bob@saintclar.net",
            "first_name": "Bob",
            "last_name": "Saint Clar",
            "birthdate": "20/12/1978",
            "phone": "0610203050",
            "lack_of_pole_emploi_id_reason": user.REASON_NOT_REGISTERED,
            "address_line_1": "10, rue du Gué",
            "address_line_2": "Sous l'escalier",
            "post_code": "35400",
            "city": "Saint-Malo",
        }
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(id=user.id)
        self.assertEqual(user.phone, post_data["phone"])
        self.assertEqual(user.address_line_1, post_data["address_line_1"])
        self.assertEqual(user.address_line_2, post_data["address_line_2"])
        self.assertEqual(user.post_code, post_data["post_code"])
        self.assertEqual(user.city, post_data["city"])

        # Ensure that the job seeker cannot update data retreived from the SSO here.
        self.assertNotEqual(user.first_name, post_data["first_name"])
        self.assertNotEqual(user.last_name, post_data["last_name"])
        self.assertNotEqual(user.birthdate.strftime("%d/%m/%Y"), post_data["birthdate"])
        self.assertNotEqual(user.email, post_data["email"])


class EditJobSeekerInfo(TestCase):
    def test_edit_by_siae(self):
        job_application = JobApplicationSentByPrescriberFactory()
        user = job_application.to_siae.members.first()

        # Ensure that the job seeker is not autonomous (i.e. he did not register by himself).
        job_application.job_seeker.created_by = user
        job_application.job_seeker.save()

        self.client.force_login(user)

        back_url = reverse("apply:details_for_siae", kwargs={"job_application_id": job_application.id})
        url = reverse("dashboard:edit_job_seeker_info", kwargs={"job_application_id": job_application.pk})
        url = f"{url}?back_url={back_url}"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        post_data = {
            "email": "bob@saintclar.net",
            "first_name": "Bob",
            "last_name": "Saint Clar",
            "birthdate": "20/12/1978",
            "lack_of_pole_emploi_id_reason": user.REASON_NOT_REGISTERED,
            "address_line_1": "10, rue du Gué",
            "post_code": "35400",
            "city": "Saint-Malo",
        }
        response = self.client.post(url, data=post_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, back_url)

        job_seeker = User.objects.get(id=job_application.job_seeker.id)
        self.assertEqual(job_seeker.first_name, post_data["first_name"])
        self.assertEqual(job_seeker.last_name, post_data["last_name"])
        self.assertEqual(job_seeker.birthdate.strftime("%d/%m/%Y"), post_data["birthdate"])
        self.assertEqual(job_seeker.address_line_1, post_data["address_line_1"])
        self.assertEqual(job_seeker.post_code, post_data["post_code"])
        self.assertEqual(job_seeker.city, post_data["city"])

        # Optional fields
        post_data |= {
            "phone": "0610203050",
            "address_line_2": "Sous l'escalier",
        }
        response = self.client.post(url, data=post_data)
        job_seeker.refresh_from_db()

        self.assertEqual(job_seeker.phone, post_data["phone"])
        self.assertEqual(job_seeker.address_line_2, post_data["address_line_2"])

    def test_edit_by_prescriber(self):
        job_application = JobApplicationSentByAuthorizedPrescriberOrganizationFactory()
        user = job_application.sender

        # Ensure that the job seeker is not autonomous (i.e. he did not register by himself).
        job_application.job_seeker.created_by = user
        job_application.job_seeker.save()

        self.client.force_login(user)
        url = reverse("dashboard:edit_job_seeker_info", kwargs={"job_application_id": job_application.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_edit_by_prescriber_of_organization(self):
        job_application = JobApplicationSentByAuthorizedPrescriberOrganizationFactory()
        prescriber = job_application.sender

        # Ensure that the job seeker is not autonomous (i.e. he did not register by himself).
        job_application.job_seeker.created_by = prescriber
        job_application.job_seeker.save()

        # Log as other member of the same organization
        other_prescriber = PrescriberFactory()
        prescribers_factories.PrescriberMembershipFactory(
            user=other_prescriber, organization=job_application.sender_prescriber_organization
        )
        self.client.force_login(other_prescriber)
        url = reverse("dashboard:edit_job_seeker_info", kwargs={"job_application_id": job_application.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_edit_autonomous_not_allowed(self):
        job_application = JobApplicationSentByPrescriberFactory()
        # The job seeker manages his own personal information (autonomous)
        user = job_application.sender
        self.client.force_login(user)

        url = reverse("dashboard:edit_job_seeker_info", kwargs={"job_application_id": job_application.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_edit_not_allowed(self):
        # Ensure that the job seeker is not autonomous (i.e. he did not register by himself).
        job_application = JobApplicationSentByPrescriberFactory(job_seeker__created_by=PrescriberFactory())

        # Lambda prescriber not member of the sender organization
        prescriber = PrescriberFactory()
        self.client.force_login(prescriber)
        url = reverse("dashboard:edit_job_seeker_info", kwargs={"job_application_id": job_application.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_edit_email_when_unconfirmed(self):
        """
        The SIAE can edit the email of a jobseeker it works with, provided he did not confirm its email.
        """
        new_email = "bidou@yopmail.com"
        siae = SiaeFactory(with_membership=True)
        user = siae.members.first()
        job_application = JobApplicationSentByPrescriberFactory(to_siae=siae, job_seeker__created_by=user)

        self.client.force_login(user)

        back_url = reverse("apply:details_for_siae", kwargs={"job_application_id": job_application.id})
        url = reverse("dashboard:edit_job_seeker_info", kwargs={"job_application_id": job_application.pk})
        url = f"{url}?back_url={back_url}"

        response = self.client.get(url)
        self.assertContains(response, "Adresse électronique")

        post_data = {
            "email": new_email,
            "birthdate": "20/12/1978",
            "lack_of_pole_emploi_id_reason": user.REASON_NOT_REGISTERED,
            "address_line_1": "10, rue du Gué",
            "post_code": "35400",
            "city": "Saint-Malo",
        }
        response = self.client.post(url, data=post_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, back_url)

        job_seeker = User.objects.get(id=job_application.job_seeker.id)
        self.assertEqual(job_seeker.email, new_email)

        # Optional fields
        post_data |= {
            "phone": "0610203050",
            "address_line_2": "Sous l'escalier",
        }
        response = self.client.post(url, data=post_data)
        job_seeker.refresh_from_db()

        self.assertEqual(job_seeker.phone, post_data["phone"])
        self.assertEqual(job_seeker.address_line_2, post_data["address_line_2"])

    def test_edit_email_when_confirmed(self):
        new_email = "bidou@yopmail.com"
        job_application = JobApplicationSentByPrescriberFactory()
        user = job_application.to_siae.members.first()

        # Ensure that the job seeker is not autonomous (i.e. he did not register by himself).
        job_application.job_seeker.created_by = user
        job_application.job_seeker.save()

        # Confirm job seeker email
        job_seeker = User.objects.get(id=job_application.job_seeker.id)
        EmailAddress.objects.create(user=job_seeker, email=job_seeker.email, verified=True)

        # Now the SIAE wants to edit the jobseeker email. The field is not available, and it cannot be bypassed
        self.client.force_login(user)

        back_url = reverse("apply:details_for_siae", kwargs={"job_application_id": job_application.id})
        url = reverse("dashboard:edit_job_seeker_info", kwargs={"job_application_id": job_application.pk})
        url = f"{url}?back_url={back_url}"

        response = self.client.get(url)
        self.assertNotContains(response, "Adresse électronique")

        post_data = {
            "email": new_email,
            "birthdate": "20/12/1978",
            "lack_of_pole_emploi_id_reason": user.REASON_NOT_REGISTERED,
            "address_line_1": "10, rue du Gué",
            "post_code": "35400",
            "city": "Saint-Malo",
        }
        response = self.client.post(url, data=post_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, back_url)

        job_seeker = User.objects.get(id=job_application.job_seeker.id)
        # The email is not changed, but other fields are taken into account
        self.assertNotEqual(job_seeker.email, new_email)
        self.assertEqual(job_seeker.birthdate.strftime("%d/%m/%Y"), post_data["birthdate"])
        self.assertEqual(job_seeker.address_line_1, post_data["address_line_1"])
        self.assertEqual(job_seeker.post_code, post_data["post_code"])
        self.assertEqual(job_seeker.city, post_data["city"])

        # Optional fields
        post_data |= {
            "phone": "0610203050",
            "address_line_2": "Sous l'escalier",
        }
        response = self.client.post(url, data=post_data)
        job_seeker.refresh_from_db()

        self.assertEqual(job_seeker.phone, post_data["phone"])
        self.assertEqual(job_seeker.address_line_2, post_data["address_line_2"])


class ChangeEmailViewTest(TestCase):
    def test_update_email(self):
        user = JobSeekerFactory()
        old_email = user.email
        new_email = "jean@gabin.fr"

        self.client.force_login(user)
        url = reverse("dashboard:edit_user_email")
        response = self.client.get(url)

        email_address = EmailAddress(email=old_email, verified=True, primary=True)
        email_address.user = user
        email_address.save()

        post_data = {"email": new_email, "email_confirmation": new_email}
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 302)

        # User is logged out
        user.refresh_from_db()
        self.assertEqual(response.request.get("user"), None)
        self.assertEqual(user.email, new_email)
        self.assertEqual(user.emailaddress_set.count(), 0)

        # User cannot log in with his old address
        post_data = {"login": old_email, "password": DEFAULT_PASSWORD}
        url = reverse("login:job_seeker")
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context_data["form"].is_valid())

        # User cannot log in until confirmation
        post_data = {"login": new_email, "password": DEFAULT_PASSWORD}
        url = reverse("login:job_seeker")
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("account_email_verification_sent"))

        # User receives an email to confirm his new address.
        email = mail.outbox[0]
        self.assertIn("Confirmez votre adresse e-mail", email.subject)
        self.assertIn("Afin de finaliser votre inscription, cliquez sur le lien suivant", email.body)
        self.assertEqual(email.to[0], new_email)

        # Confirm email + auto login.
        confirmation_token = EmailConfirmationHMAC(user.emailaddress_set.first()).key
        confirm_email_url = reverse("account_confirm_email", kwargs={"key": confirmation_token})
        response = self.client.post(confirm_email_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("account_login"))

        post_data = {"login": user.email, "password": DEFAULT_PASSWORD}
        url = reverse("account_login")
        response = self.client.post(url, data=post_data)
        self.assertTrue(response.context.get("user").is_authenticated)

        user.refresh_from_db()
        self.assertEqual(user.email, new_email)
        self.assertEqual(user.emailaddress_set.count(), 1)
        new_address = user.emailaddress_set.first()
        self.assertEqual(new_address.email, new_email)
        self.assertTrue(new_address.verified)

    def test_update_email_forbidden(self):
        url = reverse("dashboard:edit_user_email")

        job_seeker = JobSeekerFactory(identity_provider=IdentityProvider.FRANCE_CONNECT)
        self.client.force_login(job_seeker)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        prescriber = PrescriberFactory(identity_provider=IdentityProvider.INCLUSION_CONNECT)
        self.client.force_login(prescriber)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class EditUserEmailFormTest(TestCase):
    def test_invalid_form(self):
        old_email = "bernard@blier.fr"

        # Email and confirmation email do not match
        email = "jean@gabin.fr"
        email_confirmation = "oscar@gabin.fr"
        data = {"email": email, "email_confirmation": email_confirmation}
        form = EditUserEmailForm(data=data, user_email=old_email)
        self.assertFalse(form.is_valid())

        # Email already taken by another user. Bad luck!
        user = JobSeekerFactory()
        data = {"email": user.email, "email_confirmation": user.email}
        form = EditUserEmailForm(data=data, user_email=old_email)
        self.assertFalse(form.is_valid())

        # New address is the same as the old one.
        data = {"email": old_email, "email_confirmation": old_email}
        form = EditUserEmailForm(data=data, user_email=old_email)
        self.assertFalse(form.is_valid())

    def test_valid_form(self):
        old_email = "bernard@blier.fr"
        new_email = "jean@gabin.fr"
        data = {"email": new_email, "email_confirmation": new_email}
        form = EditUserEmailForm(data=data, user_email=old_email)
        self.assertTrue(form.is_valid())


class SwitchSiaeTest(TestCase):
    def test_switch_siae(self):
        siae = SiaeFactory(with_membership=True)
        user = siae.members.first()
        self.client.force_login(user)

        related_siae = SiaeFactory()
        related_siae.members.add(user)

        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], siae)

        url = reverse("siaes_views:card", kwargs={"siae_id": siae.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], siae)
        self.assertEqual(response.context["siae"], siae)

        url = reverse("dashboard:switch_siae")
        response = self.client.post(url, data={"siae_id": related_siae.pk})
        self.assertEqual(response.status_code, 302)

        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], related_siae)

        url = reverse("siaes_views:card", kwargs={"siae_id": related_siae.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], related_siae)
        self.assertEqual(response.context["siae"], related_siae)

        url = reverse("siaes_views:job_description_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], related_siae)

        url = reverse("apply:list_for_siae")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], related_siae)

    def test_can_still_switch_to_inactive_siae_during_grace_period(self):
        siae = SiaeFactory(with_membership=True)
        user = siae.members.first()
        self.client.force_login(user)

        related_siae = SiaePendingGracePeriodFactory()
        related_siae.members.add(user)

        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], siae)

        url = reverse("dashboard:switch_siae")
        response = self.client.post(url, data={"siae_id": related_siae.pk})
        self.assertEqual(response.status_code, 302)

        # User has indeed switched.
        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], related_siae)

    def test_cannot_switch_to_inactive_siae_after_grace_period(self):
        siae = SiaeFactory(with_membership=True)
        user = siae.members.first()
        self.client.force_login(user)

        related_siae = SiaeAfterGracePeriodFactory()
        related_siae.members.add(user)

        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], siae)

        # Switching to that siae is not even possible in practice because
        # it does not even show up in the menu.
        url = reverse("dashboard:switch_siae")
        response = self.client.post(url, data={"siae_id": related_siae.pk})
        self.assertEqual(response.status_code, 404)

        # User is still working on the main active siae.
        url = reverse("dashboard:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_siae"], siae)


class EditUserPreferencesTest(TestCase):
    def test_employer_opt_in_siae_no_job_description(self):
        siae = SiaeFactory(with_membership=True)
        user = siae.members.first()
        recipient = user.siaemembership_set.get(siae=siae)
        form_name = "new_job_app_notification_form"

        self.client.force_login(user)

        # Recipient's notifications are empty for the moment.
        self.assertFalse(recipient.notifications)

        url = reverse("dashboard:edit_user_notifications")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Recipients are subscribed to spontaneous notifications by default,
        # the form should reflect that.
        self.assertTrue(response.context[form_name].fields["spontaneous"].initial)

        data = {"spontaneous": True}
        response = self.client.post(url, data=data)

        self.assertEqual(response.status_code, 302)

        recipient.refresh_from_db()
        self.assertTrue(recipient.notifications)
        self.assertTrue(NewSpontaneousJobAppEmployersNotification.is_subscribed(recipient=recipient))

    def test_employer_opt_in_siae_with_job_descriptions(self):
        siae = SiaeWithMembershipAndJobsFactory()
        user = siae.members.first()
        job_descriptions_pks = list(siae.job_description_through.values_list("pk", flat=True))
        recipient = user.siaemembership_set.get(siae=siae)
        form_name = "new_job_app_notification_form"
        self.client.force_login(user)

        # Recipient's notifications are empty for the moment.
        self.assertFalse(recipient.notifications)

        url = reverse("dashboard:edit_user_notifications")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Recipients are subscribed to spontaneous notifications by default,
        # the form should reflect that.
        self.assertEqual(response.context[form_name].fields["qualified"].initial, job_descriptions_pks)

        data = {"qualified": job_descriptions_pks}
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 302)

        recipient.refresh_from_db()
        self.assertTrue(recipient.notifications)

        for pk in job_descriptions_pks:
            self.assertTrue(
                NewQualifiedJobAppEmployersNotification.is_subscribed(recipient=recipient, subscribed_pk=pk)
            )

    def test_employer_opt_out_siae_no_job_descriptions(self):
        siae = SiaeFactory(with_membership=True)
        user = siae.members.first()
        recipient = user.siaemembership_set.get(siae=siae)
        form_name = "new_job_app_notification_form"
        self.client.force_login(user)

        # Recipient's notifications are empty for the moment.
        self.assertFalse(recipient.notifications)

        url = reverse("dashboard:edit_user_notifications")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Recipients are subscribed to spontaneous notifications by default,
        # the form should reflect that.
        self.assertTrue(response.context[form_name].fields["spontaneous"].initial)

        data = {"spontaneous": False}
        response = self.client.post(url, data=data)

        self.assertEqual(response.status_code, 302)

        recipient.refresh_from_db()
        self.assertTrue(recipient.notifications)
        self.assertFalse(NewSpontaneousJobAppEmployersNotification.is_subscribed(recipient=recipient))

    def test_employer_opt_out_siae_with_job_descriptions(self):
        siae = SiaeWithMembershipAndJobsFactory()
        user = siae.members.first()
        job_descriptions_pks = list(siae.job_description_through.values_list("pk", flat=True))
        recipient = user.siaemembership_set.get(siae=siae)
        form_name = "new_job_app_notification_form"
        self.client.force_login(user)

        # Recipient's notifications are empty for the moment.
        self.assertFalse(recipient.notifications)

        url = reverse("dashboard:edit_user_notifications")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Recipients are subscribed to qualified notifications by default,
        # the form should reflect that.
        self.assertEqual(response.context[form_name].fields["qualified"].initial, job_descriptions_pks)

        # The recipient opted out from every notification.
        data = {"spontaneous": False}
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, 302)

        recipient.refresh_from_db()
        self.assertTrue(recipient.notifications)

        for _i, pk in enumerate(job_descriptions_pks):
            self.assertFalse(
                NewQualifiedJobAppEmployersNotification.is_subscribed(recipient=recipient, subscribed_pk=pk)
            )


class EditUserPreferencesExceptionsTest(TestCase):
    def test_not_allowed_user(self):
        # Only employers can currently access the Preferences page.

        prescriber = PrescriberFactory()
        self.client.force_login(prescriber)
        url = reverse("dashboard:edit_user_notifications")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        job_seeker = JobSeekerFactory()
        self.client.force_login(job_seeker)
        url = reverse("dashboard:edit_user_notifications")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
