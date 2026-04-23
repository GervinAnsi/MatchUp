from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
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
        return JsonResponse(
            {"ok": True, "tournaments": [_serialize_tournament(t) for t in tournaments]}
        )

    form = TournamentCreateForm(request.POST)
    if not form.is_valid():
        return _form_error_response(form)

    tournament = form.save()
    return JsonResponse({"ok": True, "tournament": _serialize_tournament(tournament)}, status=201)


@require_http_methods(["GET"])
def tournament_detail(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    participants = tournament.participants.all()
    matches = tournament.matches.select_related("participant1", "participant2", "winner")
    return JsonResponse(
        {
            "ok": True,
            "tournament": _serialize_tournament(tournament),
            "participants": [_serialize_participant(p) for p in participants],
            "matches": [_serialize_match(m) for m in matches],
        }
    )


@require_http_methods(["POST"])
def tournament_update(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        return admin_error

    form = TournamentUpdateForm(request.POST, instance=tournament)
    if not form.is_valid():
        return _form_error_response(form)

    updated = form.save()
    return JsonResponse({"ok": True, "tournament": _serialize_tournament(updated)})


@require_http_methods(["POST"])
def tournament_delete(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        return admin_error

    tournament.delete()
    request.session.pop(_tournament_admin_session_key(tournament_id), None)
    return JsonResponse({"ok": True, "deleted_tournament_id": tournament_id})


@require_http_methods(["POST"])
def tournament_admin_login(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    form = TournamentAdminLoginForm(request.POST)
    if not form.is_valid():
        return _form_error_response(form)

    if not tournament.check_admin_password(form.cleaned_data["password"]):
        return _error_response("Vale admin parool.", status=403)

    request.session[_tournament_admin_session_key(tournament.id)] = True
    return JsonResponse({"ok": True, "logged_in": True, "tournament_id": tournament.id})


@require_http_methods(["POST"])
def tournament_admin_logout(request, tournament_id):
    get_object_or_404(Tournament, id=tournament_id)
    request.session.pop(_tournament_admin_session_key(tournament_id), None)
    return JsonResponse({"ok": True, "logged_in": False, "tournament_id": tournament_id})


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


@require_http_methods(["POST"])
def participant_update(request, tournament_id, participant_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        return admin_error

    participant = get_object_or_404(Participant, id=participant_id, tournament=tournament)
    form = ParticipantForm(request.POST, instance=participant)
    if not form.is_valid():
        return _form_error_response(form)

    updated = form.save()
    return JsonResponse({"ok": True, "participant": _serialize_participant(updated)})


@require_http_methods(["POST"])
def participant_delete(request, tournament_id, participant_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        return admin_error

    participant = get_object_or_404(Participant, id=participant_id, tournament=tournament)
    participant.delete()
    return JsonResponse({"ok": True, "deleted_participant_id": participant_id})


@require_http_methods(["POST"])
def generate_matches(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        return admin_error

    try:
        created = generate_single_elimination_first_round(tournament)
    except ValidationError as error:
        return _error_response(error.message)

    return JsonResponse({"ok": True, "created_matches": created, "tournament_id": tournament.id})


@require_http_methods(["POST"])
def generate_next_round(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        return admin_error

    try:
        current_round = int(request.POST.get("current_round", "0"))
    except ValueError:
        return _error_response("current_round peab olema täisarv.")

    if current_round < 1:
        return _error_response("current_round peab olema >= 1.")

    try:
        created = generate_next_single_elimination_round(tournament, current_round)
    except ValidationError as error:
        return _error_response(error.message)

    return JsonResponse(
        {
            "ok": True,
            "created_matches": created,
            "next_round": current_round + 1,
            "tournament_id": tournament.id,
        }
    )


@require_http_methods(["POST"])
def result_update(request, tournament_id, match_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    admin_error = _require_tournament_admin(request, tournament)
    if admin_error:
        return admin_error

    match = get_object_or_404(Match, id=match_id, tournament=tournament)

    instance = getattr(match, "result", None)
    form = MatchResultForm(request.POST, instance=instance)
    if not form.is_valid():
        return _form_error_response(form)

    result = form.save(commit=False)
    result.match = match
    result.save()

    match.refresh_from_db()
    return JsonResponse(
        {
            "ok": True,
            "match_id": match.id,
            "winner_id": match.winner_id,
            "status": match.status,
        }
    )


@require_http_methods(["POST"])
def error_report_create(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)

    form = ErrorReportForm(request.POST)
    if not form.is_valid():
        return _form_error_response(form)

    report = form.save(commit=False)
    report.tournament = tournament

    if report.match and report.match.tournament_id != tournament.id:
        return _error_response("Valitud mäng ei kuulu sellesse turniiri.")

    report.save()
    return JsonResponse({"ok": True, "error_report_id": report.id}, status=201)
