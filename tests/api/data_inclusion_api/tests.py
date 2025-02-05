from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from itou.companies.enums import CompanyKind
from itou.companies.models import Company
from tests.companies.factories import CompanyFactory, SiaeConventionFactory
from tests.prescribers.factories import PrescriberOrganizationFactory
from tests.users.factories import EmployerFactory, PrescriberFactory
from tests.utils.test import BASE_NUM_QUERIES


def _str_with_tz(dt):
    return dt.astimezone(timezone.get_current_timezone()).isoformat()


NUM_QUERIES = BASE_NUM_QUERIES
NUM_QUERIES += 1  # count
NUM_QUERIES += 1  # get siae / organization


class DataInclusionStructureTest(APITestCase):
    maxDiff = None

    def test_list_missing_type_query_param(self):
        user = EmployerFactory()
        authenticated_client = APIClient()
        authenticated_client.force_authenticate(user)
        url = reverse("v1:structures-list")

        response = authenticated_client.get(url, format="json")
        assert response.status_code == 400


class DataInclusionSiaeStructureTest(APITestCase):
    url = reverse("v1:structures-list")
    maxDiff = None

    def setUp(self):
        super().setUp()
        self.user = EmployerFactory()
        self.client = APIClient()
        self.authenticated_client = APIClient()
        self.authenticated_client.force_authenticate(self.user)

    def test_list_structures_unauthenticated(self):
        response = self.client.get(self.url, format="json", data={"type": "siae"})
        assert response.status_code == 401

    def test_list_structures(self):
        company = CompanyFactory(siret="10000000000001")

        with self.assertNumQueries(NUM_QUERIES):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "siae"},
            )
        assert response.status_code == 200
        assert response.json()["results"] == [
            {
                "id": str(company.uid),
                "typologie": company.kind.value,
                "nom": company.display_name,
                "siret": company.siret,
                "rna": "",
                "presentation_resume": "",
                "presentation_detail": "",
                "site_web": company.website,
                "telephone": company.phone,
                "courriel": company.email,
                "code_postal": company.post_code,
                "code_insee": "",
                "commune": company.city,
                "adresse": company.address_line_1,
                "complement_adresse": company.address_line_2,
                "longitude": company.longitude,
                "latitude": company.latitude,
                "source": company.source,
                "date_maj": _str_with_tz(company.updated_at),
                "antenne": False,
                "lien_source": f"http://testserver{reverse('companies_views:card', kwargs={'siae_id': company.pk})}",
                "horaires_ouverture": "",
                "accessibilite": "",
                "labels_nationaux": [],
                "labels_autres": [],
                "thematiques": [],
            }
        ]

    def test_list_structures_antenne_with_user_created_with_proper_siret(self):
        company_1 = CompanyFactory(siret="10000000000001")
        company_2 = CompanyFactory(siret="10000000000002", convention=company_1.convention)
        company_2 = CompanyFactory(
            siret="10000000000003", source=Company.SOURCE_USER_CREATED, convention=company_1.convention
        )

        with self.assertNumQueries(NUM_QUERIES):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "siae"},
            )
            assert response.status_code == 200

        structure_data_list = response.json()["results"]

        for siae, siret, antenne in [
            (company_1, company_1.siret, False),
            (company_2, company_2.siret, False),
            # siae is user created, but it has its own siret
            # so it is not an antenne according to data.inclusion
            (company_2, company_2.siret, False),
        ]:
            structure_data = next(
                (structure_data for structure_data in structure_data_list if structure_data["id"] == str(siae.uid)),
                None,
            )
            with self.subTest(siret=siae.siret):
                assert structure_data is not None
                assert structure_data["siret"] == siret
                assert structure_data["antenne"] == antenne

    def test_list_structures_antenne_with_user_created_and_999(self):
        company_1 = CompanyFactory(siret="10000000000001")
        company_2 = CompanyFactory(siret="10000000000002", source=Company.SOURCE_ASP, convention=company_1.convention)
        company_3 = CompanyFactory(
            siret="10000000099991", source=Company.SOURCE_USER_CREATED, convention=company_1.convention
        )

        num_queries = NUM_QUERIES
        num_queries += 1  # get parent siae
        with self.assertNumQueries(num_queries):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "siae"},
            )
        assert response.status_code == 200

        structure_data_list = response.json()["results"]

        for siae, siret, antenne in [
            (company_1, company_1.siret, False),
            (company_2, company_2.siret, False),
            # siret is replaced with parent siret
            (company_3, company_1.siret, True),
        ]:
            structure_data = next(
                (structure_data for structure_data in structure_data_list if structure_data["id"] == str(siae.uid)),
                None,
            )
            with self.subTest(siret=siae.siret):
                assert structure_data is not None
                assert structure_data["siret"] == siret
                assert structure_data["antenne"] == antenne

    def test_list_structures_siret_with_999_and_no_other_siret_available(self):
        company = CompanyFactory(siret="10000000099991", source=Company.SOURCE_USER_CREATED)

        num_queries = NUM_QUERIES
        num_queries += 1  # get parent siae
        with self.assertNumQueries(num_queries):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "siae"},
            )
        assert response.status_code == 200

        structure_data_list = response.json()["results"]
        assert len(structure_data_list) == 1

        assert structure_data_list[0]["siret"] == company.siret[:9]  # fake nic is removed

    def test_list_structures_duplicated_siret(self):
        company_1 = CompanyFactory(siret="10000000000001", kind=CompanyKind.ACI)
        company_2 = CompanyFactory(siret=company_1.siret, kind=CompanyKind.EI)

        with self.assertNumQueries(NUM_QUERIES):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "siae"},
            )
        assert response.status_code == 200

        structure_data_list = response.json()["results"]

        for siae, siret, antenne in [
            # both structures will be marked as antennes, bc it is impossible to know
            # from data if one can be thought as an antenne of the other and if so, which
            # one is the antenne
            (company_1, company_1.siret, True),
            (company_2, company_2.siret, True),
        ]:
            structure_data = next(
                (structure_data for structure_data in structure_data_list if structure_data["id"] == str(siae.uid)),
                None,
            )
            with self.subTest(siret=siae.siret):
                assert structure_data is not None
                assert structure_data["siret"] == siret
                assert structure_data["antenne"] == antenne

    def test_list_structures_description_longer_than_280(self):
        company = CompanyFactory(description="a" * 300)

        with self.assertNumQueries(NUM_QUERIES):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "siae"},
            )

        assert response.status_code == 200
        structure_data = response.json()["results"][0]
        assert structure_data["presentation_resume"] == company.description[:279] + "…"
        assert structure_data["presentation_detail"] == company.description

    def test_list_structures_inactive_excluded(self):
        convention = SiaeConventionFactory(is_active=False)
        CompanyFactory(convention=convention)

        num_queries = NUM_QUERIES
        num_queries -= 1  # no siae to fetch
        with self.assertNumQueries(num_queries):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "siae"},
            )

        assert response.status_code == 200
        assert response.json()["results"] == []


