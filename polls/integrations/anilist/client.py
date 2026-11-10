import logging
import time
from io import BytesIO
from typing import Any, Tuple
from uuid import uuid4

import requests
from PIL import Image
from django.core.files.base import ContentFile
from django.db import transaction
from requests.exceptions import RequestException

from polls.models import Show, Category, CategoryShow, Character, Person, VotingConfig, Music
from .queries import GET_SHOWS, GET_CHARACTERS, GET_SONGS, GET_SHOW

logger = logging.getLogger(__name__)

timeout = 20
al_url = "https://graphql.anilist.co"
at_url = "https://graphql.animethemes.moe"
headers = {
    "User-Agent": "FediAnimeAwards/0.1.0"
}


def download_shows(year: int) -> None:
    config, _ = VotingConfig.objects.update_or_create(
        pk=1,
        defaults={"current_year": year},
    )

    genre_categories = get_genre_categories()

    seasons = (
        "WINTER",
        "SPRING",
        "SUMMER",
        "FALL"
    )

    for season in seasons:
        page = 1
        has_next_page = True
        per_page = 40

        while has_next_page and page < 3:
            payload = {
                "query": GET_SHOWS,
                "variables": {
                    "page": page,
                    "perPage": per_page,
                    "season": season,
                    "year": year,
                }
            }
            try:
                res = send_query(al_url, payload)
            except RequestException:
                logger.exception(
                    "AniList request failed: year=%s season=%s page=%s",
                    year,
                    season,
                    page,
                )
                raise
            has_next_page = al_parse_and_save_shows(res, genre_categories)
            page += 1
            # Anilist ratelimit - maximum of 30 requests per minute
            time.sleep(2)


def download_show(anilist_id: int):
    show = Show.objects.filter(pk=anilist_id).first()
    if show:
        raise RuntimeError(f"Anime with ID {anilist_id} already exists.")
    genre_categories = get_genre_categories()
    payload = {
        "query": GET_SHOW,
        "variables": {
            "id": anilist_id
        }
    }
    try:
        res = send_query(al_url, payload)
    except RequestException:
        logger.exception("AniList request failed: id=%s", anilist_id)
        raise
    al_parse_and_save_shows(res, genre_categories)
    time.sleep(2)


def al_parse_and_save_shows(data: Any, genre_cat: dict[str, Category]) -> bool:
    if data.get("errors", None):
        error = (
            f"Error parsing results: "
            f"{'; '.join([error.get('message', '') for error in data['errors']])}"
        )
        logger.error("AniList query error: %s", error)
        raise RuntimeError(error)

    shows: list[Show] = []
    cat_show_id: set[Tuple[int, Category]] = set()
    has_next_page = data["data"]["Page"]["pageInfo"]["hasNextPage"]

    # Collect all shows
    for result in data["data"]["Page"]["media"]:
        show = Show(
            al_id=result["id"],
            mal_id=result["idMal"],
            title_romaji=result["title"]["romaji"],
            title_english=result["title"]["english"],
            poster=_download_poster(result["coverImage"]["large"]),
            format=result["format"]
        )
        shows.append(show)

        # Collect AL ID - Category pairs
        # Here we assign shows to the categories based on their genre tags
        for genre in result["genres"]:
            cat = genre_cat.get(genre, None)
            if cat:
                cat_show_id.add((show.al_id, cat))
        if show.format == "MOVIE":
            cat_show_id.add((show.al_id, genre_cat["Movie"]))
        elif show.format in ("TV", "SPECIAL", "ONA", "OVA"):
            # Excluding Movies from Animation category is deliberate
            cat_show_id.add((show.al_id, genre_cat["Series"]))
            cat_show_id.add((show.al_id, genre_cat["Animation"]))
        cat_show_id.add((show.al_id, genre_cat["Soundtrack"]))

    with transaction.atomic():
        Show.objects.bulk_create(shows, batch_size=500)

        # Insert data linking show to an existing category for shows we just added
        saved_shows = {
            show.al_id: show
            for show in Show.objects.filter(
                al_id__in=[show.al_id for show in shows]
            )
        }

        category_shows: list[CategoryShow] = []
        for show_id, cat_obj in cat_show_id:
            cs = CategoryShow(
                show=saved_shows[show_id],
                category=cat_obj,
                finalist=False,
            )
            category_shows.append(cs)

        CategoryShow.objects.bulk_create(category_shows, batch_size=500)
    return has_next_page


