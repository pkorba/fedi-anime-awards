from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()

        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None

        lookup = {f"{User.USERNAME_FIELD}__iexact": username}

        try:
            user = User._default_manager.get(**lookup)
        except User.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # Fail if existing accounts collide by case.
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None