class DataInclusionPrescriberStructureTest(APITestCase):
    url = reverse("v1:structures-list")
    maxDiff = None

    def setUp(self):
        super().setUp()
        self.user = PrescriberFactory()
        self.client = APIClient()
        self.authenticated_client = APIClient()
        self.authenticated_client.force_authenticate(self.user)

    def test_list_structures_unauthenticated(self):
        response = self.client.get(self.url, format="json", data={"type": "orga"})
        assert response.status_code == 401

    def test_list_structures(self):
        orga = PrescriberOrganizationFactory(is_authorized=True)

        with self.assertNumQueries(NUM_QUERIES):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "orga"},
            )
        assert response.status_code == 200
        assert response.json()["results"] == [
            {
                "id": str(orga.uid),
                "typologie": orga.kind.value,
                "nom": orga.name,
                "siret": orga.siret,
                "rna": "",
                "presentation_resume": "",
                "presentation_detail": "",
                "site_web": orga.website,
                "telephone": orga.phone,
                "courriel": orga.email,
                "code_postal": orga.post_code,
                "code_insee": "",
                "commune": orga.city,
                "adresse": orga.address_line_1,
                "complement_adresse": orga.address_line_2,
                "longitude": orga.longitude,
                "latitude": orga.latitude,
                "source": "",
                "date_maj": _str_with_tz(orga.updated_at),
                "antenne": False,
                "lien_source": f"http://testserver{reverse('prescribers_views:card', kwargs={'org_id': orga.pk})}",
                "horaires_ouverture": "",
                "accessibilite": "",
                "labels_nationaux": [],
                "labels_autres": [],
                "thematiques": [],
            }
        ]

    def test_list_structures_date_maj_value(self):
        orga = PrescriberOrganizationFactory()

        with self.assertNumQueries(NUM_QUERIES):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "orga"},
            )

        assert response.status_code == 200
        structure_data = response.json()["results"][0]
        assert structure_data["date_maj"] == _str_with_tz(orga.updated_at)

        orga.description = "lorem ipsum"
        orga.save()

        response = self.authenticated_client.get(
            self.url,
            format="json",
            data={"type": "orga"},
        )
        assert response.status_code == 200
        structure_data = response.json()["results"][0]
        assert structure_data["date_maj"] == _str_with_tz(orga.updated_at)

    def test_list_structures_description_longer_than_280(self):
        orga = PrescriberOrganizationFactory(description="a" * 300)

        with self.assertNumQueries(NUM_QUERIES):
            response = self.authenticated_client.get(
                self.url,
                format="json",
                data={"type": "orga"},
            )

        assert response.status_code == 200
        structure_data = response.json()["results"][0]
        assert structure_data["presentation_resume"] == orga.description[:279] + "…"
        assert structure_data["presentation_detail"] == orga.description
