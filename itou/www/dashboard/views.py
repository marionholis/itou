from allauth.account.views import LogoutView, PasswordChangeView
from django.conf import settings
from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from itou.employee_record.enums import Status
from itou.employee_record.models import EmployeeRecord
from itou.institutions.models import Institution
from itou.job_applications.models import JobApplication, JobApplicationWorkflow
from itou.openid_connect.france_connect.constants import FRANCE_CONNECT_SESSION_STATE, FRANCE_CONNECT_SESSION_TOKEN
from itou.openid_connect.inclusion_connect.constants import INCLUSION_CONNECT_SESSION_KEY
from itou.prescribers.models import PrescriberOrganization
from itou.siae_evaluations.models import EvaluatedSiae, EvaluationCampaign
from itou.siaes.models import Siae
from itou.utils.perms.institution import get_current_institution_or_404
from itou.utils.perms.prescriber import get_current_org_or_404
from itou.utils.perms.siae import get_current_siae_or_404
from itou.utils.urls import get_absolute_url, get_safe_url
from itou.www.dashboard.forms import EditNewJobAppEmployersNotificationForm, EditUserEmailForm, EditUserInfoForm


@login_required
def dashboard(request, template_name="dashboard/dashboard.html"):
    can_show_financial_annexes = False
    can_show_employee_records = False
    job_applications_categories = []
    num_rejected_employee_records = 0
    active_campaigns = []

    # `current_org` can be a Siae, a PrescriberOrganization or an Institution.
    current_org = None

    if request.user.is_siae_staff:
        current_org = get_current_siae_or_404(request)
        can_show_financial_annexes = current_org.convention_can_be_accessed_by(request.user)
        can_show_employee_records = current_org.can_use_employee_record
        active_campaigns = EvaluatedSiae.objects.for_siae(current_org).in_progress()

        job_applications_categories = [
            {
                "name": "Candidatures à traiter",
                "states": [JobApplicationWorkflow.STATE_NEW, JobApplicationWorkflow.STATE_PROCESSING],
                "icon": "ri-user-add-line",
                "badge": "badge-danger",
            },
            {
                "name": "Candidatures acceptées ou mises en liste d'attente",
                "states": [JobApplicationWorkflow.STATE_ACCEPTED, JobApplicationWorkflow.STATE_POSTPONED],
                "icon": "ri-user-follow-line",
                "badge": "badge-secondary",
            },
            {
                "name": "Candidatures refusées/annulées",
                "states": [
                    JobApplicationWorkflow.STATE_REFUSED,
                    JobApplicationWorkflow.STATE_CANCELLED,
                    JobApplicationWorkflow.STATE_OBSOLETE,
                ],
                "icon": "ri-user-follow-line",
                "badge": "badge-secondary",
            },
        ]
        job_applications = current_org.job_applications_received.values("state").all()
        for category in job_applications_categories:
            category["counter"] = len([ja for ja in job_applications if ja["state"] in category["states"]])
            category[
                "url"
            ] = f"{reverse('apply:list_for_siae')}?{'&'.join([f'states={c}' for c in category['states']])}"

        num_rejected_employee_records = EmployeeRecord.objects.filter(
            status=Status.REJECTED,
            job_application__to_siae=current_org,
        ).count()

    if request.user.is_prescriber:
        try:
            current_org = get_current_org_or_404(request)
        except Http404:
            pass

    if request.user.is_labor_inspector:
        current_org = get_current_institution_or_404(request)
        active_campaigns = EvaluationCampaign.objects.for_institution(current_org).in_progress()

    context = {
        "lemarche_regions": settings.LEMARCHE_OPEN_REGIONS,
        "job_applications_categories": job_applications_categories,
        "can_create_siae_antenna": request.user.can_create_siae_antenna(parent_siae=current_org),
        "can_show_financial_annexes": can_show_financial_annexes,
        "can_show_employee_records": can_show_employee_records,
        "can_view_stats_dashboard_widget": request.user.can_view_stats_dashboard_widget(current_org=current_org),
        "can_view_stats_siae_etp": request.user.can_view_stats_siae_etp(current_org=current_org),
        "can_view_stats_siae_hiring": request.user.can_view_stats_siae_hiring(current_org=current_org),
        "can_view_stats_cd": request.user.can_view_stats_cd(current_org=current_org),
        "can_view_stats_pe": request.user.can_view_stats_pe(current_org=current_org),
        "can_view_stats_ddets": request.user.can_view_stats_ddets(current_org=current_org),
        "can_view_stats_dreets": request.user.can_view_stats_dreets(current_org=current_org),
        "can_view_stats_dgefp": request.user.can_view_stats_dgefp(current_org=current_org),
        "num_rejected_employee_records": num_rejected_employee_records,
        "active_campaigns": active_campaigns,
    }

    return render(request, template_name, context)


