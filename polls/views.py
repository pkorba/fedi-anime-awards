import logging
import re
import secrets
import string
from collections import defaultdict
from typing import Any, Tuple

from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.db.models import Max, QuerySet
from django.db.models import Q
from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy

from .models import (
    Category,
    CategoryShow,
    Character,
    Person,
    Music,
    NominationChoice,
    NominationSet,
    VotingConfig
)
from .services import register_username, LemmyError

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(
    r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
)


class CaseInsensitiveLoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": gettext_lazy("Please enter a correct username and password."),
    }


class HomeLoginView(auth_views.LoginView):
    template_name = "polls/index.html"
    authentication_form = CaseInsensitiveLoginForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["voting_enabled"] = VotingConfig.objects.get(pk=1).voting_enabled
        context["year"] = VotingConfig.objects.get(pk=1).current_year
        return context


def _get_selected_option_ids(nomination_set, finals_enabled):
    if not nomination_set:
        return set()

    if finals_enabled:
        if nomination_set.final_vote is None:
            return set()
        return {nomination_set.final_vote}

    return set(nomination_set.choices.values_list("value", flat=True))


def _save_selections(
        request,
        category,
        allowed_entries,
        max_selections,
        year,
        finals_enabled,
):
    raw_ids = request.POST.getlist("selected_entries")

    # Reject excessive input before converting or querying.
    if len(raw_ids) > max_selections:
        return JsonResponse(
            {"error": f"Select up to {max_selections} option(s)."},
            status=400,
        )

    selected_ids = []
    for raw_id in raw_ids:
        # IDs are positive ASCII decimal integers, with a safe upper bound
        # for Django's usual integer primary-key types.
        if (
                not raw_id
                or len(raw_id) > 19
                or not raw_id.isascii()
                or not raw_id.isdecimal()
        ):
            return JsonResponse({"error": "Invalid selection."}, status=400)

        selected_id = int(raw_id)
        if not 1 <= selected_id <= 9_223_372_036_854_775_807:
            return JsonResponse({"error": "Invalid selection."}, status=400)

        selected_ids.append(selected_id)

    if len(selected_ids) != len(set(selected_ids)):
        return JsonResponse(
            {"error": f"Select up to {max_selections} option(s)."},
            status=400,
        )

    valid_ids = set(
        allowed_entries
        .filter(pk__in=selected_ids)
        .values_list("pk", flat=True)
    )
    if valid_ids != set(selected_ids):
        return JsonResponse({"error": "Invalid selection."}, status=400)

    with transaction.atomic():
        nomination_set, _ = NominationSet.objects.get_or_create(
            user=request.user,
            category=category,
            year=year,
        )
        nomination_set = NominationSet.objects.select_for_update().get(
            pk=nomination_set.pk
        )

        if finals_enabled:
            new_vote = selected_ids[0] if selected_ids else None

            # Don't write to the database if the vote hasn't changed.
            if nomination_set.final_vote == new_vote:
                return JsonResponse({"saved": True})

            # One actual change per user per second across categories.
            if not cache.add(
                    f"nomination-write:{request.user.pk}",
                    True,
                    timeout=1,
            ):
                return JsonResponse(
                    {"error": "Please wait before saving again."},
                    status=429,
                )

            nomination_set.final_vote = new_vote
            nomination_set.save(update_fields=["final_vote"])

        else:
            old_values = list(
                nomination_set.choices
                .order_by("position")
                .values_list("value", flat=True)
            )

            # Don't delete and recreate choices when nothing has changed.
            if old_values == selected_ids:
                return JsonResponse({"saved": True})

            if not cache.add(
                    f"nomination-write:{request.user.pk}",
                    True,
                    timeout=1,
            ):
                return JsonResponse(
                    {"error": "Please wait before saving again."},
                    status=429,
                )

            nomination_set.choices.all().delete()
            NominationChoice.objects.bulk_create([
                NominationChoice(
                    nomination_set=nomination_set,
                    position=position,
                    value=value,
                )
                for position, value in enumerate(selected_ids, start=1)
            ])

    return JsonResponse({"saved": True})


def _render_poll(request, template, context, category_id, last_id):
    context.update({
        "previous_id": category_id - 1 if category_id > 1 else None,
        "next_id": category_id + 1 if category_id < last_id else None,
    })
    return render(request, template, context)


