import functools
from datetime import date, timedelta
from functools import partial
from operator import attrgetter

from django.utils import timezone

from itou.eligibility.models import AdministrativeCriteria, EligibilityDiagnosis
from itou.job_applications.models import JobApplicationWorkflow
from itou.metabase.management.commands._utils import (
    MetabaseTable,
    get_ai_stock_job_seeker_pks,
    get_choice,
    get_department_and_region_columns,
    get_hiring_siae,
    hash_content,
)
from itou.users.models import User


# Reword the original EligibilityDiagnosis.AUTHOR_KIND_CHOICES
AUTHOR_KIND_CHOICES = (
    (EligibilityDiagnosis.AUTHOR_KIND_PRESCRIBER, "Prescripteur"),
    (EligibilityDiagnosis.AUTHOR_KIND_SIAE_STAFF, "Employeur"),
)


def get_user_age_in_years(user):
    if user.birthdate:
        return date.today().year - user.birthdate.year
    return None


def get_user_signup_kind(user):
    creator = user.created_by
    if creator is None:
        return "autonome"
    if creator.is_prescriber:
        return "par prescripteur"
    if creator.is_siae_staff:
        return "par employeur"
    raise ValueError("Unexpected job seeker creator kind")


def get_latest_diagnosis(job_seeker):
    assert job_seeker.is_job_seeker
    if job_seeker.eligibility_diagnoses.count() == 0:
        return None
    return max(job_seeker.eligibility_diagnoses.all(), key=attrgetter("created_at"))


def get_latest_diagnosis_author_sub_kind(job_seeker):
    """
    Build a human readable sub category, e.g.
    - Employeur ACI
    - Employeur ETTI
    - Prescripteur PE
    - Prescripteur ML
    """
    latest_diagnosis = get_latest_diagnosis(job_seeker)
    if latest_diagnosis:
        author_kind = get_choice(choices=AUTHOR_KIND_CHOICES, key=latest_diagnosis.author_kind)
        author_sub_kind = None
        if (
            latest_diagnosis.author_kind == EligibilityDiagnosis.AUTHOR_KIND_SIAE_STAFF
            and latest_diagnosis.author_siae
        ):
            author_sub_kind = latest_diagnosis.author_siae.kind
        elif (
            latest_diagnosis.author_kind == EligibilityDiagnosis.AUTHOR_KIND_PRESCRIBER
            and latest_diagnosis.author_prescriber_organization
        ):
            author_sub_kind = latest_diagnosis.author_prescriber_organization.kind
        return f"{author_kind} {author_sub_kind}"
    return None


def get_latest_diagnosis_author_display_name(job_seeker):
    latest_diagnosis = get_latest_diagnosis(job_seeker)
    if latest_diagnosis:
        if (
            latest_diagnosis.author_kind == EligibilityDiagnosis.AUTHOR_KIND_SIAE_STAFF
            and latest_diagnosis.author_siae
        ):
            return latest_diagnosis.author_siae.display_name
        elif (
            latest_diagnosis.author_kind == EligibilityDiagnosis.AUTHOR_KIND_PRESCRIBER
            and latest_diagnosis.author_prescriber_organization
        ):
            return latest_diagnosis.author_prescriber_organization.display_name
    return None


def _get_latest_diagnosis_criteria_by_level(job_seeker, level):
    """
    Count criteria of given level for the latest diagnosis of
    given job seeker.
    """
    latest_diagnosis = get_latest_diagnosis(job_seeker)
    if latest_diagnosis:
        # We have to do all this in python to benefit from prefetch_related.
        return len([ac for ac in latest_diagnosis.administrative_criteria.all() if ac.level == level])
    return None


def get_latest_diagnosis_level1_criteria(job_seeker):
    return _get_latest_diagnosis_criteria_by_level(job_seeker=job_seeker, level=AdministrativeCriteria.Level.LEVEL_1)


def get_latest_diagnosis_level2_criteria(job_seeker):
    return _get_latest_diagnosis_criteria_by_level(job_seeker=job_seeker, level=AdministrativeCriteria.Level.LEVEL_2)


def get_latest_diagnosis_criteria(job_seeker, criteria_id):
    """
    Check if given criteria_id is actually present in latest diagnosis
    of given job seeker.

    Return 1 if present, 0 if absent and None if there is no diagnosis.
    """
    latest_diagnosis = get_latest_diagnosis(job_seeker)
    if latest_diagnosis:
        # We have to do all this in python to benefit from prefetch_related.
        return len([ac for ac in latest_diagnosis.administrative_criteria.all() if ac.id == criteria_id])
    return None


def _format_criteria_name_as_column_comment(criteria):
    column_comment = (
        criteria.name.replace("'", " ")
        .replace(",", "")
        .replace("12-24", "12 à 24")
        .replace("+", "plus de ")
        .replace("-", "moins de ")
        .strip()
    )
    # Deduplicate consecutive spaces.
    column_comment = " ".join(column_comment.split())
    return column_comment


