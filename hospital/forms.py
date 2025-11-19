from django import forms

from hospital.models import (
    ElectionLedger,
    Election,
    Ward,
    CitySector,
    BILLING_METHOD_CHOICES,
    VotePlace,
    Member,
)


class ElectionLedgerCreateForm(forms.ModelForm):
    election = forms.ModelChoiceField(
        queryset=Election.objects.all(),
        label="選挙名*",
        widget=forms.Select(attrs={"class": "form-control", "tabindex": "1"}),
    )

    voter = forms.ModelChoiceField(
        queryset=Member.objects.filter(role=Member.Role.PATIENT),
        label="選挙人氏名*",
        widget=forms.Select(attrs={"class": "form-control", "tabindex": "2"}),
    )

    vote_ward = forms.ModelChoiceField(
        queryset=Ward.objects.all(),
        label="病棟*",
        widget=forms.Select(attrs={"class": "form-control", "tabindex": "3"}),
    )

    vote_city_sector = forms.ModelChoiceField(
        queryset=CitySector.objects.all(),
        label="投票区*",
        widget=forms.Select(attrs={"class": "form-control", "tabindex": "4"}),
    )

    remark = forms.CharField(
        label="備考",
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": "3", "tabindex": "5"}
        ),
    )

    billing_method = forms.ChoiceField(
        choices=BILLING_METHOD_CHOICES,
        label="投票用紙請求の方法*",
        initial=2,
        widget=forms.Select(attrs={"class": "form-control", "tabindex": "6"}),
    )

    proxy_billing_request_date = forms.DateField(
        label="代理請求の依頼を受けた日",
        error_messages={
            "invalid": "代理請求の依頼を受けた日を正しく入力してください。"
        },
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "tabindex": "7"}),
    )

    proxy_billing_date = forms.DateField(
        label="代理請求日",
        error_messages={"invalid": "代理請求日を正しく入力してください。"},
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "tabindex": "8"}),
    )

    ballot_received_date = forms.DateField(
        label="投票用紙受領日",
        error_messages={"invalid": "投票用紙受領日を正しく入力してください。"},
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "tabindex": "9"}),
    )

    vote_date = forms.DateField(
        label="投票日",
        error_messages={"invalid": "投票日を正しく入力してください。"},
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "tabindex": "10"}),
    )

    vote_place = forms.ModelChoiceField(
        queryset=VotePlace.objects.all(),
        label="投票場所",
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "tabindex": "11"}),
    )

    vote_observer = forms.ModelChoiceField(
        queryset=Member.objects.filter(role=Member.Role.STAFF),
        label="投票立会人",
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "tabindex": "12"}),
    )

    applied_for_proxy_voting = forms.BooleanField(
        label="代理投票申請の有無",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
                "style": "margin-left: 20px;",
                "tabindex": "13",
            }
        ),
    )

    delivery_date = forms.DateField(
        label="投票用紙送付日",
        error_messages={"invalid": "投票用紙送付日を正しく入力してください。"},
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "tabindex": "14"}),
    )

    class Meta:
        model = ElectionLedger
        fields = "__all__"


class ElectionLedgerUpdateForm(ElectionLedgerCreateForm):
    pass