def _character_poll(request, category_id, last_id, year, finals_enabled, context):
    template = "polls/characters.html"
    category = get_object_or_404(Category, name="Character")

    allowed_entries = Character.objects.all()
    if finals_enabled:
        allowed_entries = allowed_entries.filter(finalist=True)

    max_selections = 1 if finals_enabled else 5

    if request.method == "POST":
        return _save_selections(
            request,
            category,
            allowed_entries,
            max_selections,
            year,
            finals_enabled,
        )

    nomination_set = NominationSet.objects.filter(
        user=request.user,
        category=category,
        year=year,
    ).first()
    selected_option_ids = _get_selected_option_ids(nomination_set, finals_enabled)

    selected_entries = list(
        allowed_entries
        .filter(pk__in=selected_option_ids)
        .select_related("show")
        .order_by("name", "pk")
    )

    query_values = request.GET.getlist("q")

    if len(query_values) > 1:
        return HttpResponseBadRequest("Invalid search query.")

    raw_query = query_values[0] if query_values else ""
    if len(raw_query) > 100:
        return HttpResponseBadRequest("Search query is too long.")

    search_query = raw_query.strip()

    has_more = False
    entry_count = allowed_entries.count()

    if len(search_query) >= 2:
        matches = (
            allowed_entries
            .filter(
                Q(name__icontains=search_query)
                | Q(show__title_english__icontains=search_query)
                | Q(show__title_romaji__icontains=search_query)
            )
            .exclude(pk__in=selected_option_ids)
            .select_related("show")
            .order_by("name", "pk")
        )

        results = list(matches[:101])
        has_more = len(results) > 100
        matching_entries = results[:100]
        entries = selected_entries + matching_entries
    elif entry_count <= 100:
        entries = list(
            allowed_entries
            .select_related("show")
            .order_by("name", "pk")
        )
    else:
        entries = selected_entries

    context.update({
        "active_page": "characters",
        "active_category": category,
        "entries": entries,
        "selected_option_ids": selected_option_ids,
        "max_selections": max_selections,
        "search_query": search_query,
        "has_more": has_more,
        "finals_enabled": finals_enabled
    })

    return _render_poll(request, template, context, category_id, last_id)


def _people_poll(request, category_id, last_id, year, finals_enabled, context):
    template = "polls/people.html"
    category = get_object_or_404(Category, name="Voice Performance")

    allowed_entries = Person.objects.all()
    if finals_enabled:
        allowed_entries = allowed_entries.filter(finalist=True)

    max_selections = 1 if finals_enabled else 5

    if request.method == "POST":
        return _save_selections(
            request,
            category,
            allowed_entries,
            max_selections,
            year,
            finals_enabled,
        )

    nomination_set = NominationSet.objects.filter(
        user=request.user,
        category=category,
        year=year,
    ).first()
    selected_option_ids = _get_selected_option_ids(nomination_set, finals_enabled)

    selected_entries = list(
        allowed_entries
        .filter(pk__in=selected_option_ids)
        .select_related("character", "character__show")
        .order_by("name", "pk")
    )

    query_values = request.GET.getlist("q")

    if len(query_values) > 1:
        return HttpResponseBadRequest("Invalid search query.")

    raw_query = query_values[0] if query_values else ""
    if len(raw_query) > 100:
        return HttpResponseBadRequest("Search query is too long.")

    search_query = raw_query.strip()

    has_more = False
    entry_count = allowed_entries.count()

    if len(search_query) >= 2:
        matches = (
            allowed_entries
            .filter(
                Q(name__icontains=search_query)
                | Q(character__name__icontains=search_query)
            )
            .exclude(pk__in=selected_option_ids)
            .select_related("character", "character__show")
            .order_by("name", "pk")
        )

        results = list(matches[:101])
        has_more = len(results) > 100
        matching_entries = results[:100]
        entries = selected_entries + matching_entries
    elif entry_count <= 100:
        entries = list(
            allowed_entries
            .select_related("character", "character__show")
            .order_by("name", "pk")
        )
    else:
        entries = selected_entries

    context.update({
        "active_page": "people",
        "active_category": category,
        "entries": entries,
        "selected_option_ids": selected_option_ids,
        "max_selections": max_selections,
        "search_query": search_query,
        "has_more": has_more,
        "finals_enabled": finals_enabled,
    })

    return _render_poll(request, template, context, category_id, last_id)