def get_genre_categories() -> dict[str, Category]:
    # Changes here require corresponding changes in Category table in the DB (look: migrations)
    genre_to_category_name = {
        "Action": "Action",
        "Adventure": "Fantasy/Adventure",
        "Comedy": "Comedy",
        "Drama": "Drama",
        "Fantasy": "Fantasy/Adventure",
        "Mystery": "Drama",
        "Psychological": "Drama",
        "Romance": "Romance",
        "Sci-Fi": "Fantasy/Adventure",
        "Slice of Life": "Slice of Life",
        "Movie": "Movie of the Year",
        "Series": "Anime of the Year",
        "Animation": "Animation",
        "Soundtrack": "Soundtrack"
    }

    category_names = set(genre_to_category_name.values())

    categories_by_name = {
        category.name: category
        for category in Category.objects.filter(name__in=category_names)
    }

    missing = category_names - categories_by_name.keys()
    if missing:
        error = f"Missing categories in database: {sorted(missing)}"
        logger.error("Error mapping genres to categories: %s", error)
        raise ValueError(error)

    return {
        genre: categories_by_name[category_name]
        for genre, category_name in genre_to_category_name.items()
    }


def download_characters_people(show_id: int = 0, by_id: bool = False) -> None:
    if by_id:
        shows = {show_id: Show.objects.get(pk=show_id)}
        show_keys = [show_id]
    else:
        shows = Show.objects.in_bulk()
        show_keys = list(shows.keys())

    for lang in ("JAPANESE", "ENGLISH"):
        start = 0
        end = 10 if len(show_keys) > 10 else len(show_keys)

        while start < len(show_keys):
            payload = {
                "query": GET_CHARACTERS,
                "variables": {
                    "ids": show_keys[start:end],
                    "page": 1,
                    "perPage": len(show_keys[start:end]),
                    "charactersPage": 1,
                    "language": lang
                }
            }

            try:
                res = send_query(al_url, payload)
            except RequestException as e:
                logger.exception("AniList request for characters failed: %s", e)
                raise

            al_parse_and_save_characters(res, shows, True if lang == "JAPANESE" else False)
            start = end
            end = end + 10 if end + 10 < len(show_keys) else len(show_keys)
            time.sleep(2)


def al_parse_and_save_characters(data: Any, shows: dict[Any, Show], save_characters: bool) -> None:
    if data.get("errors", None):
        error = (
            f"Error parsing results: "
            f"{'; '.join([error.get('message', '') for error in data['errors']])}"
        )
        logger.error("AniList query error: %s", error)
        raise RuntimeError(error)

    # Collect all characters and voice performances (people)
    for result in data["data"]["Page"]["media"]:
        characters: list[Character] = []
        people_dicts: list[dict[str, Any]] = []

        for character_raw in result["characters"]["edges"]:
            # Create character object
            character = Character(
                al_id=character_raw["node"]["id"],
                show=shows[result["id"]],
                name=character_raw["node"]["name"]["full"],
                picture=None,  # Added manually in the final vote phase
                finalist=False,
            )

            characters.append(character)

            # Save VA data with a link to character via char_id
            for person_raw in character_raw["voiceActors"]:
                person = {
                    "char_id": character_raw["node"]["id"],
                    "al_id": person_raw["id"],
                    "name": person_raw["name"]["full"],
                }
                people_dicts.append(person)

        with transaction.atomic():
            # Insert characters; ignore conflicts because AniList database contains duplicated
            # character entries under some of the shows
            if save_characters:
                Character.objects.bulk_create(characters, batch_size=500, ignore_conflicts=True)

            saved_characters = {
                character.al_id: character
                for character in Character.objects.filter(
                    show=shows[result["id"]],
                    al_id__in=[character.al_id for character in characters],
                )
            }

            people: list[Person] = []
            for pd in people_dicts:
                person = Person(
                    name=pd["name"],
                    character=saved_characters[pd["char_id"]],
                    al_id=pd["al_id"],
                    finalist=False,
                )
                people.append(person)

            # Insert characters; ignore conflicts because AniList database contains duplicated
            # character entries under some of the shows
            Person.objects.bulk_create(people, batch_size=500, ignore_conflicts=True)