def format_criteria_name_as_column_name(criteria):
    column_comment = _format_criteria_name_as_column_comment(criteria)
    column_name = column_comment.replace("(", "").replace(")", "").replace(" ", "_").lower()
    return f"critère_n{criteria.level}_{column_name}"


def get_gender_from_nir(job_seeker):
    if job_seeker.nir:
        match job_seeker.nir[0]:
            case "1":
                return "Homme"
            case "2":
                return "Femme"
            case _:
                raise ValueError("Unexpected NIR first digit")
    return None


def get_birth_year_from_nir(job_seeker):
    if job_seeker.nir:
        # It will be our data analysts' job to decide whether `05` means `1905` or `2005`.
        birth_year = int(job_seeker.nir[1:3])
        return birth_year
    return None


def get_birth_month_from_nir(job_seeker):
    if job_seeker.nir:
        birth_month = int(job_seeker.nir[3:5])
        if not 1 <= birth_month <= 12:
            # Exotic values means the birth month is unknown, as the 31-42 range was never observed in our data.
            # https://fr.wikipedia.org/wiki/Num%C3%A9ro_de_s%C3%A9curit%C3%A9_sociale_en_France#ancrage_B
            birth_month = 0
        return birth_month
    return None


@functools.cache
def _get_qpv_job_seeker_pks():
    """
    Load once and for all the list of all job seeker pks which are located in a QPV zone.

    The alternative would have been to naively compute `QPV.in_qpv(u, geom_field="coords")` for each and every one
    of the ~700k job seekers, which would have resulted in a undesirable deluge of 700k micro SQL requests.

    Unfortunately we failed so far at finding a clean ORM friendly way to do this in a single SQL request.
    """
    qpv_job_seekers = User.objects.raw(
        # Takes only ~2s on local dev.
        "SELECT uu.id FROM users_user uu INNER JOIN geo_qpv gq ON ST_Contains(gq.geometry, uu.coords::geometry)"
    )
    # A list of ~100k integers is permanently loaded in memory. It is fortunately not a very high volume of data.
    # Objects returned by `raw` are defered which means their fields are not preloaded unless they have been
    # explicitely specified in the SQL request. We did specify and thus preload `id` fields.
    return [job_seeker.pk for job_seeker in qpv_job_seekers]


def get_job_seeker_qpv_info(job_seeker):
    if not job_seeker.coords or job_seeker.geocoding_score < 0.8:
        # Under this geocoding score, we can't assert the quality of the QPV information.
        return "Adresse non-géolocalisée"
    if job_seeker.pk in _get_qpv_job_seeker_pks():
        return "Adresse en QPV"
    return "Adresse hors QPV"


TABLE = MetabaseTable(name="candidats")
TABLE.add_columns(
    [
        {
            "name": "id_anonymisé",
            "type": "varchar",
            "comment": "ID anonymisé du candidat",
            "fn": lambda o: hash_content(o.id),
        },
        {
            "name": "hash_nir",
            "type": "varchar",
            "comment": "Version obfusquée du NIR",
            "fn": lambda o: hash_content(o.nir) if o.nir else None,
        },
        {
            "name": "sexe_selon_nir",
            "type": "varchar",
            "comment": "Sexe du candidat selon le NIR",
            "fn": get_gender_from_nir,
        },
        {
            "name": "annee_naissance_selon_nir",
            "type": "integer",
            "comment": "Année de naissance du candidat selon le NIR",
            "fn": get_birth_year_from_nir,
        },
        {
            "name": "mois_naissance_selon_nir",
            "type": "integer",
            "comment": "Mois de naissance du candidat selon le NIR",
            "fn": get_birth_month_from_nir,
        },
        {"name": "age", "type": "integer", "comment": "Age du candidat en années", "fn": get_user_age_in_years},
        {
            "name": "date_inscription",
            "type": "date",
            "comment": "Date inscription du candidat",
            "fn": lambda o: o.date_joined,
        },
        {
            "name": "type_inscription",
            "type": "varchar",
            "comment": "Type inscription du candidat",
            "fn": get_user_signup_kind,
        },
        {
            "name": "pe_connect",
            "type": "boolean",
            "comment": "Le candidat utilise PE Connect",
            "fn": lambda o: o.is_peamu,
        },
        {
            "name": "pe_inscrit",
            "type": "boolean",
            "comment": "Le candidat a un identifiant PE",
            "fn": lambda o: o.pole_emploi_id is not None and o.pole_emploi_id != "",
        },
        {
            "name": "date_dernière_connexion",
            "type": "date",
            "comment": "Date de dernière connexion au service du candidat",
            "fn": lambda o: o.last_login,
        },
        {
            "name": "actif",
            "type": "boolean",
            "comment": "Dernière connexion dans les 7 jours",
            "fn": lambda o: o.last_login > timezone.now() + timedelta(days=-7) if o.last_login else False,
        },
    ]
)

