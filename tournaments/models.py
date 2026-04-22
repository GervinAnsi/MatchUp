from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password


class Tournament(models.Model):
    class SportType(models.TextChoices):
        FOOTBALL = "football", "Jalgpall"
        BASKETBALL = "basketball", "Korvpall"
        VOLLEYBALL = "volleyball", "Võrkpall"
        TENNIS = "tennis", "Tennis"
        PADEL = "padel", "Padel"
        MMA = "mma", "MMA"
        ESPORT = "esport", "E-sport"
        OTHER = "other", "Muu"

    class TournamentFormat(models.TextChoices):
        SINGLE_ELIMINATION = "single_elimination", "Single Elimination"
        ROUND_ROBIN = "round_robin", "Round Robin"
        GROUP_STAGE = "group_stage", "Alagrupid"
        OTHER = "other", "Muu"

    class TournamentStatus(models.TextChoices):
        DRAFT = "draft", "Mustand"
        REGISTRATION_OPEN = "registration_open", "Registreerimine avatud"
        READY = "ready", "Valmis alustamiseks"
        ACTIVE = "active", "Käimas"
        FINISHED = "finished", "Lõpetatud"
        CANCELLED = "cancelled", "Tühistatud"

    name = models.CharField(max_length=150)
    sport_type = models.CharField(
        max_length=30,
        choices=SportType.choices,
        default=SportType.OTHER,
    )
    format = models.CharField(
        max_length=30,
        choices=TournamentFormat.choices,
        default=TournamentFormat.SINGLE_ELIMINATION,
    )
    date = models.DateField()
    time = models.TimeField()
    location = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=30,
        choices=TournamentStatus.choices,
        default=TournamentStatus.DRAFT,
    )

    max_participants = models.PositiveIntegerField(default=2)
    admin_password_hash = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "time", "name"]

    def __str__(self):
        return f"{self.name} ({self.date})"

    def clean(self):
        if self.max_participants < 2:
            raise ValidationError("Turniiril peab olema vähemalt 2 osalejat.")

    def set_admin_password(self, raw_password: str) -> None:
        """
        Hashib ja salvestab turniiri admin-parooli.
        """
        if not raw_password or len(raw_password.strip()) < 4:
            raise ValidationError("Admin-parool peab olema vähemalt 4 tähemärki pikk.")
        self.admin_password_hash = make_password(raw_password.strip())

    def check_admin_password(self, raw_password: str) -> bool:
        """
        Kontrollib, kas sisestatud parool vastab turniiri admin-paroolile.
        """
        if not raw_password:
            return False
        return check_password(raw_password, self.admin_password_hash)

    @property
    def participant_count(self) -> int:
        return self.participants.count()

    @property
    def is_full(self) -> bool:
        return self.participant_count >= self.max_participants


class Participant(models.Model):
    class ParticipantType(models.TextChoices):
        PLAYER = "player", "Mängija"
        TEAM = "team", "Meeskond"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    name = models.CharField(max_length=120)
    type = models.CharField(
        max_length=20,
        choices=ParticipantType.choices,
        default=ParticipantType.PLAYER,
    )
    contact_info = models.CharField(max_length=150, blank=True)
    seed = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tournament", "name")

    def __str__(self):
        return self.name

    def clean(self):
        if self.seed is not None and self.seed < 1:
            raise ValidationError("Paigutusnumber peab olema vähemalt 1.")


class Match(models.Model):
    class MatchStatus(models.TextChoices):
        PLANNED = "planned", "Planeeritud"
        ONGOING = "ongoing", "Käimas"
        FINISHED = "finished", "Lõpetatud"
        CANCELLED = "cancelled", "Tühistatud"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="matches",
    )
    participant1 = models.ForeignKey(
        Participant,
        on_delete=models.PROTECT,
        related_name="matches_as_participant1",
    )
    participant2 = models.ForeignKey(
        Participant,
        on_delete=models.PROTECT,
        related_name="matches_as_participant2",
    )
    round = models.PositiveIntegerField(default=1)
    bracket_position = models.PositiveIntegerField(blank=True, null=True)
    scheduled_time = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=MatchStatus.choices,
        default=MatchStatus.PLANNED,
    )
    winner = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="won_matches",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["round", "scheduled_time", "id"]

    def __str__(self):
        return f"{self.tournament.name}: {self.participant1} vs {self.participant2}"

    def clean(self):
        if self.participant1_id == self.participant2_id:
            raise ValidationError("Üks osaleja ei saa mängida iseenda vastu.")

        if self.participant1.tournament_id != self.tournament_id:
            raise ValidationError("Esimene osaleja ei kuulu sellesse turniiri.")

        if self.participant2.tournament_id != self.tournament_id:
            raise ValidationError("Teine osaleja ei kuulu sellesse turniiri.")

        if self.winner and self.winner not in [self.participant1, self.participant2]:
            raise ValidationError("Võitja peab olema üks mängu osalejatest.")

    @property
    def has_result(self) -> bool:
        return hasattr(self, "result")

    def set_winner_from_result(self):
        """
        Määrab võitja seotud tulemuse põhjal.
        Viigi korral jätab winner välja NULL.
        """
        if not self.has_result:
            self.winner = None
            return

        if self.result.participant1_score > self.result.participant2_score:
            self.winner = self.participant1
        elif self.result.participant2_score > self.result.participant1_score:
            self.winner = self.participant2
        else:
            self.winner = None


class Result(models.Model):
    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        related_name="result",
    )
    participant1_score = models.PositiveIntegerField(default=0)
    participant2_score = models.PositiveIntegerField(default=0)
    result_confirmed = models.BooleanField(default=False)
    entered_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-entered_at"]

    def __str__(self):
        return (
            f"Tulemus: {self.match.participant1} {self.participant1_score} - "
            f"{self.participant2_score} {self.match.participant2}"
        )

    def clean(self):
        if self.participant1_score < 0 or self.participant2_score < 0:
            raise ValidationError("Tulemus ei saa olla negatiivne.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.match.set_winner_from_result()

        if self.result_confirmed:
            self.match.status = Match.MatchStatus.FINISHED
        elif self.match.status == Match.MatchStatus.PLANNED:
            self.match.status = Match.MatchStatus.ONGOING

        self.match.save(update_fields=["winner", "status"])


class ErrorReport(models.Model):
    class ReportStatus(models.TextChoices):
        NEW = "new", "Uus"
        REVIEWED = "reviewed", "Üle vaadatud"
        RESOLVED = "resolved", "Lahendatud"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="error_reports",
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.SET_NULL,
        related_name="error_reports",
        null=True,
        blank=True,
    )
    message = models.TextField()
    reported_by_name = models.CharField(max_length=120, blank=True)
    reported_by_email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.NEW,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Veateavitus #{self.pk} - {self.tournament.name}"

    def clean(self):
        if self.match and self.match.tournament_id != self.tournament_id:
            raise ValidationError("Valitud mäng ei kuulu samasse turniiri.")