from urllib.parse import ParseResult, parse_qsl, urlparse

from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.safestring import mark_safe


def get_safe_url(request, param_name=None, fallback_url=None, url=None):
    url = url or request.GET.get(param_name) or request.POST.get(param_name)

    allowed_hosts = settings.ALLOWED_HOSTS
    require_https = request.is_secure()

    if url:
        if settings.DEBUG:
            # In DEBUG mode the network location part `127.0.0.1:8000` contains
            # a port and fails the validation of `url_has_allowed_host_and_scheme`
            # since it's not a member of `allowed_hosts`:
            # https://github.com/django/django/blob/525274f/django/utils/http.py#L413
            # As a quick fix, we build a new URL without the port.

            url_info = urlparse(url)
            url_without_port = ParseResult(
                scheme=url_info.scheme,
                netloc=url_info.hostname,
                path=url_info.path,
                params=url_info.params,
                query=url_info.query,
                fragment=url_info.fragment,
            ).geturl()
            if url_has_allowed_host_and_scheme(url_without_port, allowed_hosts, require_https):
                return url

        else:
            if url_has_allowed_host_and_scheme(url, allowed_hosts, require_https):
                return url

    return fallback_url


def get_absolute_url(path=""):
    if path.startswith("/"):
        path = path[1:]
    return f"{settings.ITOU_PROTOCOL}://{settings.ITOU_FQDN}/{path}"


def get_external_link_markup(url, text):
    return mark_safe(
        f'<a href="{url}" rel="noopener" target="_blank" aria-label="Ouverture dans un nouvel onglet">{text}</a>'
    )


def add_url_params(url: str, params: dict[str, str]) -> str:
    """Add GET params to provided URL being aware of existing.

    :param url: string of target URL
    :param params: dict containing requested params to be added
    :return: string with updated URL

    >> url = 'http://127.0.0.1:8000/login/activate_siae_staff_account?next_url=%2Finvitations
    >> new_params = {'test': 'value' }
    >> add_url_params(url, new_params)
    'http://127.0.0.1:8000/login/activate_siae_staff_account?next_url=%2Finvitations&test=value
    """

    # Remove params with None values
    params = {key: params[key] for key in params if params[key] is not None}
    url_parts = urlparse(url)
    query = dict(parse_qsl(url_parts.query))
    query.update(params)

    new_url = url_parts._replace(query=urlencode(query)).geturl()

    return new_url


class SiretConverter:
    """
    Custom path converter for Siret.
    https://docs.djangoproject.com/en/dev/topics/http/urls/#registering-custom-path-converters
    """

    regex = "[0-9]{14}"

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return f"{value}"


def get_tally_form_url(form_id, **kwargs):
    url = f"{settings.TALLY_URL}/r/{form_id}"

    if kwargs:
        url += "?" + urlencode(kwargs)

    return mark_safe(url)
