from polls.integrations.lemmy import client
from django.conf import settings
from polls.integrations.lemmy.client import LemmyError

def register_username(username, password):
    message = (
        "### Fediverse Anime Awards  \n"
        f"Your account with username `{username}` has been registered.  \n"
        f"Here's your password: `{password}`  \n  \n"
        f"If you didn't register on {settings.FEDI_ANIME_AWARDS_URL}, ignore this message."
    )
    client.send_message(username, message, True)

def reset_password(username, message):
    client.send_message(username, message)