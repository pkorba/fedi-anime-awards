"""
URL configuration for fedi_anime_awards project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from polls.admin_views import (
    download_data,
    enable_finals,
    show_results,
    download_single_data,
    get_results_md
)
from polls.views import HomeLoginView

urlpatterns = [
    path("", HomeLoginView.as_view(template_name="polls/index.html"), name="home_login"),
    path("", include("polls.urls")),
    path(
        "admin/polls/download-data/",
        admin.site.admin_view(download_data),
        name="polls_download_data",
    ),
    path(
        "admin/polls/download-single-data/",
        admin.site.admin_view(download_single_data),
        name="polls_download_single_data",
    ),
    path(
        "admin/polls/select-finalists-data/",
        admin.site.admin_view(enable_finals),
        name="polls_select_finalists",
    ),
    path(
        "admin/polls/results/",
        admin.site.admin_view(show_results),
        name="polls_results",
    ),
    path(
        "admin/polls/results_admin_md/",
        admin.site.admin_view(get_results_md),
        name="results_admin_md",
    ),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