def _music_poll(request, category_id, last_id, year, finals_enabled, context):
    category = get_object_or_404(Category, name="Musical Sequence")
    template = "polls/music.html"

    allowed_entries = Music.objects.all()
    if finals_enabled:
        allowed_entries = allowed_entries.filter(finalist=True)

    max_selections = 1 if finals_enabled else 5

    if request.method == "POST":
        return _save_selections(
            request,
            category,
            allowed_entries,
            max_selections,
            year,
            finals_enabled,
        )

    nomination_set = NominationSet.objects.filter(
        user=request.user,
        category=category,
        year=year,
    ).first()
    selected_option_ids = _get_selected_option_ids(nomination_set, finals_enabled)

    context.update({
        "active_page": "music",
        "active_category": category,
        "entries": allowed_entries,
        "selected_option_ids": selected_option_ids,
        "max_selections": max_selections,
        "finals_enabled": finals_enabled,
    })

    return _render_poll(request, template, context, category_id, last_id)


def _category_poll(request, category_id, last_id, year, finals_enabled, context):
    category = get_object_or_404(
        Category.objects.exclude(name__in=[
            "Character",
            "Voice Performance",
            "Musical Sequence",
        ]),
        pk=category_id,
    )
    template = "polls/category.html"

    allowed_entries = (
        CategoryShow.objects
        .filter(category=category)
        .select_related("show")
        .order_by("show__title_english", "show__title_romaji")
    )

    if finals_enabled:
        allowed_entries = allowed_entries.filter(finalist=True)

    max_selections = 1 if finals_enabled else 5

    if request.method == "POST":
        return _save_selections(
            request,
            category,
            allowed_entries,
            max_selections,
            year,
            finals_enabled,
        )

    nomination_set = NominationSet.objects.filter(
        user=request.user,
        category=category,
        year=year,
    ).first()
    selected_option_ids = _get_selected_option_ids(nomination_set, finals_enabled)

    context.update({
        "active_page": "category",
        "active_category": category,
        "entries": allowed_entries,
        "selected_option_ids": selected_option_ids,
        "max_selections": max_selections,
        "finals_enabled": finals_enabled,
    })

    return _render_poll(request, template, context, category_id, last_id)


@login_required
def category_poll(request, category_id):
    config = VotingConfig.objects.get(pk=1)
    year = config.current_year
    finals_enabled = config.finals_vote
    voting_enabled = config.voting_enabled

    if not voting_enabled and not request.user.is_staff:
        return redirect("home_login")

    excluded_names = ["Character", "Voice Performance", "Musical Sequence"]

    max_id = (
            Category.objects
            .exclude(name__in=excluded_names)
            .aggregate(max_id=Max("id"))["max_id"]
            or 0
    )

    characters_id = max_id + 1
    people_id = max_id + 2
    music_id = max_id + 3
    last_id = music_id

    if not 1 <= category_id <= last_id:
        raise Http404

    context = {
        "categories": Category.objects.exclude(name__in=excluded_names),
        "characters_id": characters_id,
        "people_id": people_id,
        "music_id": music_id
    }

    if category_id == characters_id:
        return _character_poll(request, category_id, last_id, year, finals_enabled, context)

    if category_id == people_id:
        return _people_poll(request, category_id, last_id, year, finals_enabled, context)

    if category_id == music_id:
        return _music_poll(request, category_id, last_id, year, finals_enabled, context)

    return _category_poll(request, category_id, last_id, year, finals_enabled, context)


def signup(request):
    error = ""
    username = ""
    year = VotingConfig.objects.get(pk=1).current_year

    if request.method == "POST":
        usernames = request.POST.getlist("username")
        challenges = request.POST.getlist("challenge")
        agreements = request.POST.getlist("agree")

        # Treat missing or duplicated scalar fields as invalid.
        username = usernames[0].strip() if len(usernames) == 1 else ""
        challenge = challenges[0].strip().casefold() if len(challenges) == 1 else ""
        agreed = agreements == ["on"]

        User = get_user_model()

        if not username:
            error = "Enter a username."
        elif len(username) > 150:
            error = f"Username must be 150 characters or fewer."
        elif not USERNAME_RE.fullmatch(username):
            error = "Use the format username@instance.tld"
        elif not agreed:
            error = "You must agree to the Terms of Service and Privacy Policy."
        elif len(challenge) > 10 or challenge not in {"6", "six"}:
            error = "Wrong answer."
        elif User.objects.filter(username__iexact=username).exists():
            error = "That username is already taken."
        else:
            user = User(username=username)
            password = ''.join(
                secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10)
            )
            user.set_password(password)

            # send random password using pythorhead
            # don't create the user if sending password fails
            try:
                register_username(username, password)
            except LemmyError as e:
                logger.exception("Registration failed: %s", e)
                return render(
                    request,
                    "registration/signup.html",
                    {
                        "username": username,
                        "error": str(e),
                        "year": year + 1,
                    },
                )

            user.save()
            return redirect("signup_done")

    return render(request, "registration/signup.html", {
        "username": username,
        "error": error,
        "year": year + 1,
    })


