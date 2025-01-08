from django import forms


class SendMessageForm(forms.Form):
    user_input = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={"placeholder": "Type your message", "class": "form-control"}
        ),
        error_messages={"required": "Please enter a message."},
    )
