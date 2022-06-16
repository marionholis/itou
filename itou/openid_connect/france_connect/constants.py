import datetime

from django.conf import settings


FRANCE_CONNECT_SCOPES = "openid gender given_name family_name email birthdate birthplace birthcountry"

FRANCE_CONNECT_ENDPOINT_AUTHORIZE = f"{settings.FRANCE_CONNECT_BASE_URL}/authorize"
FRANCE_CONNECT_ENDPOINT_TOKEN = f"{settings.FRANCE_CONNECT_BASE_URL}/token"
FRANCE_CONNECT_ENDPOINT_USERINFO = f"{settings.FRANCE_CONNECT_BASE_URL}/userinfo"
FRANCE_CONNECT_ENDPOINT_LOGOUT = f"{settings.FRANCE_CONNECT_BASE_URL}/logout"

FRANCE_CONNECT_STATE_EXPIRATION = datetime.timedelta(hours=1)

FRANCE_CONNECT_SESSION_TOKEN = "FC_ID_TOKEN"
FRANCE_CONNECT_SESSION_STATE = "FC_STATE"
