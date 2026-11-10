import logging
import re

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.urls import reverse

from .services import LemmyError, reset_password

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(
    r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
)


class LemmyPasswordResetForm(PasswordResetForm):
    email = forms.CharField(label="Username", strip=True)

    def clean_email(self):
        username = self.cleaned_data["email"]

        if len(username) > 150:
            raise forms.ValidationError("Username is too long.")

        if not USERNAME_RE.fullmatch(username):
            raise forms.ValidationError("Use the format username@instance.tld")

        return username

    def get_users(self, username):
        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD
        lookup = {f"{username_field}__iexact": username}

        for user in user_model._default_manager.filter(**lookup):
            if user.is_active and user.has_usable_password():
                yield user

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        path = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": context["uid"], "token": context["token"]},
        )
        reset_link = f"{context['protocol']}://{context['domain']}{path}"
        message = (
            "### Fediverse Anime Awards  \n"
            "You have submitted a password change request!  \n"
            "If it was you, confirm the password change.  \n"
            f"URL: [**CONFIRM**]({reset_link})  \n  \n"
            "If you didn't request password change on "
            f"{settings.FEDI_ANIME_AWARDS_URL}, ignore this message."
        )

        username = context["user"].get_username()
        try:
            reset_password(username, message)
        except LemmyError as e:
            logger.error("Username password reset failed: %s", e)
