import asyncio
import logging

import requests
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.dateparse import parse_datetime

from itou.external_data.models import ExternalDataImport, JobSeekerExternalData


# PE Connect API data retrieval tools

API_ESD_BASE_URL = settings.API_ESD_BASE_URL

ESD_USERINFO_API = "peconnect-individu/v1/userinfo"
ESD_COORDS_API = "peconnect-coordonnees/v1/coordonnees"
ESD_STATUS_API = "peconnect-statut/v1/statut"
ESD_BIRTHDATE_API = "peconnect-datenaissance/v1/etat-civil"

# FIXME: not registered yet
ESD_COMPENSATION_API = "peconnect-indemnisations/v1/indemnisation"
ESD_PT_TRAININGS_API = "peconnect-formations/v1/formations"
ESD_PT_LICENSES_API = "peconnect-formations/v1/permits"

# Internal ----

logger = logging.getLogger(__name__)


# This part may be refactored with the processing of other APIs
# YAGNI at the moment


def _call_api(api_path, token):
    """ 
    Make a sync call to an API
    For further processing, returning smth else than `None` if considered a success
    """
    url = f"{API_ESD_BASE_URL}/{api_path}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 200:
        result = resp.json()
        # logger.debug(f"CALL {url}: {result}")
        return result
    else:
        # Track it for QoS
        logger.warning(f"API call to: {url} returned status code {resp.status_code}")
        return None


def _fields_or_failed(result, keys):
    if not result:
        return None
    else:
        return {k: v for k, v in result.items() if k in keys}


def _get_userinfo(token):
    """
    Get main info from user:
        * first and family names
        * gender
        * email address

    See: https://www.emploi-store-dev.fr/portail-developpeur-cms/home/catalogue-des-api/documentation-des-api/api/api-pole-emploi-connect/api-peconnect-individu-v1.html

    """
    # Fields of interest
    keys = ["given_name", "family_name", "gender", "email"]
    return _fields_or_failed(_call_api(ESD_USERINFO_API, token), keys)


def _get_birthdate(token):
    """
    Get birthdate of user (format `YYYY-MM-DDTHH:MM:SSZ`), converted as `datetime` object.

    See: https://www.emploi-store-dev.fr/portail-developpeur-cms/home/catalogue-des-api/documentation-des-api/api/api-pole-emploi-connect/api-peconnect-datenaissance-v1.html

    """
    key = "dateDeNaissance"
    # code, resp = _call_api(ESD_BIRTHDATE_API, token)
    result = _fields_or_failed(_call_api(ESD_BIRTHDATE_API, token), [key])
    if result:
        return {key: result.get(key)}
    else:
        return None


def _get_status(token):
    """
    Get current status of candidate.

    Returns a dict with codeStatutIndividu field from API:
        * 0: does not seek a job
        * 1: active jobseeker

    See: https://www.emploi-store-dev.fr/portail-developpeur-cms/home/catalogue-des-api/documentation-des-api/api/api-pole-emploi-connect/api-peconnect-statut-v1.html
    """
    key = "codeStatutIndividu"
    result = _fields_or_failed(_call_api(ESD_STATUS_API, token), [key])
    if result:
        code = result.get(key)
        return {key: int(code)}
    else:
        return None


def _get_address(token):
    """
    Get current address of the candidate:

    Returns a dict with fields:
        * adresse1
        * adresse2
        * adresse3
        * adresse4
        * codePostal
        * codeINSEE
        * libelleCommune

    Does not return country related fields (only France ATM)

    See: https://www.emploi-store-dev.fr/portail-developpeur-cms/home/catalogue-des-api/documentation-des-api/api/api-pole-emploi-connect/api-peconnect-coordonnees-v1.html
    """
    keys = ["adresse1", "adresse2", "adresse3", "adresse4", "codePostal", "codeINSEE", "libelleCommune"]
    return _fields_or_failed(_call_api(ESD_COORDS_API, token), keys)


def _get_compensations(token):
    """
    Get user "compensations" (social allowance):

    Return a dict with fields:
        * beneficiairePrestationSolidarite (has one or more of AER, AAH, ASS, RSA)
        * beneficiaireAssuranceChomage (has ARE or ASP)

    See: https://www.emploi-store-dev.fr/portail-developpeur-cms/home/catalogue-des-api/documentation-des-api/api/api-pole-emploi-connect/api-indemnisations-v1.html
    """
    keys = ["beneficiairePrestationSolidarite", "beneficiaireAssuranceChomage"]
    return _fields_or_failed(_call_api(ESD_COMPENSATION_API, token), keys)


