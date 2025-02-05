import datetime

import pytest
from dateutil.relativedelta import relativedelta
from django.test import override_settings
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from itou.companies.models import Company
from itou.employee_record.enums import Status
from itou.users.enums import LackOfNIRReason
from itou.utils.templatetags import format_filters
from tests.approvals import factories as approvals_factories
from tests.companies.factories import CompanyFactory, CompanyWithMembershipAndJobsFactory
from tests.employee_record import factories as employee_record_factories
from tests.employee_record.factories import EmployeeRecordFactory
from tests.job_applications.factories import JobApplicationWithApprovalNotCancellableFactory
from tests.utils.test import BASE_NUM_QUERIES, TestCase, assertMessages, parse_response_to_soup


@pytest.mark.usefixtures("unittest_compatibility")
class ListEmployeeRecordsTest(TestCase):
    URL = reverse_lazy("employee_record_views:list")

    def setUp(self):
        super().setUp()
        # User must be super user for UI first part (tmp)
        self.company = CompanyWithMembershipAndJobsFactory(name="Evil Corp.", membership__user__first_name="Elliot")
        self.company_without_perms = CompanyWithMembershipAndJobsFactory(
            kind="EITI", name="A-Team", membership__user__first_name="Hannibal"
        )
        self.user = self.company.members.get(first_name="Elliot")
        self.user_without_perms = self.company_without_perms.members.get(first_name="Hannibal")
        self.job_application = JobApplicationWithApprovalNotCancellableFactory(
            to_company=self.company,
            for_snapshot=True,
        )
        self.job_seeker = self.job_application.job_seeker

    def test_permissions(self):
        """
        Non-eligible SIAE should not be able to access this list
        """
        self.client.force_login(self.user_without_perms)

        response = self.client.get(self.URL)

        assert response.status_code == 403

    def test_new_employee_records(self):
        """
        Check if new employee records / job applications are displayed in the list
        """
        self.client.force_login(self.user)

        response = self.client.get(self.URL)

        self.assertContains(response, format_filters.format_approval_number(self.job_application.approval.number))

    def test_status_filter(self):
        """
        Check status filter
        """
        # No status defined
        self.client.force_login(self.user)
        approval_number_formatted = format_filters.format_approval_number(self.job_application.approval.number)

        response = self.client.get(self.URL)
        self.assertContains(response, approval_number_formatted)

        # Or NEW
        response = self.client.get(self.URL + "?status=NEW")
        self.assertContains(response, approval_number_formatted)

        # More complete tests to come with fixtures files
        for status in [Status.SENT, Status.REJECTED, Status.PROCESSED]:
            response = self.client.get(self.URL + f"?status={status.value}")
            self.assertNotContains(response, approval_number_formatted)

    def test_job_seeker_filter(self):
        approval_number_formatted = format_filters.format_approval_number(self.job_application.approval.number)
        other_job_application = JobApplicationWithApprovalNotCancellableFactory(to_company=self.company)
        other_approval_number_formatted = format_filters.format_approval_number(other_job_application.approval.number)
        self.client.force_login(self.user)

        response = self.client.get(self.URL)
        self.assertContains(response, approval_number_formatted)
        self.assertContains(response, other_approval_number_formatted)

        response = self.client.get(self.URL + f"?job_seekers={self.job_seeker.pk}")
        self.assertContains(response, approval_number_formatted)
        self.assertNotContains(response, other_approval_number_formatted)

        response = self.client.get(self.URL + "?job_seekers=0")
        self.assertContains(response, "Sélectionnez un choix valide. 0 n’en fait pas partie.")
        self.assertContains(response, approval_number_formatted)
        self.assertContains(response, other_approval_number_formatted)

    def test_employee_records_approval_display(self):
        self.client.force_login(self.user)
        approval = self.job_application.approval
        approval.start_at = datetime.date(2023, 9, 2)
        approval.end_at = datetime.date(2024, 10, 11)
        approval.save()

        response = self.client.get(self.URL)

        self.assertContains(response, "<small>Date de début</small><strong>02/09/2023</strong>", html=True)
        self.assertContains(
            response, "<small>Date prévisionnelle de fin</small><strong>11/10/2024</strong>", html=True
        )

    def test_employee_records_with_a_suspension_need_to_be_updated(self):
        self.client.force_login(self.user)
        approvals_factories.SuspensionFactory(
            approval=self.job_application.approval, siae=self.job_application.to_company
        )

        response = self.client.get(self.URL + "?status=NEW")

        # Global message alert
        assert str(parse_response_to_soup(response, selector=".s-title-01 .alert")) == self.snapshot(name="alert")

        # Item message alert
        assert str(
            parse_response_to_soup(
                response,
                selector=".employee-records-list .c-box--results__footer",
                replace_in_attr=[self.job_application],
            )
        ) == self.snapshot(name="action")

    def test_existing_employee_records_with_a_suspension_does_not_show_need_to_be_updated_message(self):
        self.client.force_login(self.user)
        employee_record = EmployeeRecordFactory(job_application=self.job_application)
        approvals_factories.SuspensionFactory(
            approval=self.job_application.approval, siae=self.job_application.to_company
        )

        response = self.client.get(self.URL + "?status=NEW")

        # Global message alert
        assertMessages(response, [])

        # Item message alert
        assert (
            str(
                parse_response_to_soup(
                    response,
                    selector=".employee-records-list .c-box--results__footer",
                    replace_in_attr=[self.job_application, employee_record],
                )
            )
            == self.snapshot()
        )

    def test_employee_records_with_a_prolongation_need_to_be_updated(self):
        self.client.force_login(self.user)
        approvals_factories.ProlongationFactory(
            approval=self.job_application.approval,
            declared_by_siae=self.job_application.to_company,
        )

        response = self.client.get(self.URL + "?status=NEW")

        # Global message alert
        assert str(parse_response_to_soup(response, selector=".s-title-01 .alert")) == self.snapshot(name="alert")
        # Item message alert
        assert str(
            parse_response_to_soup(
                response,
                selector=".employee-records-list .c-box--results__footer",
                replace_in_attr=[self.job_application],
            )
        ) == self.snapshot(name="action")

    def test_existing_employee_records_with_a_prolongation_does_not_show_need_to_be_updated_message(self):
        self.client.force_login(self.user)
        employee_record = EmployeeRecordFactory(job_application=self.job_application)
        approvals_factories.ProlongationFactory(
            approval=self.job_application.approval,
            declared_by_siae=self.job_application.to_company,
        )

        response = self.client.get(self.URL + "?status=NEW")

        # Global message alert
        assertMessages(response, [])
        # Item message alert
        assert (
            str(
                parse_response_to_soup(
                    response,
                    selector=".employee-records-list .c-box--results__footer",
                    replace_in_attr=[self.job_application, employee_record],
                )
            )
            == self.snapshot()
        )

    def test_employee_record_to_disable(self):
        self.client.force_login(self.user)
        employee_record = employee_record_factories.EmployeeRecordFactory(job_application=self.job_application)

        response = self.client.get(self.URL + "?status=NEW")

        assert (
            str(
                parse_response_to_soup(
                    response,
                    selector=".employee-records-list .c-box--results__footer",
                    replace_in_attr=[self.job_application, employee_record],
                )
            )
            == self.snapshot()
        )

    @override_settings(TALLY_URL="https://tally.so")
    def test_employee_records_with_nir_associated_to_other(self):
        self.client.force_login(self.user)
        self.job_seeker.jobseeker_profile.nir = ""
        self.job_seeker.jobseeker_profile.lack_of_nir_reason = LackOfNIRReason.NIR_ASSOCIATED_TO_OTHER
        self.job_seeker.jobseeker_profile.save(update_fields=("nir", "lack_of_nir_reason"))

        response = self.client.get(self.URL + "?status=NEW")

        self.assertContains(response, format_filters.format_approval_number(self.job_application.approval.number))
        # Global message alert
        assert str(parse_response_to_soup(response, selector=".s-title-01 .alert")) == self.snapshot(name="alert")
        # Item message alert
        assert str(
            parse_response_to_soup(
                response,
                selector=".employee-records-list .c-box--results__footer",
                replace_in_attr=[self.job_application],
            )
        ) == self.snapshot(name="action")

    @override_settings(TALLY_URL="https://tally.so")
    def test_employee_record_to_disable_with_nir_associated_to_other(self):
        self.client.force_login(self.user)
        self.job_seeker.jobseeker_profile.nir = ""
        self.job_seeker.jobseeker_profile.lack_of_nir_reason = LackOfNIRReason.NIR_ASSOCIATED_TO_OTHER
        self.job_seeker.jobseeker_profile.save(update_fields=("nir", "lack_of_nir_reason"))
        new_er = employee_record_factories.EmployeeRecordFactory(job_application=self.job_application)

        response = self.client.get(self.URL + "?status=NEW")

        self.assertContains(response, format_filters.format_approval_number(self.job_application.approval.number))
        # Global message alert
        assert str(parse_response_to_soup(response, selector=".s-title-01 .alert")) == self.snapshot(name="alert")
        # Item message alert
        assert str(
            parse_response_to_soup(
                response,
                selector=".employee-records-list .c-box--results__footer",
                replace_in_attr=[new_er],
            )
        ) == self.snapshot(name="action")

    def test_rejected_without_custom_message(self):
        self.client.force_login(self.user)

        record = employee_record_factories.EmployeeRecordWithProfileFactory(job_application__to_company=self.company)
        record.update_as_ready()
        record.update_as_sent(self.faker.asp_batch_filename(), 1, None)
        record.update_as_rejected("0012", "JSON Invalide", None)

        response = self.client.get(self.URL + "?status=REJECTED")
        self.assertContains(response, "Erreur 0012")
        self.assertContains(response, "JSON Invalide")

    def test_rejected_custom_messages(self):
        self.client.force_login(self.user)

        record = employee_record_factories.EmployeeRecordWithProfileFactory(job_application__to_company=self.company)

        tests_specs = [
            (
                "3308",
                "Le champ Commune de Naissance doit être en cohérence avec le champ Département de Naissance",
                "Il semblerait que la commune de naissance sélectionnée ne corresponde pas au département",
            ),
            (
                "3417",
                "Le code INSEE de la commune de l’adresse doit correspondre à un code INSEE de commune référencée",
                "La commune de résidence du salarié n’est pas référencée",
            ),
            (
                "3435",
                "L’annexe de la structure doit être à l’état Valide ou Provisoire",
                "Nous n’avons pas encore reçu d’annexe financière à jour pour votre structure.",
            ),
            (
                "3436",
                "Un PASS IAE doit être unique pour un même SIRET",
                "La fiche salarié associée à ce PASS IAE et à votre SIRET a déjà été intégrée à l’ASP.",
            ),
        ]
        for err_code, err_message, custom_err_message in tests_specs:
            with self.subTest(err_code):
                record.status = Status.SENT
                record.update_as_rejected(err_code, err_message, "{}")

                response = self.client.get(self.URL + "?status=REJECTED")
                self.assertContains(response, f"Erreur {err_code}")
                self.assertNotContains(response, err_message)
                self.assertContains(response, custom_err_message)

    def _check_employee_record_order(self, url, first_job_application, second_job_application):
        response = self.client.get(url)
        response_text = response.content.decode(response.charset)
        # The index method raises ValueError if the value isn't found
        first_job_seeker_position = response_text.index(
            format_filters.format_approval_number(first_job_application.approval.number)
        )
        second_job_seeker_position = response_text.index(
            format_filters.format_approval_number(second_job_application.approval.number)
        )
        assert first_job_seeker_position < second_job_seeker_position

    def test_new_employee_records_sorted(self):
        """
        Check if new employee records / job applications are correctly sorted
        """
        self.client.force_login(self.user)

        job_applicationA = JobApplicationWithApprovalNotCancellableFactory(
            to_company=self.company,
            job_seeker__last_name="Aaaaa",
            hiring_start_at=timezone.now() - relativedelta(days=15),
        )
        job_applicationZ = JobApplicationWithApprovalNotCancellableFactory(
            to_company=self.company,
            job_seeker__last_name="Zzzzz",
            hiring_start_at=timezone.now() - relativedelta(days=10),
        )

        # Zzzzz's hiring start is more recent
        self._check_employee_record_order(self.URL, job_applicationZ, job_applicationA)

        # order with -hiring_start_at is the default
        self._check_employee_record_order(self.URL + "?order=-hiring_start_at", job_applicationZ, job_applicationA)
        self._check_employee_record_order(self.URL + "?order=hiring_start_at", job_applicationA, job_applicationZ)

        # Zzzzz after Aaaaa
        self._check_employee_record_order(self.URL + "?order=name", job_applicationA, job_applicationZ)
        self._check_employee_record_order(self.URL + "?order=-name", job_applicationZ, job_applicationA)

        # Count queries
        num_queries = BASE_NUM_QUERIES
        num_queries += 1  # Get django session
        num_queries += 3  # Get current user and siae
        num_queries += 1  # Select job seeker for filters
        num_queries += 1  # Select employee_records status count
        num_queries += 1  # Lazy load of SIAE convention in `.eligible_as_employee_record()`
        num_queries += 1  # Select ordered job applications
        num_queries += 1  # Select EmployeeRecords
        with self.assertNumQueries(num_queries):
            self.client.get(self.URL)

    def test_rejected_employee_records_sorted(self):
        self.client.force_login(self.user)

        recordA = employee_record_factories.EmployeeRecordWithProfileFactory(
            job_application__to_company=self.company,
            job_application__job_seeker__last_name="Aaaaa",
            job_application__hiring_start_at=timezone.now() - relativedelta(days=15),
        )
        recordZ = employee_record_factories.EmployeeRecordWithProfileFactory(
            job_application__to_company=self.company,
            job_application__job_seeker__last_name="Zzzzz",
            job_application__hiring_start_at=timezone.now() - relativedelta(days=10),
        )
        for i, record in enumerate((recordA, recordZ)):
            record.update_as_ready()
            record.update_as_sent(f"RIAE_FS_2021041013000{i}.json", 1, None)
            record.update_as_rejected("0012", "JSON Invalide", None)

        # Zzzzz's hiring start is more recent
        self._check_employee_record_order(
            self.URL + "?status=REJECTED", recordZ.job_application, recordA.job_application
        )

        # order with -hiring_start_at is the default
        self._check_employee_record_order(
            self.URL + "?status=REJECTED&order=-hiring_start_at",
            recordZ.job_application,
            recordA.job_application,
        )
        self._check_employee_record_order(
            self.URL + "?status=REJECTED&order=hiring_start_at",
            recordA.job_application,
            recordZ.job_application,
        )

        # Zzzzz after Aaaaa
        self._check_employee_record_order(
            self.URL + "?status=REJECTED&order=name",
            recordA.job_application,
            recordZ.job_application,
        )
        self._check_employee_record_order(
            self.URL + "?status=REJECTED&order=-name",
            recordZ.job_application,
            recordA.job_application,
        )

    def test_ready_employee_records_sorted(self):
        self.client.force_login(self.user)

        recordA = employee_record_factories.EmployeeRecordWithProfileFactory(
            job_application__to_company=self.company,
            job_application__job_seeker__last_name="Aaaaa",
            job_application__hiring_start_at=timezone.now() - relativedelta(days=15),
        )
        recordZ = employee_record_factories.EmployeeRecordWithProfileFactory(
            job_application__to_company=self.company,
            job_application__job_seeker__last_name="Zzzzz",
            job_application__hiring_start_at=timezone.now() - relativedelta(days=10),
        )
        for record in (recordA, recordZ):
            record.update_as_ready()

        # Zzzzz's hiring start is more recent
        self._check_employee_record_order(self.URL + "?status=READY", recordZ.job_application, recordA.job_application)

        # order with -hiring_start_at is the default
        self._check_employee_record_order(
            self.URL + "?status=READY&order=-hiring_start_at",
            recordZ.job_application,
            recordA.job_application,
        )
        self._check_employee_record_order(
            self.URL + "?status=READY&order=hiring_start_at",
            recordA.job_application,
            recordZ.job_application,
        )

        # Zzzzz after Aaaaa
        self._check_employee_record_order(
            self.URL + "?status=READY&order=name",
            recordA.job_application,
            recordZ.job_application,
        )
        self._check_employee_record_order(
            self.URL + "?status=READY&order=-name",
            recordZ.job_application,
            recordA.job_application,
        )

    def test_display_result_count(self):
        self.client.force_login(self.user)
        response = self.client.get(self.URL + "?status=NEW")
        self.assertContains(response, "1 résultat")

        JobApplicationWithApprovalNotCancellableFactory(to_company=self.company)
        response = self.client.get(self.URL + "?status=NEW")
        self.assertContains(response, "2 résultats")

        response = self.client.get(self.URL + "?status=READY")
        self.assertContains(response, "0 résultat")


def test_an_active_siae_without_convention_can_not_access_the_view(client):
    siae = CompanyFactory(
        use_employee_record=True,
        source=Company.SOURCE_STAFF_CREATED,
        convention=None,
        with_membership=True,
    )
    client.force_login(siae.members.first())

    response = client.get(reverse("employee_record_views:list"))
    assert response.status_code == 403