class ItouPasswordChangeView(PasswordChangeView):
    """
    https://github.com/pennersr/django-allauth/issues/468
    """

    success_url = reverse_lazy("dashboard:index")


password_change = login_required(ItouPasswordChangeView.as_view())


class ItouLogoutView(LogoutView):
    def post(self, *args, **kwargs):
        """
        We overload this method so that we can process the PEAMU callback
        or notify a SSO when the user logs out.
        Original code:
        https://github.com/pennersr/django-allauth/blob/master/allauth/account/views.py#L775
        TODO(alaurent) It would be cleaner to put all SSO logouts into UserAdapter.get_logout_redirect_url
        """

        peamu_id_token = self.request.user.peamu_id_token
        fc_token = self.request.session.get(FRANCE_CONNECT_SESSION_TOKEN)
        fc_state = self.request.session.get(FRANCE_CONNECT_SESSION_STATE)
        ic_session = self.request.session.get(INCLUSION_CONNECT_SESSION_KEY)
        # Note: if you need session data, fetch them BEFORE calling super() ;)
        ajax_response = super().post(*args, **kwargs)

        # Logout user from the app and from any SSO
        if fc_token:
            params = {"id_token": fc_token, "state": fc_state}
            fc_base_logout_url = get_absolute_url(reverse("france_connect:logout"))
            fc_logout_url = f"{fc_base_logout_url}?{urlencode(params)}"
            return HttpResponseRedirect(fc_logout_url)
        if ic_session:
            params = {"token": ic_session["token"], "state": ic_session["state"]}
            ic_base_logout_url = reverse("inclusion_connect:logout")
            ic_logout_url = f"{ic_base_logout_url}?{urlencode(params)}"
            return HttpResponseRedirect(ic_logout_url)
        if peamu_id_token:
            hp_url = self.request.build_absolute_uri("/")
            params = {"id_token_hint": peamu_id_token, "redirect_uri": hp_url}
            peamu_logout_url = f"{settings.PEAMU_AUTH_BASE_URL}/compte/deconnexion?{urlencode(params)}"
            return HttpResponseRedirect(peamu_logout_url)
        else:
            return ajax_response


logout = login_required(ItouLogoutView.as_view())


@login_required
def edit_user_email(request, template_name="dashboard/edit_user_email.html"):
    if request.user.has_sso_provider:
        return HttpResponseForbidden()
    form = EditUserEmailForm(data=request.POST or None, user_email=request.user.email)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            request.user.email = form.cleaned_data["email"]
            request.user.save()
            if request.user.emailaddress_set and request.user.emailaddress_set.first():
                request.user.emailaddress_set.first().delete()
        auth.logout(request)
        return HttpResponseRedirect(reverse("account_logout"))

    context = {
        "form": form,
    }

    return render(request, template_name, context)


@login_required
def edit_user_info(request, template_name="dashboard/edit_user_info.html"):
    """
    Edit a user.
    """
    dashboard_url = reverse_lazy("dashboard:index")
    prev_url = get_safe_url(request, "prev_url", fallback_url=dashboard_url)
    form = EditUserInfoForm(instance=request.user, editor=request.user, data=request.POST or None)
    extra_data = request.user.externaldataimport_set.pe_sources().first()

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Mise à jour de vos informations effectuée !")
        success_url = get_safe_url(request, "success_url", fallback_url=dashboard_url)
        return HttpResponseRedirect(success_url)

    context = {
        "extra_data": extra_data,
        "form": form,
        "prev_url": prev_url,
    }

    return render(request, template_name, context)


