import pprint
from datetime import date
from time import sleep

from django.conf import settings
from django.core.management.base import BaseCommand
from httpx import HTTPStatusError

from itou.job_applications.models import JobApplication
from itou.siaes.models import Siae
from itou.utils.apis.esd import get_access_token
from itou.utils.apis.pole_emploi import (
    PoleEmploiIndividu,
    PoleEmploiMiseAJourPass,
    PoleEmploiMiseAJourPassIAEAPI,
    PoleEmploiRechercheIndividuCertifieAPI,
)


class Command(BaseCommand):
    """
    Performs a sample HTTP request to pole emploi

    When ready:
        django-admin fetch_pole_emploi --verbosity=2
    """

    help = "Test synchronizing sample user data stored by Pole Emploi"

    # The following sample users are provided by Pole Emploi.
    # Dependending on their category, we know what kind of error the API should provide.

    API_DATE_FORMAT = "%Y-%m-%d"

    def generate_sample_api_params(self, encrypted_identifier):
        approval_start_at = date(2021, 6, 1)
        approval_end_at = date(2021, 7, 1)
        approved_pass = "A"
        approval_number = "999992139048"
        siae_siret = "42373532300044"

        return {
            "idNational": encrypted_identifier,
            "statutReponsePassIAE": approved_pass,
            "typeSIAE": PoleEmploiMiseAJourPass.kind(Siae.KIND_EI),
            "dateDebutPassIAE": approval_start_at.strftime(self.API_DATE_FORMAT),
            "dateFinPassIAE": approval_end_at.strftime(self.API_DATE_FORMAT),
            "numPassIAE": approval_number,
            "numSIRETsiae": siae_siret,
            "origineCandidature": PoleEmploiMiseAJourPass.sender_kind(JobApplication.SENDER_KIND_JOB_SEEKER),
        }

    def is_dry_run(self, api_production_or_sandbox):
        return api_production_or_sandbox == PoleEmploiMiseAJourPassIAEAPI.USE_SANDBOX_ROUTE

    def get_token(self, api_production_or_sandbox):
        print("demande de token rechercherIndividuCertifie et MiseAJourPass")
        try:
            maj_pass_iae_api_scope = "passIAE api_maj-pass-iaev1"
            if self.is_dry_run(maj_pass_iae_api_scope):
                maj_pass_iae_api_scope = "passIAE api_testmaj-pass-iaev1"

            # It is not obvious but we can ask for one token only with all the necessary rights
            token_recherche_et_maj = get_access_token(
                f"api_rechercheindividucertifiev1 rechercherIndividuCertifie {maj_pass_iae_api_scope}"
            )
            sleep(1)
            return token_recherche_et_maj
        except HTTPStatusError as error:
            print(error.response.content)

    def get_pole_emploi_individual(self, individual, api_token):
        try:
            individual_pole_emploi = PoleEmploiRechercheIndividuCertifieAPI(individual, api_token)
            # 3 requests/second max. I had timeout issues so 1 second take some margins
            sleep(1)  #
            if not individual.is_valid:
                print(f"Error while fetching individual: {individual.code_sortie}")

            return individual_pole_emploi
        except HTTPStatusError as error:
            print(error.response.content)

    def dump_settings(self):
        print(f"API_ESD_AUTH_BASE_URL: {settings.API_ESD_AUTH_BASE_URL}")
        print(f"API_ESD_BASE_URL:      {settings.API_ESD_BASE_URL}")
        print(f"API_ESD_KEY:           {settings.API_ESD_KEY}")
        print(f"API_ESD_SECRET:        {settings.API_ESD_SECRET}")

    def synchronize_pass_iae(self):
        pp = pprint.PrettyPrinter(indent=4)
        self.dump_settings()
        # api_mode = PoleEmploiMiseAJourPassIAEAPI.USE_SANDBOX_ROUTE
        api_mode = PoleEmploiMiseAJourPassIAEAPI.USE_PRODUCTION_ROUTE
        token_recherche_et_maj = self.get_token(api_mode)
        individuals = [
            # (PoleEmploiIndividu("FARID", "ROCHDI", date(1968, 3, 3), "1680364445023"), 836, "PE"),
            (PoleEmploiIndividu("MARIA", "LOPES", date(1962, 5, 2), "2620599039619"), 837, "CAP_EMPLOI"),
            (PoleEmploiIndividu("CLAUDE", "CASTAGNAU", date(1965, 4, 12), "2650475114291"), 838, "ML"),
        ]

        for i in range(len(individuals)):
            individual, code_siae, code_prescripteur = individuals[i]

            individual_pole_emploi = self.get_pole_emploi_individual(individual, token_recherche_et_maj)
            print(individual.first_name, individual.last_name)
            print("on poste sur l’API rechercherIndividuCertifie")
            print(individual.as_api_params())
            print("retour d’API:")
            print(individual_pole_emploi.data)
            print()
            if individual_pole_emploi.is_valid:
                params = self.generate_sample_api_params(individual_pole_emploi.id_national_demandeur)
                params["typeSIAE"] = code_siae
                params["typologiePrescripteur"] = code_prescripteur
                pp.pprint(params)
                try:
                    print("on poste sur l’API MiseAJourPass")
                    maj = PoleEmploiMiseAJourPassIAEAPI(params, token_recherche_et_maj, api_mode)
                    # 1 request/second max, taking a bit of margin here due to occasionnal timeouts
                    sleep(1.5)
                    print(maj.data)

                except HTTPStatusError as error:
                    print(error.response.content)

                    print(individual.last_name)
                    print(maj.data)
        print()

    def handle(self, dry_run=False, **options):
        self.synchronize_pass_iae()
