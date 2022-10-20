# Generated by Django 3.1.3 on 2020-11-20 13:21

from django.db import migrations


# from itou.siaes.models import Siae


# def link_user_created_siaes_to_their_convention_when_possible(apps, schema_editor):
#     """
#     Reduce the number of user created siaes without convention from 316 down to 58.

#     For several weeks now, new user created siaes are automatically linked
#     to the convention of the initial siae.
#     This is not retroactive though, thus we have a remnant of old user created
#     siaes without convention.
#     When possible we figure out the initial siae and link the user created siae
#     to the same convention automatically to avoid user hassle and support hassle.
#     In edge cases and ambiguous cases we leave things as is and the user
#     will later fix the situation by themselves in the upcoming
#     "My Financial Annexes" interface.
#     """
#     siae_query = Siae.objects.filter(
#         kind__in=SIAE_WITH_CONVENTION_KINDS, source=Siae.SOURCE_USER_CREATED, convention__isnull=True
#     )
#     total = siae_query.count()
#     print("-" * 80)
#     print(f"Found {total} user created siaes without a convention.")

#     siae_query = (
#         siae_query.filter(created_by__isnull=False)
#         .select_related("created_by")
#         .prefetch_related(
#             "created_by__siaemembership_set",
#             "created_by__siaemembership_set__siae",
#             "created_by__siaemembership_set__siae__convention",
#         )
#     )

#     fixed = 0
#     for orphan_siae in siae_query.all():
#         # orphan_siae is a user created siae without convention.
#         user = orphan_siae.created_by

#         # We are looking for the initial siae the user created orphan_siae from.
#         # The user was necessarily admin of that initial siae
#         memberships = user.siaemembership_set.filter(is_siae_admin=True)
#         # The initial siae necessarily had the same SIREN and must be
#         # of ASP source.
#         initial_siae_candidates = [
#             membership.siae
#             for membership in memberships.all()
#             if membership.siae.source == Siae.SOURCE_ASP
#             and membership.siae.siren == orphan_siae.siren
#             and membership.siae.is_subject_to_eligibility_rules
#         ]

#         # Only proceed if we find exactly one initial siae candidate.
#         # If we have 2+ candidates we have an unsolvable ambiguity
#         # and just leave things as is.
#         if len(initial_siae_candidates) == 1:
#             initial_siae = initial_siae_candidates[0]
#             orphan_siae.convention = initial_siae.convention
#             orphan_siae.save()
#             fixed += 1

#     print(f"Fixed {fixed} of them by attaching the correct convention.")
#     print(f"{total - fixed} of them are left as is without a convention.")


class Migration(migrations.Migration):

    dependencies = [
        ("siaes", "0040_remove_siaefinancialannex_convention_number"),
    ]

    # Migration disabled since it breaks tests with error:
    # `psycopg2.errors.UndefinedColumn: column users_user.address_line_1 does not exist`
    operations = [migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop)]
    # operations = [
    #     migrations.RunPython(link_user_created_siaes_to_their_convention_when_possible, migrations.RunPython.noop)
    # ]
