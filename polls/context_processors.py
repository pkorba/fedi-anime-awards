from .models import Show, NominationChoice


def show_table_status(request):
    return {"has_shows": Show.objects.exists()}


def nomination_choice_table_status(request):
    return {"has_nominations": NominationChoice.objects.exists()}
