from django.db import migrations


def create_initial_categories(apps, schema_editor):
    Category = apps.get_model("polls", "Category")

    Category.objects.get_or_create(name="Action")
    Category.objects.get_or_create(name="Fantasy/Adventure")
    Category.objects.get_or_create(name="Comedy")
    Category.objects.get_or_create(name="Drama")
    Category.objects.get_or_create(name="Romance")
    Category.objects.get_or_create(name="Slice of Life")
    Category.objects.get_or_create(name="Animation")
    Category.objects.get_or_create(name="Soundtrack")
    Category.objects.get_or_create(name="Movie of the Year")
    Category.objects.get_or_create(name="Anime of the Year")
    Category.objects.get_or_create(name="Character")
    Category.objects.get_or_create(name="Voice Performance")
    Category.objects.get_or_create(name="Musical Sequence")

    VotingConfig = apps.get_model("polls", "VotingConfig")
    VotingConfig.objects.get_or_create(
        id=1,
        defaults={
            "current_year": 1000,
            "finals_vote": False,
            "voting_enabled": False,
        }
    )


def remove_initial_categories(apps, schema_editor):
    Category = apps.get_model("polls", "Category")

    Category.objects.filter(
        name__in=[
            "Action",
            "Fantasy/Adventure",
            "Comedy",
            "Drama",
            "Romance",
            "Slice of Life",
            "Animation",
            "Soundtrack",
            "Movie of the Year",
            "Anime of the Year",
            "Character",
            "Voice Performance",
            "Musical Sequence",
        ]
    ).delete()

    VotingConfig = apps.get_model("polls", "VotingConfig")
    VotingConfig.objects.filter(id=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("polls", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_categories,
            remove_initial_categories,
        ),
    ]
