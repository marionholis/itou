from django.conf import settings
from rest_framework import authentication, generics

from itou.api import AUTH_TOKEN_EXPLANATION_TEXT
from itou.users.enums import UserKind
from itou.users.models import User

from .perms import ApplicantsAPIPermission
from .serializers import ApplicantSerializer


class ApplicantsView(generics.ListAPIView):
    authentication_classes = (
        authentication.TokenAuthentication,
        authentication.SessionAuthentication,
    )
    permission_classes = (ApplicantsAPIPermission,)
    serializer_class = ApplicantSerializer

    def get_queryset(self):
        multi_companies_mode = bool(self.request.query_params.get("mode_multi_structures")) is True
        companies_uids_params = self.request.query_params.get("uid_structures")
        memberships = (
            self.request.user.active_or_in_grace_period_company_memberships()
            .order_by("created_at")
            .values("company_id", "company__uid")
        )
        if companies_uids_params:
            companies_uids_params = companies_uids_params.split(",")
            companies_ids = [
                membership["company_id"]
                for membership in memberships
                if str(membership["company__uid"]) in companies_uids_params
            ]
        else:
            companies_ids = [membership["company_id"] for membership in memberships]

        if not multi_companies_mode and not companies_uids_params:
            # Legacy behaviour.
            # Return the first membership available.
            companies_ids = companies_ids[:1]

        return (
            User.objects.filter(job_applications__to_company_id__in=companies_ids, kind=UserKind.JOB_SEEKER)
            .select_related("jobseeker_profile__birth_place", "jobseeker_profile__birth_country")
            .distinct()
            .order_by("-pk")
        )


ApplicantsView.__doc__ = f"""\
# Liste des candidats par structure

Cette API retourne la liste de tous les demandeurs d'emploi liés aux candidatures reçues par
la ou les structure(s) sélectionnée(s).

Les candidats sont triés par date de création dans la base des emplois de l'inclusion,
du plus récent au plus ancien.

# Permissions

L'utilisation de cette API nécessite un jeton d'autorisation (`token`) :

{AUTH_TOKEN_EXPLANATION_TEXT}

Le compte administrateur utilisé peut être membre d'une ou de plusieurs structures.
Par défaut, l'API renvoie les candidatures reçues par la première structure dont le compte est membre
car la première version avait été pensée ainsi.

# Paramètres

- mode_multi_structures : renvoie les candidats de toutes les structures.
- uid_structures : renvoie les candidats des structures demandées.

Attention, le compte doit être administrateur des structures.

# Exemples de requêtes

## Mode multistructures

```bash
curl
-L '{settings.ITOU_PROTOCOL}://{settings.ITOU_FQDN}/api/v1/candidats/?mode_multi_structures=1' \
-H 'Authorization: Token [token]'
```

## Fitre par structure

Afin de trouver l'identifiant unique d'une structure, connectez-vous à votre espace personnel
et cliquez sur « Mon espace » > « Accès aux APIs ».

### Une structure

```bash
curl
-L '{settings.ITOU_PROTOCOL}://{settings.ITOU_FQDN}/api/v1/candidats/?structures_uid=[uid-1]' \
-H 'Authorization: Token [token]'
```

### Plusieurs structures

Séparez les identifiants par des virgules.

```bash
curl
-L '{settings.ITOU_PROTOCOL}://{settings.ITOU_FQDN}/api/v1/candidats/?structures_uid=[uid-1,uid-2,uid-3]' \
-H 'Authorization: Token [token]'
```

"""
