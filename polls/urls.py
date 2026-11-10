from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LemmyPasswordResetForm

urlpatterns = [
    path("signup", views.signup, name="signup"),

    path("signup/done", views.signup_done, name="signup_done"),

    path("policies/", views.policies, name="policies"),

    path("polls/<int:category_id>/", views.category_poll, name="category_poll"),

    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="home_login"),
        name="logout",
    ),

    # Password reset
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(
            form_class=LemmyPasswordResetForm,
            template_name="registration/password_reset_form.html",
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    # Password change
    path(
        "password_change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
        ),
        name="password_change",
    ),
    path(
        "password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html",
        ),
        name="password_change_done",
    ),

    # Results
    path("results/", views.results, name="user_polls_results"),

    path("results_md/", views.results_md, name="results_md"),
]
