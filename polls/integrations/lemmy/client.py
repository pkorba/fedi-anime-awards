from pythorhead import Lemmy
import logging
from datetime import datetime, date
from django.conf import settings

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
def send_message(username: str, message: str, verify_age: bool = False) -> None:
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

    if verify_age:
        account_creation_date =  user["person_view"]["person"]["published"]
        _verify_account_age(account_creation_date, username)

    try:
        _lemmy.private_message(message, user_id)
    except Exception:
        _lemmy = None
        raise LemmyError(f"Sending private message to {username} failed.")


def _verify_account_age(creation_date: str, username: str) -> None:
    if not creation_date:
        logger.info(f"No published date found for {username}.")
        raise LemmyError(f"Could not determine account age for {username}.")

    try:
        date_obj = datetime.fromisoformat(creation_date.replace("Z", "+00:00")).date()
    except ValueError:
        logger.error(f"Failed parsing account creation date for {username}.")
        raise LemmyError(
            "Failed parsing account creation date. Please contact website's administrator"
        )

    year = VotingConfig.objects.get(pk=1).current_year
    if date_obj > date(year, 12, 31):
        raise LemmyError(
            f"Only accounts created before 1 Jan {year + 1} are allowed."
        )