def _get_aggregated_user_data(token):
    """
    Aggregates all needed user data before formatting and storage.
    Returns a pair status and a "flat" dict.
    """
    # Include API results "à volonté"
    results = [
        _get_userinfo(token),
        _get_birthdate(token),
        _get_status(token),
        _get_address(token),
        _get_compensations(token),
    ]

    ok = all(results)
    partial = not ok and any(results)
    cleaned_results = [part for part in results if part]

    if ok:
        status = ExternalDataImport.STATUS_OK
    elif partial:
        status = ExternalDataImport.STATUS_PARTIAL
    else:
        status = ExternalDataImport.STATUS_FAILED

    resp = {}
    for result in cleaned_results:
        resp.update(result)

    return status, resp


def _model_fields_changed(initial, final_instance):
    """
    Return an array with fields of the model_instance object that will be changed on `save()`
    """
    final = model_to_dict(final_instance)
    class_name = type(final_instance).__name__
    return [f"{class_name}/{final_instance.pk}/{k}" for k, v in initial.items() if v != final.get(k)]


# External user data from PE Connect API:
# * transform raw data from API
# * dispatch data into models if possible
# * or store as key / value if needed


def _store_user_data(user, status, data):
    """
    Store user data and produce a "report" containing a JSON object, with these fields:
        - fields_fetched (array): successfully imported field names
        - fields_failed (array): fields that could not be fetched (API error...)
        - fields_updated (array): updated fields in the db each of form: `class_name/pk/field_name` (f.i. `User/10/birthdate`)

    Return a ExternalDataImport object containing outcome of the data import
    """
    # Set a trace of data import, whatever the resulting status
    data_import = user.externaldataimport_set.pe_imports().first()

    fields_fetched = [k for k, v in data.items() if v is not None]
    fields_failed = [k for k, v in data.items() if v is None]

    job_seeker_data = JobSeekerExternalData(user=user, data_import=data_import)

    # Record changes on model objects:
    initial_job_seekeer_data = model_to_dict(job_seeker_data)
    initial_user = model_to_dict(user)

    for k in fields_fetched:
        v = data.get(k)

        # User part:
        if k == "dateDeNaissance":
            user.birthdate = user.birthdate or parse_datetime(v)
        elif k == "adresse4":
            user.address_line_1 = "" or user.address_line_1 or v
        elif k == "adresse2":
            user.address_line_2 = "" or user.address_line_2 or v
        elif k == "codePostal":
            user.post_code = user.post_code or v
        elif k == "libelleCommune":
            user.city = user.city or v

        # JobSeekerExternalData part:
        if k == "codeStatutIndividu":
            job_seeker_data.is_pe_jobseeker = True if v == 1 else False
        elif k == "beneficiairePrestationSolidarite":
            job_seeker_data.has_minimal_social_allowance = v

    # Check updated fields
    # To be done before saving objects:
    fields_updated = _model_fields_changed(initial_user, user) + _model_fields_changed(
        initial_job_seekeer_data, job_seeker_data
    )

    user.save()
    job_seeker_data.save()

    report = {"fields_fetched": fields_fetched, "fields_failed": fields_failed, "fields_updated": fields_updated}

    data_import.status = status
    data_import.report = report
    data_import.save()

    return data_import


#  Public ----

# Experimental:
# * logs will be truncated (per thread writing, will not work simply with async)
#
async def async_import_user_data(user, token):
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, import_user_data, user, token)


def import_user_data(user, token):
    """
    Import external user data via PE Connect
    Returns a valid ExternalDataImport object when result is partial or ok.
    """
    # Create a new import with a pending status (will be async)
    data_import = user.externaldataimport_set.pe_imports().first() or ExternalDataImport(
        source=ExternalDataImport.DATA_SOURCE_PE_CONNECT, user=user
    )
    data_import.status = ExternalDataImport.STATUS_PENDING
    data_import.save()

    try:
        status, result = _get_aggregated_user_data(token)
        data_import = _store_user_data(user, status, result)

        # At the moment, results are stored only if OK
        if status == ExternalDataImport.STATUS_OK:
            logger.info(f"Stored external data for user {user}")
        elif status == ExternalDataImport.STATUS_PARTIAL:
            logger.warning(f"Could only fetch partial results for {user}")
        else:
            logger.error(f"Could not fetch any data for {user}: not data stored")
    except Exception as ex:
        logger.error(f"Data import for {user} failed: {ex}")
        data_import.status = ExternalDataImport.STATUS_FAILED
        data_import.save()

    return data_import
