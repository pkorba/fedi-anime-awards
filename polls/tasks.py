import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.tasks import task

from polls.integrations.lemmy import client
from polls.integrations.lemmy.client import LemmyError


@task(queue_name="messages")
def register_username(username: str, year: int):
    password = ''.join(
        secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12)
    )

    message = (
        f"### Fediverse Anime Awards {year}  \n"
        f"Your account with username `{username}` has been registered.  \n"
        f"Here's your password: `{password}`  \n  \n"
        f"If you didn't register on {settings.FEDI_ANIME_AWARDS_URL}, ignore this message."
    )
    try:
        client.send_message(username, message, True)

        User = get_user_model()
        User.objects.create_user(username=username, password=password)

    except LemmyError as e:
        return {"ok": False, "message": str(e)}

    return {"ok": True}


@task(queue_name="messages")
def reset_password(username, message):
    client.send_message(username, message)
