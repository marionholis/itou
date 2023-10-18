from datetime import datetime

from django.db.models import F, Q, Value
from django.db.models.functions import Least, Lower, NullIf, StrIndex
from django.http import JsonResponse
from unidecode import unidecode

from itou.asp.models import Commune
from itou.cities.models import City
from itou.jobs.models import Appellation


# Consider that after 50 matches the user should refine its search.
MAX_CITIES_TO_RETURN = 50


def autocomplete_name(qs, term, extra_ordering_by):
    term = unidecode(term.lower())
    term_spaced = term.replace("-", " ")
    term_hyphenated = term.replace(" ", "-")
    # We started with a trigram similarity and word similarity approach. It is disappointing
    # since it does return results that are not expected, for instance results containing
    # letters not present in the search.
    # It has been decided with the UX to use the simplest approach. It seems that most
    # people look for a city by "the start of the name", not by "any word within the name"
    # so the icontains lookup, ordered by index of the matching string, feels more natural.
    # The hyphenated/unhyphenated thing has been added considering the mess that hyphens
    # represent in french city names. It should be improved in the future to handle cases
    # such as search terms “La Chapelle du” not finding La Chapelle-du-Châtelard.

    return (
        qs.filter(Q(name__unaccent__icontains=term_spaced) | Q(name__unaccent__icontains=term_hyphenated))
        .annotate(
            spaced_index=NullIf(StrIndex(Lower("name__unaccent"), Value(term_spaced)), 0),
            hyphenated_index=NullIf(StrIndex(Lower("name__unaccent"), Value(term_hyphenated)), 0),
            best_index=Least(F("spaced_index"), F("hyphenated_index")),
        )
        .order_by(F("best_index").asc(nulls_last=True), "name", extra_ordering_by)
    )


def cities_autocomplete(request):
    """
    Returns JSON data compliant with the jQuery UI Autocomplete Widget:
    https://api.jqueryui.com/autocomplete/#option-source
    """

    term = request.GET.get("term", "").strip()
    cities = []

    if term:
        if term.isdigit():
            cities = City.objects.filter(post_codes__contains=[term]).order_by("name", "department")
        else:
            cities = autocomplete_name(City.objects.all(), term, extra_ordering_by="department")

        cities = [{"value": city.display_name, "slug": city.slug} for city in cities[:MAX_CITIES_TO_RETURN]]

    return JsonResponse(cities, safe=False)


def jobs_autocomplete(request):
    """
    Returns JSON data compliant with either the jQuery UI Autocomplete Widget or Select2
    """

    term = request.GET.get("term", "").strip()
    # TODO(xfernandez): drop legacy support in a few weeks and only keep select2 mode
    select2_mode = "select2" in request.GET
    appellations = []

    if term:
        if select2_mode:
            appellations = [
                {
                    "text": f"{appellation.name} ({appellation.rome.code})",
                    "id": appellation.pk,
                }
                for appellation in Appellation.objects.autocomplete(term, limit=10)
            ]
        else:
            appellations = [
                {
                    "value": f"{appellation.name} ({appellation.rome.code})",
                    "code": appellation.code,
                    "rome": appellation.rome.code,
                    "name": appellation.name,
                }
                for appellation in Appellation.objects.autocomplete(term, limit=10)
            ]

    return JsonResponse({"results": appellations} if select2_mode else appellations, safe=False)


def communes_autocomplete(request):
    """
    Autocomplete endpoint for INSEE communes (ASP ref. files)

    Slight variation : a `date` parameter is sent with search term
    in order to get valid INSEE codes (with this date within a period between
    commune.start_date and commune.end_date)

    Returns JSON data compliant with the jQuery UI Autocomplete Widget:
    https://api.jqueryui.com/autocomplete/#option-source
    """
    communes = []
    term = request.GET.get("term", "").strip()

    try:
        dt = datetime.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        # Can't extract date in ISO format: use today as fallback
        dt = datetime.now()

    active_communes_qs = Commune.objects.filter(start_date__lte=dt).filter(Q(end_date=None) | Q(end_date__gt=dt))
    if term:
        if term.isdigit():
            communes = active_communes_qs.filter(code__startswith=term).order_by("name", "code")
        else:
            communes = autocomplete_name(active_communes_qs, term, extra_ordering_by="code")

        communes = [
            {
                "value": f"{commune.name} ({commune.department_code})",
                "code": commune.code,
                "department": commune.department_code,
            }
            for commune in communes[:MAX_CITIES_TO_RETURN]
        ]

    return JsonResponse(communes, safe=False)
