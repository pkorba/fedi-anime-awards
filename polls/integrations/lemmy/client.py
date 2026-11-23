import logging
from datetime import datetime, date, timezone

from django.conf import settings
from pythorhead import Lemmy
from pythorhead.types import ModlogActionType

from polls.models import VotingConfig


class LemmyError(Exception):
    pass


logger = logging.getLogger(__name__)
_lemmy: Lemmy = None


def _lemmy_login(timeout: int = 30):
    global _lemmy

    try:
        client = Lemmy(
            settings.LEMMY_INSTANCE,
            raise_exceptions=True,
            request_timeout=timeout,
        )
        client.log_in(settings.LEMMY_USERNAME, settings.LEMMY_PASSWORD)
    except Exception:
        _lemmy = None
        raise LemmyError(
            "Connection to Lemmy failed. Try again later. "
            "If it happens again, contact the website's administrator."
        )

    _lemmy = client


# Client gets invalidated every time there's an error, because it's not clear what kind of error
# different Lemmy versions might return in case of unsuccessful authentication.
# Also, because pythorhead doesn't send stay_logged_in param, the session will expire after a week
# https://join-lemmy.org/lemmy-js-client-docs/main/types/Login.html#stay_logged_in
def send_message(username: str, message: str, verify: bool = False) -> None:
    global _lemmy

    if not _lemmy:
        _lemmy_login(30)

    try:
        user = _lemmy.user.get(username=username)
    except Exception:
        _lemmy = None
        raise LemmyError(f"No valid username found for {username}.")

    user_id = user["person_view"]["person"]["id"]
    if not user_id:
        raise LemmyError(f"No valid ID found for {username}.")

    if verify:
        # Check if user is banned on instance or in chosen community
        banned = user["person_view"]["person"]["banned"]
        expires = user["person_view"]["person"].get("ban_expires", None)

        if banned and not expires:
            raise LemmyError(f"User {username} is banned.")
        elif banned and expires:
            expiration = _parse_date(expires, "ban expiration", username)
            if expiration > datetime.now(timezone.utc):
                raise LemmyError(f"User {username} is banned.")

        _verify_community_ban(user_id, username)

        # Check if account age crosses the threshold
        account_creation_date = user["person_view"]["person"]["published"]
        _verify_account_age(account_creation_date, username)

    try:
        _lemmy.private_message(message, user_id)
    except Exception:
        _lemmy = None
        raise LemmyError(f"Sending private message to {username} failed.")


def _verify_community_ban(user_id: int, username: str) -> None:
    global _lemmy

    try:
        modlog_page = _lemmy.modlog.get(
            community_id=settings.LEMMY_COMMUNITY_ID,
            limit=1,
            other_person_id=user_id,
            page=1,
            type_=ModlogActionType.ModBanFromCommunity,
        )
        modlog = modlog_page["banned_from_community"]
    except Exception:
        _lemmy = None
        raise LemmyError(f"Could not determine account status for {username}.")

    if not modlog:
        return

    banned = modlog[0]["mod_ban_from_community"]["banned"]
    expiration = modlog[0]["mod_ban_from_community"].get("expires", None)
    if not banned:
        return

    if not expiration:
        raise LemmyError(f"User {username} is banned.")

    expiration_date = _parse_date(expiration, "ban expiration", username)
    if expiration_date > datetime.now(timezone.utc):
        raise LemmyError(f"User {username} is banned.")


def _verify_account_age(creation_date: str, username: str) -> None:
    if not creation_date:
        logger.info(f"No published date found for {username}.")
        raise LemmyError(f"Could not determine account age for {username}.")

    date_obj = _parse_date(creation_date, "account creation", username)
    year = VotingConfig.objects.get(pk=1).current_year

    if date_obj.date() > date(year, 12, 31):
        raise LemmyError(
            f"Only accounts created before 1 Jan {year + 1} are allowed to participate."
        )


def _parse_date(date_str: str, field_name: str, username: str) -> datetime:
    try:
        date_obj = datetime.fromisoformat(date_str)
    except ValueError:
        logger.error(f"Failed parsing date field '{field_name}' for {username}.")
        raise LemmyError(
            "Failed parsing date field. Please contact website's administrator"
        )

    return date_obj
