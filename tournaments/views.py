from django.core.exceptions import ValidationError
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import (
    ErrorReportForm,
    MatchResultForm,
    ParticipantForm,
    TournamentAdminLoginForm,
    TournamentCreateForm,
    TournamentUpdateForm,
)
from .models import Match, Participant, Tournament
from .services import (
    can_generate_next_round,
    generate_next_single_elimination_round,
    generate_single_elimination_first_round,
)


def _error_response(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def _form_error_response(form, status=400):
    return JsonResponse({"ok": False, "errors": form.errors}, status=status)


def _tournament_admin_session_key(tournament_id):
    return f"tournament_admin_{tournament_id}"


def _require_tournament_admin(request, tournament):
    is_admin = request.session.get(_tournament_admin_session_key(tournament.id), False)
    if not is_admin:
        return _error_response("Turniiri admin login on vajalik.", status=403)
    return None


def _serialize_tournament(tournament):
    return {
        "id": tournament.id,
        "name": tournament.name,
        "sport_type": tournament.sport_type,
        "format": tournament.format,
        "date": tournament.date.isoformat(),
        "time": tournament.time.isoformat(),
        "location": tournament.location,
        "description": tournament.description,
        "status": tournament.status,
        "max_participants": tournament.max_participants,
        "participant_count": tournament.participant_count,
    }


def _serialize_participant(participant):
    return {
        "id": participant.id,
        "tournament_id": participant.tournament_id,
        "name": participant.name,
        "type": participant.type,
        "contact_info": participant.contact_info,
        "seed": participant.seed,
    }


def _serialize_match(match):
    return {
        "id": match.id,
        "tournament_id": match.tournament_id,
        "participant1_id": match.participant1_id,
        "participant2_id": match.participant2_id,
        "round": match.round,
        "status": match.status,
        "winner_id": match.winner_id,
        "scheduled_time": match.scheduled_time.isoformat() if match.scheduled_time else None,
    }


@require_http_methods(["GET", "POST"])
def tournament_list_create(request):
    if request.method == "GET":
        tournaments = Tournament.objects.all()
        sport_types_count = Tournament.objects.values("sport_type").distinct().count()
        total_players = Participant.objects.count()
        completed_tournaments = Tournament.objects.filter(
            status=Tournament.TournamentStatus.FINISHED
        ).count()
        return render(
            request,
            "tournament_list.html",
            {
                "tournaments": tournaments,
                "sport_types_count": sport_types_count,
                "total_players": total_players,
                "completed_tournaments": completed_tournaments,
            },
        )

    form = TournamentCreateForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "tournament_form.html",
            {"form": form, "page_title": "Loo uus turniir"},
            status=400,
        )

    tournament = form.save()
    messages.success(request, "Turniir loodud.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)


@require_http_methods(["GET"])
def tournament_list_api(request):
    tournaments = Tournament.objects.all()
    return JsonResponse(
        {"ok": True, "tournaments": [_serialize_tournament(t) for t in tournaments]}
    )


@require_http_methods(["GET", "POST"])
def tournament_create(request):
    if request.method == "GET":
        return render(
            request,
            "tournament_form.html",
            {"form": TournamentCreateForm(), "page_title": "Loo uus turniir"},
        )

    form = TournamentCreateForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "tournament_form.html",
            {"form": form, "page_title": "Loo uus turniir"},
            status=400,
        )

    tournament = form.save()
    messages.success(request, "Turniir loodud.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)


@require_http_methods(["GET"])
def tournament_detail(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    participants = tournament.participants.all()
    matches = tournament.matches.select_related("participant1", "participant2", "winner")
    current_round = 0
    can_generate_next_round_flag = False

    if tournament.format == Tournament.TournamentFormat.SINGLE_ELIMINATION and matches.exists():
        last_match = matches.order_by("-round", "-id").first()
        current_round = last_match.round if last_match else 0
        if current_round:
            can_generate_next_round_flag = can_generate_next_round(tournament, current_round)

    is_admin = request.session.get(_tournament_admin_session_key(tournament.id), False)
    return render(
        request,
        "tournament_detail.html",
        {
            "tournament": tournament,
            "participants": participants,
            "matches": matches,
            "is_admin": is_admin,
            "standings": [],
            "current_round": current_round,
            "can_generate_next_round": can_generate_next_round_flag,
        },
    )


@require_http_methods(["GET", "POST"])
def tournament_update(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        messages.error(request, "Turniiri admin login on vajalik.")
        return redirect("tournaments:tournament_admin_login", tournament_id=tournament.id)

    if request.method == "GET":
        form = TournamentUpdateForm(instance=tournament)
        return render(
            request,
            "tournament_form.html",
            {"form": form, "page_title": "Muuda turniiri"},
        )

    form = TournamentUpdateForm(request.POST, instance=tournament)
    if not form.is_valid():
        return render(
            request,
            "tournament_form.html",
            {"form": form, "page_title": "Muuda turniiri"},
            status=400,
        )

    updated = form.save()
    messages.success(request, "Turniir uuendatud.")
    return redirect("tournaments:tournament_detail", tournament_id=updated.id)


@require_http_methods(["GET", "POST"])
def tournament_delete(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        messages.error(request, "Turniiri admin login on vajalik.")
        return redirect("tournaments:tournament_admin_login", tournament_id=tournament.id)

    if request.method == "GET":
        return render(request, "tournament_confirm_delete.html", {"tournament": tournament})

    tournament.delete()
    request.session.pop(_tournament_admin_session_key(tournament_id), None)
    messages.success(request, "Turniir kustutatud.")
    return redirect("tournaments:tournament_list")


@require_http_methods(["GET", "POST"])
def tournament_admin_login(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if request.method == "GET":
        return render(
            request,
            "admin_login.html",
            {"form": TournamentAdminLoginForm(), "tournament": tournament},
        )

    form = TournamentAdminLoginForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "admin_login.html",
            {"form": form, "tournament": tournament},
            status=400,
        )

    if not tournament.check_admin_password(form.cleaned_data["password"]):
        form.add_error("password", "Vale admin parool.")
        return render(
            request,
            "admin_login.html",
            {"form": form, "tournament": tournament},
            status=403,
        )

    request.session[_tournament_admin_session_key(tournament.id)] = True
    messages.success(request, "Admin login õnnestus.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)


@require_http_methods(["GET", "POST"])
def tournament_admin_logout(request, tournament_id):
    get_object_or_404(Tournament, id=tournament_id)
    request.session.pop(_tournament_admin_session_key(tournament_id), None)
    messages.success(request, "Logisid admin-kontolt välja.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament_id)


@require_http_methods(["GET", "POST"])
def participant_list_create(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)

    if request.method == "GET":
        participants = tournament.participants.all()
        return JsonResponse(
            {"ok": True, "participants": [_serialize_participant(p) for p in participants]}
        )

    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        return admin_error

    form = ParticipantForm(request.POST)
    if not form.is_valid():
        return _form_error_response(form)

    participant = form.save(commit=False)
    participant.tournament = tournament
    participant.save()
    return JsonResponse({"ok": True, "participant": _serialize_participant(participant)}, status=201)


@require_http_methods(["GET", "POST"])
def participant_create(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        messages.error(request, "Turniiri admin login on vajalik.")
        return redirect("tournaments:tournament_admin_login", tournament_id=tournament.id)

    if request.method == "GET":
        return render(
            request,
            "participant_form.html",
            {
                "form": ParticipantForm(),
                "page_title": "Lisa osaleja",
                "tournament": tournament,
            },
        )

    form = ParticipantForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "participant_form.html",
            {"form": form, "page_title": "Lisa osaleja", "tournament": tournament},
            status=400,
        )

    participant = form.save(commit=False)
    participant.tournament = tournament
    participant.save()
    messages.success(request, "Osaleja lisatud.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)


@require_http_methods(["GET", "POST"])
def participant_update(request, tournament_id, participant_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        messages.error(request, "Turniiri admin login on vajalik.")
        return redirect("tournaments:tournament_admin_login", tournament_id=tournament.id)

    participant = get_object_or_404(Participant, id=participant_id, tournament=tournament)
    if request.method == "GET":
        form = ParticipantForm(instance=participant)
        return render(
            request,
            "participant_form.html",
            {
                "form": form,
                "page_title": "Muuda osalejat",
                "tournament": tournament,
            },
        )

    form = ParticipantForm(request.POST, instance=participant)
    if not form.is_valid():
        return render(
            request,
            "participant_form.html",
            {"form": form, "page_title": "Muuda osalejat", "tournament": tournament},
            status=400,
        )

    updated = form.save()
    messages.success(request, "Osaleja uuendatud.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)


@require_http_methods(["GET", "POST"])
def participant_delete(request, tournament_id, participant_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        messages.error(request, "Turniiri admin login on vajalik.")
        return redirect("tournaments:tournament_admin_login", tournament_id=tournament.id)

    participant = get_object_or_404(Participant, id=participant_id, tournament=tournament)
    if request.method == "GET":
        return render(
            request,
            "participant_confirm_delete.html",
            {"participant": participant, "tournament": tournament},
        )

    participant.delete()
    messages.success(request, "Osaleja kustutatud.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)


@require_http_methods(["GET", "POST"])
def generate_matches(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        messages.error(request, "Turniiri admin login on vajalik.")
        return redirect("tournaments:tournament_admin_login", tournament_id=tournament.id)

    try:
        created = generate_single_elimination_first_round(tournament)
    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("tournaments:tournament_detail", tournament_id=tournament.id)

    messages.success(request, f"Loodi {created} mängu.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)


@require_http_methods(["POST"])
def generate_next_round(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        messages.error(request, "Turniiri admin login on vajalik.")
        return redirect("tournaments:tournament_admin_login", tournament_id=tournament.id)

    current_round_raw = request.POST.get("current_round")
    if current_round_raw:
        try:
            current_round = int(current_round_raw)
        except ValueError:
            messages.error(request, "Vooru number peab olema täisarv.")
            return redirect("tournaments:tournament_detail", tournament_id=tournament.id)
    else:
        last_match = tournament.matches.order_by("-round", "-id").first()
        current_round = last_match.round if last_match else 0

    if current_round < 1:
        messages.error(request, "Järgmist vooru ei saa luua, sest mänge pole veel loodud.")
        return redirect("tournaments:tournament_detail", tournament_id=tournament.id)

    try:
        created = generate_next_single_elimination_round(tournament, current_round)
    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("tournaments:tournament_detail", tournament_id=tournament.id)

    if created > 0:
        messages.success(request, f"Loodi {created} mängu vooruks {current_round + 1}.")
    else:
        messages.success(request, "Turniir on lõpetatud.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)


@require_http_methods(["GET", "POST"])
def result_update(request, tournament_id, match_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        messages.error(request, "Turniiri admin login on vajalik.")
        return redirect("tournaments:tournament_admin_login", tournament_id=tournament.id)

    match = get_object_or_404(Match, id=match_id, tournament=tournament)
    if request.method == "GET":
        instance = getattr(match, "result", None)
        form = MatchResultForm(instance=instance)
        return render(
            request,
            "match_result_form.html",
            {"form": form, "match": match, "tournament": tournament},
        )

    instance = getattr(match, "result", None)
    form = MatchResultForm(request.POST, instance=instance)
    if not form.is_valid():
        return render(
            request,
            "match_result_form.html",
            {"form": form, "match": match, "tournament": tournament},
            status=400,
        )

    result = form.save(commit=False)
    result.match = match
    result.save()

    match.refresh_from_db()
    messages.success(request, "Mängu tulemus salvestatud.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)


@require_http_methods(["GET", "POST"])
def error_report_create(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if request.method == "GET":
        form = ErrorReportForm()
        form.fields["match"].queryset = tournament.matches.all()
        return render(
            request,
            "error_report_form.html",
            {"form": form, "tournament": tournament},
        )

    form = ErrorReportForm(request.POST)
    form.fields["match"].queryset = tournament.matches.all()
    if not form.is_valid():
        return render(
            request,
            "error_report_form.html",
            {"form": form, "tournament": tournament},
            status=400,
        )

    report = form.save(commit=False)
    report.tournament = tournament

    if report.match and report.match.tournament_id != tournament.id:
        form.add_error("match", "Valitud mäng ei kuulu sellesse turniiri.")
        return render(
            request,
            "error_report_form.html",
            {"form": form, "tournament": tournament},
            status=400,
        )

    report.save()
    messages.success(request, "Veateavitus saadetud.")
    return redirect("tournaments:tournament_detail", tournament_id=tournament.id)
