import logging
from collections import defaultdict
from typing import Tuple, Any

from django.db import transaction
from django.db.models import Count, F, Window
from django.db.models.functions import Rank
from django.tasks import task

from polls.integrations.anilist import client
from .models import (
    CategoryShow,
    NominationChoice,
    NominationSet,
    VotingConfig,
    Character,
    Person,
    Music,
    Category,
    ImportState,
)

logger = logging.getLogger(__name__)


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

def _set_import_state(status, *, label="", error_type=""):
    ImportState.objects.update_or_create(
        pk=1,
        defaults={
            "status": status,
            "label": label,
            "error_type": error_type,
        },
    )

def run_import(label, import_function, *args):
    _set_import_state(ImportState.Status.RUNNING, label=label)

    try:
        import_function(*args)
    except Exception as e:
        logger.exception("Import failed: %s", label)
        _set_import_state(
            ImportState.Status.FAILED,
            label=label,
            error_type=type(e).__name__,
        )
        raise  # Let django-tasks-db record the task as failed too.

    _set_import_state(ImportState.Status.SUCCESSFUL, label=label)

@task
def import_year(year: int) -> None:
    run_import(f"Year {year}", _download_from_api, year)


@task
def import_single_show(anilist_id: int) -> None:
    run_import(
        f"AniList ID {anilist_id}",
        _download_single_from_api,
        anilist_id,
    )

def _download_from_api(year: int) -> None:
    client.download_shows(year)
    client.download_characters_people()
    client.download_music()


def _download_single_from_api(anilist_id: int) -> None:
    client.download_show(anilist_id)
    client.download_characters_people(anilist_id, True)
    client.download_music(anilist_id, True)


def select_finalists() -> None:
    with transaction.atomic():
        year = VotingConfig.objects.get(pk=1).current_year
        VotingConfig.objects.filter(pk=1).update(voting_enabled=False)
        VotingConfig.objects.filter(pk=1).update(finals_vote=True)

    counts = (
        NominationChoice.objects
        .filter(
            nomination_set__year=year,
            nomination_set__user__is_active=True,
        )
        .values(
            "nomination_set__category_id",
            "nomination_set__category__name",
            "value",
        )
        .annotate(votes=Count("pk"))
    )

    top_6_per_category = (
        counts
        .annotate(
            rank=Window(
                expression=Rank(),
                partition_by=[F("nomination_set__category_id")],
                order_by=F("votes").desc(),
            )
        )
        .filter(rank__lte=6)
        .order_by(
            "nomination_set__category__name",
            "rank",
            "value",
        )
    )

    with transaction.atomic():
        # Clear previous finalists for CategoryShow
        CategoryShow.objects.filter(finalist=True).update(finalist=False)

        # Clear previous finalists in the other tables
        other_models = set(MODEL_BY_CATEGORY_ID.values()) - {CategoryShow}
        for model in other_models:
            model.objects.filter(finalist=True).update(finalist=False)

        pks_by_model = defaultdict(set)

        # Set new finalists in each category
        for row in top_6_per_category:
            category_id = row["nomination_set__category_id"]
            model = MODEL_BY_CATEGORY_ID[category_id]
            pks_by_model[model].add(row["value"])

        for model, pks in pks_by_model.items():
            model.objects.filter(pk__in=pks).update(finalist=True)


def get_results() -> Tuple[int, dict[Tuple[str, int], list[Any]], dict[Tuple[str, int], list[Any]], bool]:
    year = VotingConfig.objects.get(pk=1).current_year
    final_enabled = VotingConfig.objects.get(pk=1).finals_vote

    nominations_sorted = _get_nominations(year)
    finals_sorted = _get_finals(year)

    return year, nominations_sorted, finals_sorted, final_enabled


def _get_nominations(year) -> dict[Tuple[str, int], list[Any]]:
    nominations = (
        NominationChoice.objects
        .filter(
            nomination_set__year=year,
            nomination_set__user__is_active=True
        )
        .values(
            "nomination_set__category_id",
            "nomination_set__category__name",
            "value",
        )
        .annotate(votes=Count("pk"))
    )

    nominations_ranked = list(
        nominations
        .annotate(
            rank=Window(
                expression=Rank(),
                partition_by=[F("nomination_set__category_id")],
                order_by=F("votes").desc(),
            )
        )
        .order_by(
            "nomination_set__category_id",
            "rank",
            "value",
        )
    )

    _add_names(
        nominations_ranked,
        "nomination_set__category_id",
        "value",
    )

    return _sort_results(
        nominations_ranked,
        "nomination_set__category__name",
        "nomination_set__category_id"
    )


def _get_finals(year) -> dict[Tuple[str, int], list[Any]]:
    finals = (
        NominationSet.objects
        .filter(
            year=year,
            final_vote__isnull=False,
            user__is_active=True
        )
        .values("category_id", "category__name", "final_vote")
        .annotate(votes=Count("pk"))
    )

    finals_ranked = list(
        finals
        .annotate(
            rank=Window(
                expression=Rank(),
                partition_by=[F("category_id")],
                order_by=F("votes").desc(),
            )
        )
        .order_by(
            "category_id",
            "rank",
            "final_vote",
        )
    )

    _add_names(
        finals_ranked,
        "category_id",
        "final_vote",
    )

    return _sort_results(finals_ranked, "category__name", "category_id")


def _add_names(
        rows: list[dict[str, Any]],
        category_key: str,
        value_key: str
) -> None:
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
        rows: list[dict[str, Any]],
        category_name: str,
        category_id: str) -> dict[Tuple[str, int], list[Any]]:
    rows_sorted = {(key.name, key.id): [] for key in Category.objects.all()}
    for row in rows:
        rows_sorted[row[category_name], row[category_id]].append(row)
    return rows_sorted


def get_admin_results_md(is_final: bool) -> str:
    year = VotingConfig.objects.get(pk=1).current_year

    if is_final:
        user_votes = _get_finals(year)
    else:
        user_votes = _get_nominations(year)

    markdown = f"# Fediverse Anime Awards {year}"
    if not is_final:
        markdown += f" (Nominations)"
    markdown += f" - Full Results"

    for category_pair, category in user_votes.items():
        markdown += f"  \n## {category_pair[0]}  \n"
        if not category:
            markdown += f"No results for this category.  \n  \n"
        else:
            markdown += f"|Place|Name|Votes|  \n|-|-|-|  \n"
            for item in category:
                markdown += f"|{item['rank']}.|{item['name']}|{item['votes']}|  \n"

    return markdown
