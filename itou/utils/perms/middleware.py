from django.conf import settings


class ItouCurrentOrganizationMiddleware:
    """
    Store the SIRET of the current SIAE in session.
    https://docs.djangoproject.com/en/dev/topics/http/middleware/#writing-your-own-middleware
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Before the view is called.

        user = request.user

        if user.is_authenticated:

            if user.is_siae_staff:
                session_key = settings.ITOU_SESSION_CURRENT_SIAE_KEY
                if not request.session.get(session_key):
                    request.session[session_key] = user.siae_set.first().siret

        response = self.get_response(request)

        # After the view is called.

        return response