def user_can_edit_job_seeker_info(user, job_application, current_siae_pk=None):
    return (
        # Only when the information is not managed by job seekers themselves
        job_application.has_editable_job_seeker
        and (
            # Same sender (no SQL)
            job_application.sender_id == user.id
            # Member of the SIAE that offers the job application
            or (current_siae_pk and current_siae_pk == job_application.to_siae_id)
            # Member of the authorized prescriber organization who propose the candidate to the job application
            or user.is_prescriber_of_authorized_organization(job_application.sender_prescriber_organization_id)
        )
    )


@login_required
def edit_job_seeker_info(request, job_application_id, template_name="dashboard/edit_job_seeker_info.html"):
    job_application = get_object_or_404(JobApplication.objects.select_related("job_seeker"), pk=job_application_id)
    current_siae_pk = request.session.get(settings.ITOU_SESSION_CURRENT_SIAE_KEY)
    if not user_can_edit_job_seeker_info(request.user, job_application, current_siae_pk):
        raise PermissionDenied

    dashboard_url = reverse_lazy("dashboard:index")
    back_url = get_safe_url(request, "back_url", fallback_url=dashboard_url)
    form = EditUserInfoForm(instance=job_application.job_seeker, editor=request.user, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Les informations du candidat ont été mises à jour.")
        return HttpResponseRedirect(back_url)

    context = {
        "form": form,
        "job_application": job_application,
        "prev_url": back_url,
    }

    return render(request, template_name, context)


@login_required
@require_POST
def switch_siae(request):
    """
    Switch to the dashboard of another SIAE of the same SIREN.
    """
    dashboard_url = reverse_lazy("dashboard:index")

    pk = request.POST["siae_id"]
    queryset = Siae.objects.active_or_in_grace_period().member_required(request.user)
    siae = get_object_or_404(queryset, pk=pk)
    request.session[settings.ITOU_SESSION_CURRENT_SIAE_KEY] = siae.pk

    return HttpResponseRedirect(dashboard_url)


@login_required
@require_POST
def switch_prescriber_organization(request):
    """
    Switch prescriber organization for a user with multiple memberships.
    """
    dashboard_url = reverse_lazy("dashboard:index")

    pk = request.POST["prescriber_organization_id"]
    queryset = PrescriberOrganization.objects
    prescriber_organization = get_object_or_404(queryset, pk=pk)
    request.session[settings.ITOU_SESSION_CURRENT_PRESCRIBER_ORG_KEY] = prescriber_organization.pk

    return HttpResponseRedirect(dashboard_url)


@login_required
@require_POST
def switch_institution(request):
    """
    Switch prescriber organization for a user with multiple memberships.
    """
    dashboard_url = reverse_lazy("dashboard:index")

    pk = request.POST["institution_id"]
    queryset = Institution.objects
    institution = get_object_or_404(queryset, pk=pk)
    request.session[settings.ITOU_SESSION_CURRENT_INSTITUTION_KEY] = institution.pk

    return HttpResponseRedirect(dashboard_url)


@login_required
def edit_user_notifications(request, template_name="dashboard/edit_user_notifications.html"):
    if not request.user.is_siae_staff:
        raise PermissionDenied

    current_siae_pk = request.session.get(settings.ITOU_SESSION_CURRENT_SIAE_KEY)
    siae = get_object_or_404(Siae, pk=current_siae_pk)
    membership = request.user.siaemembership_set.get(siae=siae)
    new_job_app_notification_form = EditNewJobAppEmployersNotificationForm(
        recipient=membership, siae=siae, data=request.POST or None
    )

    dashboard_url = reverse_lazy("dashboard:index")
    back_url = get_safe_url(request, "back_url", fallback_url=dashboard_url)

    if request.method == "POST" and new_job_app_notification_form.is_valid():
        new_job_app_notification_form.save()
        messages.success(request, "Vos préférences ont été modifiées.")
        success_url = get_safe_url(request, "success_url", fallback_url=dashboard_url)
        return HttpResponseRedirect(success_url)

    context = {
        "new_job_app_notification_form": new_job_app_notification_form,
        "back_url": back_url,
    }

    return render(request, template_name, context)
