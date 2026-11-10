from datetime import date

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseNotAllowed, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import ImportState
from .admin_tasks import (
    select_finalists,
    get_results,
    import_single_show,
    import_year,
    get_admin_results_md
)


@staff_member_required
def download_data(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        year = int(request.POST.get("year", ""))
    except ValueError:
        return HttpResponseBadRequest("Choose a valid year.")

    if year < 2024 or year > date.today().year:
        return HttpResponseBadRequest("Year is out of range.")

    label = f"Year {year}"
    ImportState.objects.update_or_create(
        pk=1,
        defaults={
            "status": ImportState.Status.READY,
            "label": label,
            "error_type": "",
        },
    )

    import_year.enqueue(year=year)
    messages.success(request, "Data import started. It will take approximately 5-10 minutes.")

    return redirect(reverse("admin:app_list", kwargs={"app_label": "polls"}))


@staff_member_required
def download_single_data(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        anilist_id = int(request.POST.get("anilist_id", ""))
    except ValueError:
        return HttpResponseBadRequest("Choose a valid AniList ID.")

    label = f"AniList ID {anilist_id}"
    ImportState.objects.update_or_create(
        pk=1,
        defaults={
            "status": ImportState.Status.READY,
            "label": label,
            "error_type": "",
        },
    )

    import_single_show.enqueue(anilist_id=anilist_id)
    messages.success(request, "Data import started.")

    return redirect(reverse("admin:app_list", kwargs={"app_label": "polls"}))


@staff_member_required
def enable_finals(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        select_finalists()
    except RuntimeError:
        messages.error(request, "Failed to select finalists.")
    else:
        messages.success(request, "Finalists selected. View the poll as an admin to see them.")

    return redirect(reverse("admin:app_list", kwargs={"app_label": "polls"}))


@staff_member_required
def show_results(request):
    year, nominations, finals, final_enabled = get_results()

    return render(request, "polls/results.html", {
        "year": year,
        "nominations": nominations,
        "finals": finals,
        "final_enabled": final_enabled,
        "full": True
    })


@staff_member_required
def get_results_md(request):
    is_final = request.GET.get("final", "").lower() == "true"
    markdown = get_admin_results_md(is_final)
    return JsonResponse({"text": markdown})