def download_music(show_id: int = 0, by_id: bool = False) -> None:
    if by_id:
        shows = {show_id: Show.objects.get(pk=show_id)}
        show_keys = [show_id]
    else:
        shows = Show.objects.in_bulk()
        show_keys = list(shows.keys())
    start = 0
    end = 10 if len(show_keys) > 10 else len(show_keys)

    while start < len(show_keys):
        payload = {
            "query": GET_SONGS,
            "variables": {
                "id": show_keys[start:end]
            }
        }

        try:
            res = send_query(at_url, payload)
        except RequestException as e:
            logger.exception("AnimeThemes request for music performances failed: %s", e)
            raise

        at_parse_and_save_songs(res, shows)
        start = end
        end = end + 10 if end + 10 < len(show_keys) else len(show_keys)
        time.sleep(2)


def at_parse_and_save_songs(data: Any, shows: dict[Any, Show]) -> None:
    if data.get("errors", None):
        error = (
            f"Error parsing results: "
            f"{'; '.join([error.get('message', '') for error in data['errors']])}"
        )
        logger.error("AnimeThemes query error: %s", error)
        raise RuntimeError(error)

    # Collect all songs
    songs: list[Music] = []

    for anime_data in data["data"]["findAnimeByExternalSite"]:
        anime_title = anime_data["title"]["english"] or anime_data["title"]["romaji"]
        anime_al_id = anime_data["resources"]["nodes"][0]["externalId"]

        for song_data in anime_data["animethemes"]:
            if song_data["song"]:
                song_title = song_data["song"]["title"]["romaji"]
            else:
                song_title = ""
            song_num = song_data["sequence"] or ""
            song_type_num = f"{song_data["type"]}{song_num}"
            for version_num, video in enumerate(song_data["animethemeentries"], start=1):
                if len(song_data["animethemeentries"]) > 1:
                    version = f"v{version_num}"
                else:
                    version = ""
                song_name = f"{song_title} ({anime_title} {song_type_num}{version})"
                video_link = None
                if video["videos"]["nodes"]:
                    video_link = video["videos"]["nodes"][0]["link"]

                song = Music(
                    show=shows[anime_al_id],
                    title=song_name,
                    url=video_link,
                    type=song_data["type"],
                    thumb=None,  # Added manually in the final vote phase
                    finalist=False,
                )

                songs.append(song)

    with transaction.atomic():
        Music.objects.bulk_create(songs, batch_size=500)


def send_query(url: str, payload: dict[str, Any], attempt: int = 1) -> dict[str, Any]:
    res = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=timeout
    )
    if res.status_code == 429:
        # Maximum 10 attempts when hitting ratelimit
        if attempt == 10:
            res.raise_for_status()

        retry_after = res.headers.get("Retry-After")
        try:
            delay = max(2, int(retry_after))
        except (TypeError, ValueError):
            delay = 2 ** (attempt)  # fallback

        time.sleep(delay)
        return send_query(url, payload, attempt + 1)

    res.raise_for_status()
    return res.json()


def _download_poster(payload: str) -> ContentFile | None:
    if not payload:
        return None

    try:
        res = requests.get(payload, headers=headers, timeout=timeout)
        res.raise_for_status()

        with Image.open(BytesIO(res.content)) as image:
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            image = image.convert("RGBA" if has_alpha else "RGB")

            output = BytesIO()
            image.save(output, format="AVIF", quality=90)

        return ContentFile(output.getvalue(), name=f"{uuid4().hex}.avif")
    except Exception as e:
        logger.exception("Failed to download or convert poster")
        return None
