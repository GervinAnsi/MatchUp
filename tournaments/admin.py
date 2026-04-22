from django.contrib import admin
from .models import Tournament, Participant, Match, Result, ErrorReport


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0


class MatchInline(admin.TabularInline):
    model = Match
    extra = 0
    fk_name = "tournament"


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sport_type",
        "format",
        "date",
        "time",
        "status",
        "max_participants",
        "participant_count",
    )
    list_filter = ("sport_type", "format", "status", "date")
    search_fields = ("name", "location", "description")
    readonly_fields = ("created_at", "updated_at", "participant_count")
    inlines = [ParticipantInline, MatchInline]

    fieldsets = (
        ("Põhiandmed", {
            "fields": (
                "name",
                "sport_type",
                "format",
                "date",
                "time",
                "location",
                "description",
            )
        }),
        ("Seaded", {
            "fields": (
                "status",
                "max_participants",
                "admin_password_hash",
            )
        }),
        ("Süsteemi väljad", {
            "fields": (
                "created_at",
                "updated_at",
                "participant_count",
            )
        }),
    )


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "tournament", "seed", "created_at")
    list_filter = ("type", "tournament")
    search_fields = ("name", "contact_info", "tournament__name")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tournament",
        "participant1",
        "participant2",
        "round",
        "status",
        "winner",
        "scheduled_time",
    )
    list_filter = ("status", "round", "tournament")
    search_fields = (
        "tournament__name",
        "participant1__name",
        "participant2__name",
    )


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        "match",
        "participant1_score",
        "participant2_score",
        "result_confirmed",
        "entered_at",
    )
    list_filter = ("result_confirmed", "entered_at")
    search_fields = (
        "match__tournament__name",
        "match__participant1__name",
        "match__participant2__name",
    )


@admin.register(ErrorReport)
class ErrorReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tournament",
        "match",
        "reported_by_name",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at", "tournament")
    search_fields = (
        "tournament__name",
        "reported_by_name",
        "reported_by_email",
        "message",
    )