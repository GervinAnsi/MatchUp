from django.urls import path

from . import views


urlpatterns = [
    path("", views.tournament_list_create, name="tournament_list_create"),
    path("<int:tournament_id>/", views.tournament_detail, name="tournament_detail"),
    path("<int:tournament_id>/update/", views.tournament_update, name="tournament_update"),
    path("<int:tournament_id>/delete/", views.tournament_delete, name="tournament_delete"),
    path(
        "<int:tournament_id>/admin/login/",
        views.tournament_admin_login,
        name="tournament_admin_login",
    ),
    path(
        "<int:tournament_id>/admin/logout/",
        views.tournament_admin_logout,
        name="tournament_admin_logout",
    ),
    path(
        "<int:tournament_id>/participants/",
        views.participant_list_create,
        name="participant_list_create",
    ),
    path(
        "<int:tournament_id>/participants/<int:participant_id>/update/",
        views.participant_update,
        name="participant_update",
    ),
    path(
        "<int:tournament_id>/participants/<int:participant_id>/delete/",
        views.participant_delete,
        name="participant_delete",
    ),
    path(
        "<int:tournament_id>/matches/generate/",
        views.generate_matches,
        name="generate_matches",
    ),
    path(
        "<int:tournament_id>/rounds/generate-next/",
        views.generate_next_round,
        name="generate_next_round",
    ),
    path(
        "<int:tournament_id>/matches/<int:match_id>/result/",
        views.result_update,
        name="result_update",
    ),
    path(
        "<int:tournament_id>/error-reports/create/",
        views.error_report_create,
        name="error_report_create",
    ),
]
