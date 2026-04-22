from collections import defaultdict
from typing import List

from django.core.exceptions import ValidationError

from .models import Tournament, Participant, Match, Result


def generate_single_elimination_first_round(tournament: Tournament) -> int:
    """
    Loob single elimination turniiri esimese vooru mängud.
    Tagastab loodud mängude arvu.
    """
    if tournament.format != Tournament.TournamentFormat.SINGLE_ELIMINATION:
        raise ValidationError("See funktsioon toetab ainult single elimination formaati.")

    if tournament.matches.exists():
        raise ValidationError("Selle turniiri mängud on juba loodud.")

    participants = list(tournament.participants.order_by("seed", "id"))

    if len(participants) < 2:
        raise ValidationError("Mängude genereerimiseks peab olema vähemalt 2 osalejat.")

    if len(participants) % 2 != 0:
        raise ValidationError("Single elimination esimese vooru loomiseks peab osalejate arv olema paaris.")

    created_count = 0
    for index in range(0, len(participants), 2):
        p1 = participants[index]
        p2 = participants[index + 1]

        Match.objects.create(
            tournament=tournament,
            participant1=p1,
            participant2=p2,
            round=1,
            bracket_position=(index // 2) + 1,
            status=Match.MatchStatus.PLANNED,
        )
        created_count += 1

    tournament.status = Tournament.TournamentStatus.READY
    tournament.save(update_fields=["status"])

    return created_count


def get_round_matches(tournament: Tournament, round_number: int) -> List[Match]:
    """
    Tagastab kõik konkreetse vooru mängud.
    """
    return list(
        tournament.matches.filter(round=round_number).select_related(
            "participant1",
            "participant2",
            "winner",
        )
    )


def can_generate_next_round(tournament: Tournament, current_round: int) -> bool:
    """
    Kontrollib, kas järgmise vooru saab luua:
    - kõik current_round mängud peavad olema lõpetatud
    - igal mängul peab olema võitja
    """
    round_matches = tournament.matches.filter(round=current_round)

    if not round_matches.exists():
        return False

    for match in round_matches:
        if match.status != Match.MatchStatus.FINISHED or not match.winner:
            return False

    return True


def generate_next_single_elimination_round(tournament: Tournament, current_round: int) -> int:
    """
    Loob järgmise single elimination vooru eelmise vooru võitjate põhjal.
    Tagastab loodud mängude arvu.
    """
    if tournament.format != Tournament.TournamentFormat.SINGLE_ELIMINATION:
        raise ValidationError("See funktsioon toetab ainult single elimination formaati.")

    if not can_generate_next_round(tournament, current_round):
        raise ValidationError("Järgmist vooru ei saa veel luua, sest eelmise vooru tulemused ei ole valmis.")

    next_round = current_round + 1

    if tournament.matches.filter(round=next_round).exists():
        raise ValidationError("Järgmine voor on juba loodud.")

    winners = [
        match.winner
        for match in tournament.matches.filter(round=current_round).order_by("bracket_position", "id")
        if match.winner
    ]

    if len(winners) < 2:
        raise ValidationError("Järgmise vooru loomiseks ei ole piisavalt võitjaid.")

    if len(winners) == 1:
        tournament.status = Tournament.TournamentStatus.FINISHED
        tournament.save(update_fields=["status"])
        return 0

    if len(winners) % 2 != 0:
        raise ValidationError("Võitjate arv peab olema paaris, et järgmine voor genereerida.")

    created_count = 0
    for index in range(0, len(winners), 2):
        Match.objects.create(
            tournament=tournament,
            participant1=winners[index],
            participant2=winners[index + 1],
            round=next_round,
            bracket_position=(index // 2) + 1,
            status=Match.MatchStatus.PLANNED,
        )
        created_count += 1

    tournament.status = Tournament.TournamentStatus.ACTIVE
    tournament.save(update_fields=["status"])

    return created_count


def finalize_tournament_if_possible(tournament: Tournament) -> bool:
    """
    Märgib turniiri lõpetatuks, kui viimane lõpetatud mäng andis ühe üldvõitja.
    """
    matches = tournament.matches.order_by("-round", "-id")

    if not matches.exists():
        return False

    final_match = matches.first()

    if final_match.status == Match.MatchStatus.FINISHED and final_match.winner:
        # Kui kõige viimases voorus on ainult 1 mäng, võib lugeda turniiri lõppenuks
        same_round_count = tournament.matches.filter(round=final_match.round).count()
        if same_round_count == 1:
            tournament.status = Tournament.TournamentStatus.FINISHED
            tournament.save(update_fields=["status"])
            return True

    return False


def calculate_round_robin_standings(tournament: Tournament):
    """
    Arvutab lihtsa tabeliseisu round robin formaadi jaoks.
    Punktid:
    - võit = 3
    - viik = 1
    - kaotus = 0
    """
    standings = defaultdict(lambda: {
        "participant": None,
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "points_for": 0,
        "points_against": 0,
        "goal_difference": 0,
        "points": 0,
    })

    participants = tournament.participants.all()
    for participant in participants:
        standings[participant.id]["participant"] = participant

    matches = tournament.matches.select_related("participant1", "participant2").prefetch_related("result")

    for match in matches:
        if not hasattr(match, "result"):
            continue

        result = match.result
        p1 = match.participant1
        p2 = match.participant2

        standings[p1.id]["played"] += 1
        standings[p2.id]["played"] += 1

        standings[p1.id]["points_for"] += result.participant1_score
        standings[p1.id]["points_against"] += result.participant2_score

        standings[p2.id]["points_for"] += result.participant2_score
        standings[p2.id]["points_against"] += result.participant1_score

        if result.participant1_score > result.participant2_score:
            standings[p1.id]["wins"] += 1
            standings[p1.id]["points"] += 3
            standings[p2.id]["losses"] += 1
        elif result.participant2_score > result.participant1_score:
            standings[p2.id]["wins"] += 1
            standings[p2.id]["points"] += 3
            standings[p1.id]["losses"] += 1
        else:
            standings[p1.id]["draws"] += 1
            standings[p2.id]["draws"] += 1
            standings[p1.id]["points"] += 1
            standings[p2.id]["points"] += 1

    result_list = []
    for row in standings.values():
        row["goal_difference"] = row["points_for"] - row["points_against"]
        result_list.append(row)

    result_list.sort(
        key=lambda x: (
            -x["points"],
            -x["goal_difference"],
            -x["points_for"],
            x["participant"].name.lower(),
        )
    )

    return result_list