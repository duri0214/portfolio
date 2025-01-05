from django import forms


class SendMessageForm(forms.Form):
    user_input = forms.CharField(label="Your Message", max_length=500)
