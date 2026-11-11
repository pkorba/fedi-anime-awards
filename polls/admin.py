from django.contrib import admin

from .models import (
    Category,
    CategoryShow,
    Show,
    Person,
    Music,
    Character,
    VotingConfig,
    NominationChoice,
    NominationSet,
    ImportState,
)

admin.site.register(Category)


@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
    list_display = ["al_id", "title_english", "title_romaji", "format"]
    search_fields = ["title_english", "title_romaji"]


@admin.register(CategoryShow)
class CategoryShowAdmin(admin.ModelAdmin):
    list_display = ["show", "category", "finalist"]
    search_fields = ["show__title_english", "show__title_romaji"]
    list_editable = ["finalist"]


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ["al_id", "name", "show", "finalist"]
    search_fields = ["name"]
    list_editable = ["finalist"]


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["al_id", "name", "character", "finalist"]
    search_fields = ["name", "character__name"]
    list_editable = ["finalist"]


@admin.register(Music)
class MusicAdmin(admin.ModelAdmin):
    list_display = ["title", "type", "url", "finalist"]
    search_fields = ["title"]
    list_editable = ["finalist"]


@admin.register(VotingConfig)
class VotingConfigAdmin(admin.ModelAdmin):
    list_display = ["current_year", "voting_enabled", "finals_vote"]

    def has_add_permission(self, request):
        return not VotingConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NominationSet)
class NominationSetAdmin(admin.ModelAdmin):
    list_display = ["year", "user", "category", "final_vote"]
    search_fields = ["user__username", "category__name"]


@admin.register(NominationChoice)
class NominationChoiceAdmin(admin.ModelAdmin):
    list_display = ["nomination_set", "position", "value"]
    search_fields = ["nomination_set__user__username"]


@admin.register(ImportState)
class ImportStateAdmin(admin.ModelAdmin):
    list_display = ["label", "error_type", "updated_at"]
