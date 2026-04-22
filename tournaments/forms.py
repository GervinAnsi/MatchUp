from django import forms

from .models import ErrorReport, Participant, Result, Tournament


class TournamentCreateForm(forms.ModelForm):
    admin_password = forms.CharField(
        label="Admin parool",
        min_length=4,
        max_length=128,
        widget=forms.PasswordInput,
    )
    admin_password_confirm = forms.CharField(
        label="Korda admin parooli",
        min_length=4,
        max_length=128,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = Tournament
        fields = [
            "name",
            "sport_type",
            "format",
            "date",
            "time",
            "location",
            "description",
            "max_participants",
        ]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("admin_password")
        password_confirm = cleaned_data.get("admin_password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error("admin_password_confirm", "Paroolid ei kattu.")
        return cleaned_data

    def save(self, commit=True):
        tournament = super().save(commit=False)
        tournament.set_admin_password(self.cleaned_data["admin_password"])
        if commit:
            tournament.save()
        return tournament


class TournamentUpdateForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = [
            "name",
            "sport_type",
            "format",
            "date",
            "time",
            "location",
            "description",
            "status",
            "max_participants",
        ]


class TournamentAdminLoginForm(forms.Form):
    password = forms.CharField(
        label="Admin parool",
        max_length=128,
        widget=forms.PasswordInput,
    )


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["name", "type", "contact_info", "seed"]


class MatchResultForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ["participant1_score", "participant2_score", "result_confirmed"]


class ErrorReportForm(forms.ModelForm):
    class Meta:
        model = ErrorReport
        fields = ["match", "message", "reported_by_name", "reported_by_email"]