TABLE.add_columns(get_department_and_region_columns(comment_suffix=" du candidat"))

TABLE.add_columns(
    [
        {
            "name": "adresse_en_qpv",
            "type": "varchar",
            "comment": "Analyse QPV sur adresse du candidat",
            "fn": get_job_seeker_qpv_info,
        },
        {
            "name": "total_candidatures",
            "type": "integer",
            "comment": "Nombre de candidatures",
            "fn": lambda o: o.job_applications.count(),
        },
        {
            "name": "total_embauches",
            "type": "integer",
            "comment": "Nombre de candidatures de type accepté",
            # We have to do all this in python to benefit from prefetch_related.
            "fn": lambda o: len(
                [ja for ja in o.job_applications.all() if ja.state == JobApplicationWorkflow.STATE_ACCEPTED]
            ),
        },
        {
            "name": "total_diagnostics",
            "type": "integer",
            "comment": "Nombre de diagnostics",
            "fn": lambda o: o.eligibility_diagnoses.count(),
        },
        {
            "name": "date_diagnostic",
            "type": "date",
            "comment": "Date du dernier diagnostic",
            "fn": lambda o: getattr(get_latest_diagnosis(o), "created_at", None),
        },
        {
            "name": "id_auteur_diagnostic_prescripteur",
            "type": "integer",
            "comment": "ID auteur diagnostic si prescripteur",
            "fn": lambda o: get_latest_diagnosis(o).author_prescriber_organization.id
            if get_latest_diagnosis(o)
            and get_latest_diagnosis(o).author_kind == EligibilityDiagnosis.AUTHOR_KIND_PRESCRIBER
            and get_latest_diagnosis(o).author_prescriber_organization
            else None,
        },
        {
            "name": "id_auteur_diagnostic_employeur",
            "type": "integer",
            "comment": "ID auteur diagnostic si employeur",
            "fn": lambda o: get_latest_diagnosis(o).author_siae.id
            if get_latest_diagnosis(o)
            and get_latest_diagnosis(o).author_kind == EligibilityDiagnosis.AUTHOR_KIND_SIAE_STAFF
            and get_latest_diagnosis(o).author_siae
            else None,
        },
        {
            "name": "type_auteur_diagnostic",
            "type": "varchar",
            "comment": "Type auteur du dernier diagnostic",
            "fn": lambda o: get_choice(choices=AUTHOR_KIND_CHOICES, key=get_latest_diagnosis(o).author_kind)
            if get_latest_diagnosis(o)
            else None,
        },
        {
            "name": "sous_type_auteur_diagnostic",
            "type": "varchar",
            "comment": "Sous type auteur du dernier diagnostic",
            "fn": get_latest_diagnosis_author_sub_kind,
        },
        {
            "name": "nom_auteur_diagnostic",
            "type": "varchar",
            "comment": "Nom auteur du dernier diagnostic",
            "fn": get_latest_diagnosis_author_display_name,
        },
        {
            "name": "type_structure_dernière_embauche",
            "type": "varchar",
            "comment": "Type de la structure destinataire de la dernière embauche du candidat",
            "fn": lambda o: get_hiring_siae(o).kind if get_hiring_siae(o) else None,
        },
        {
            "name": "total_critères_niveau_1",
            "type": "integer",
            "comment": "Total critères de niveau 1 du dernier diagnostic",
            "fn": get_latest_diagnosis_level1_criteria,
        },
        {
            "name": "total_critères_niveau_2",
            "type": "integer",
            "comment": "Total critères de niveau 2 du dernier diagnostic",
            "fn": get_latest_diagnosis_level2_criteria,
        },
    ]
)


# Add one column for each of the 15 criteria.
for criteria in AdministrativeCriteria.objects.order_by("id").all():
    column_comment = _format_criteria_name_as_column_comment(criteria)
    column_name = format_criteria_name_as_column_name(criteria)

    TABLE.add_columns(
        [
            {
                "name": column_name,
                "type": "boolean",
                "comment": f"Critère {column_comment} (niveau {criteria.level})",
                "fn": partial(get_latest_diagnosis_criteria, criteria_id=criteria.id),
            }
        ]
    )

TABLE.add_columns(
    [
        {
            "name": "injection_ai",
            "type": "boolean",
            "comment": "Provient des injections AI",
            # Here we flag job seekers as soon as any of their approvals is from the AI stock.
            # In theory we should only flag them when their latest approval `o.approvals_wrapper.latest_approval`
            # matches, but the performance becomes terrible (e.g. 120 minutes vs 30 minutes), is not easy to fix due
            # to how `approvals_wrapper.latest_approval` is implemented and gives the exact same end result
            # anyway (71205 users), most likely since most if not all of these users only have a single approval
            # anyway.
            # FIXME(vperron): It would be interesting to test again now though.
            "fn": lambda o: o.pk in get_ai_stock_job_seeker_pks(),
        },
    ]
)
