from django.shortcuts import redirect
from django.views.generic import TemplateView, FormView

from ai_agent.forms import SendMessageForm
from .models import Message, Entity


class IndexView(TemplateView):
    template_name = "ai_agent/index.html"

    def get_context_data(self, **kwargs):
        messages = Message.objects.select_related("entity").order_by("created_at")
        return {"messages": messages}


class SendMessageView(FormView):
    template_name = "ai_agent/index.html"
    form_class = SendMessageForm

    def form_valid(self, form):
        entity = Entity.objects.get(name="User")
        Message.objects.create(
            entity=entity,
            message_content=form.cleaned_data["user_input"],
        )

        return redirect("agt:index")