def signup_done(request):
    return render(request, "registration/signup_done.html")


MODEL_BY_CATEGORY_ID = {
    1: CategoryShow,
    2: CategoryShow,
    3: CategoryShow,
    4: CategoryShow,
    5: CategoryShow,
    6: CategoryShow,
    7: CategoryShow,
    8: CategoryShow,
    9: CategoryShow,
    10: CategoryShow,
    11: Character,
    12: Person,
    13: Music,
}


@login_required
def results(request):
    year = VotingConfig.objects.get(pk=1).current_year
    final_enabled = VotingConfig.objects.get(pk=1).finals_vote

    nominations_sorted = _get_nominations(year, request.user)
    finals_sorted = _get_finals(year, request.user)

    return render(request, "polls/results.html", {
        "year": year,
        "nominations": nominations_sorted,
        "finals": finals_sorted,
        "final_enabled": final_enabled,
        "full": False
    })


def _get_nominations(year: int, user: Any) -> dict[Tuple[str, int], list[Any]]:
    nominations = (
        NominationChoice.objects
        .filter(nomination_set__year=year, nomination_set__user=user)
        .values(
            "nomination_set__category_id",
            "nomination_set__category__name",
            "value",
        )
    )

    _add_names(
        nominations,
        "nomination_set__category_id",
        "value",
    )

    return _sort_results(
        nominations,
        "nomination_set__category__name",
        "nomination_set__category_id"
    )


def _get_finals(year: int, user: Any) -> dict[Tuple[str, int], list[Any]]:
    finals = (
        NominationSet.objects
        .filter(year=year, final_vote__isnull=False, user=user)
        .values("category_id", "category__name", "final_vote")
    )

    _add_names(
        finals,
        "category_id",
        "final_vote",
    )

    return _sort_results(finals, "category__name", "category_id")


def _add_names(rows: QuerySet[Any, dict[str, Any]], category_key: str, value_key: str) -> None:
    ids_by_model = defaultdict(set)

    for row in rows:
        model = MODEL_BY_CATEGORY_ID[row[category_key]]
        ids_by_model[model].add(row[value_key])

    objects_by_model = {}

    for model, ids in ids_by_model.items():
        queryset = model.objects.filter(pk__in=ids)

        if model is CategoryShow:
            queryset = queryset.select_related("show")

        objects_by_model[model] = {obj.pk: obj for obj in queryset}

    for row in rows:
        model = MODEL_BY_CATEGORY_ID[row[category_key]]
        obj = objects_by_model[model][row[value_key]]

        if model is CategoryShow:
            row["name"] = obj.show.title_english or obj.show.title_romaji
        else:
            row["name"] = str(obj)


def _sort_results(
        rows: QuerySet[Any, dict[str, Any]],
        category_name: str,
        category_id: str
) -> dict[Tuple[str, int], list[Any]]:
    rows_sorted = {(key.name, key.id): [] for key in Category.objects.all()}
    for row in rows:
        rows_sorted[(row[category_name], row[category_id])].append(row)
    return rows_sorted


@login_required
def results_md(request):
    year = VotingConfig.objects.get(pk=1).current_year
    is_final = request.GET.get("final", "").lower() == "true"

    if is_final:
        user_votes = _get_finals(year, request.user)
    else:
        user_votes = _get_nominations(year, request.user)

    markdown = f"## Fediverse Anime Awards {year}"
    if not is_final:
        markdown += f" (Nominations)"
    markdown += f" - u/{request.user.get_username()} votes"

    for category_pair, category in user_votes.items():
        markdown += f"  \n**{category_pair[0]}**  \n"
        if not category:
            markdown += f"No results for this category.  \n"
        else:
            for item in category:
                if is_final:
                    markdown += f"{item['name']}  \n"
                else:
                    markdown += f"- {item['name']}  \n"

    return JsonResponse({"text": markdown})

def policies(request):
    return render(request, "polls/policies.html", {
        "contact_username": settings.CONTACT_USERNAME,
        "contact_url": settings.CONTACT_URL,
    })