from django.conf import settings
from django.db import models
from django.db.models import Q


class Show(models.Model):
    class Format(models.TextChoices):
        TV = "TV", "TV"
        MOVIE = "MOVIE", "Movie"
        OVA = "OVA", "OVA"
        ONA = "ONA", "ONA"
        SPECIAL = "SPECIAL", "Special"

    al_id = models.PositiveIntegerField(unique=True, primary_key=True)
    mal_id = models.PositiveIntegerField(
        unique=False,
        blank=True,
        null=True,
    )

    title_romaji = models.CharField(max_length=300)
    title_english = models.CharField(
        max_length=300,
        blank=True,
        null=True,
    )

    poster = models.ImageField(
        upload_to="posters/",
        blank=True,
        null=True,
    )

    format = models.CharField(
        max_length=10,
        choices=Format.choices,
    )

    categories = models.ManyToManyField(
        "Category",
        related_name="shows",
        through="CategoryShow",
        blank=True,
    )

    def __str__(self):
        title = self.title_english or self.title_romaji
        return title


class Category(models.Model):
    name = models.CharField(
        max_length=200,
        unique=True,
    )

    class Meta:
        verbose_name = "category"
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class CategoryShow(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    finalist = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["category", "show"],
                name="unique_category_show",
            )
        ]

class Character(models.Model):
    al_id = models.PositiveIntegerField(unique=False)
    show = models.ForeignKey(
        Show,
        on_delete=models.CASCADE,
        related_name="characters",
    )
    name = models.CharField(max_length=200)
    picture = models.ImageField(
        upload_to="characters/",
        blank=True,
        null=True,
    )
    finalist = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["al_id", "show"],
                name="unique_id_per_show",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.show})"


class Person(models.Model):
    al_id = models.PositiveIntegerField(unique=False)
    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="people",
    )
    name = models.CharField(max_length=200)
    finalist = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["al_id", "character"],
                name="unique_id_per_character",
            )
        ]

        verbose_name = "person"
        verbose_name_plural = "people"

    def __str__(self):
        return f"{self.name} as {self.character}"


class Music(models.Model):
    class MusicType(models.TextChoices):
        OPENING = "OP", "OP"
        ENDING = "ED", "ED"
        INSERT = "IN", "IN"

    show = models.ForeignKey(
        Show,
        on_delete=models.CASCADE,
        related_name="musics",
    )
    url = models.URLField(blank=True, null=True)
    title = models.CharField(max_length=300)
    type = models.CharField(
        max_length=2,
        choices=MusicType.choices,
    )
    thumb = models.ImageField(
        upload_to="music/",
        blank=True,
        null=True,
    )
    finalist = models.BooleanField(default=False)

    class Meta:
        verbose_name = "music"
        verbose_name_plural = "music"

    def __str__(self):
        return self.title


class NominationSet(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nomination_sets",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="nomination_sets",
    )
    year = models.PositiveSmallIntegerField()

    # One final vote for this user, category, and year.
    final_vote = models.PositiveBigIntegerField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "year"],
                name="one_set_per_user_category_year",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.category} ({self.year})"


class NominationChoice(models.Model):
    nomination_set = models.ForeignKey(
        NominationSet,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    position = models.PositiveSmallIntegerField()
    value = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(position__gte=1, position__lte=5),
                name="nomination_position_1_to_5",
            ),
            models.UniqueConstraint(
                fields=["nomination_set", "position"],
                name="unique_position_per_nomination_set",
            ),
            models.UniqueConstraint(
                fields=["nomination_set", "value"],
                name="unique_value_per_nomination_set",
            ),
        ]


class VotingConfig(models.Model):
    # Fixed primary key - allow only one configuration row
    id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )
    current_year = models.PositiveSmallIntegerField()
    finals_vote = models.BooleanField(default=False)
    voting_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.current_year} voting configuration"


class ImportState(models.Model):
    class Status(models.TextChoices):
        READY = "READY", "Queued"
        RUNNING = "RUNNING", "Running"
        SUCCESSFUL = "SUCCESSFUL", "Succeeded"
        FAILED = "FAILED", "Failed"

    # Use this model as a singleton row with pk=1.
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.READY,
    )
    label = models.CharField(max_length=100, blank=True)
    error_type = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)