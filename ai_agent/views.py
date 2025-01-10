from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View
from django.views.generic.edit import FormView

from ai_agent.domain.service.conversation import ConversationService
from ai_agent.forms import SendMessageForm
from ai_agent.models import Message, Entity


class IndexView(FormView):
    template_name = "ai_agent/index.html"
    form_class = SendMessageForm
    success_url = reverse_lazy("agt:index")

    def get_context_data(self, **kwargs):
        messages = Message.objects.select_related("entity").order_by("created_at")
        context = super().get_context_data(**kwargs)
        context["messages"] = messages
        return context

    def form_valid(self, form):
        entity = Entity.objects.get(name="User")
        Message.objects.create(
            entity=entity,
            message_content=form.cleaned_data["user_input"],
        )

        return super().form_valid(form)


class NextTurnView(View):
    """
    Handles advancing to the next turn in the conversation.
    """

    @staticmethod
    def post(request, *args, **kwargs):
        input_text = request.POST.get("input_text", "")
        try:
            # 次のエンティティを取得
            next_entity = ConversationService.get_next_entity(input_text)

            # 仮の応答を生成（ここをAI応答に変更可能）
            response = f"{next_entity.name} が回答します: 仮の応答テキスト"

            # メッセージを作成
            ConversationService.create_message(next_entity, response)
        except ValueError as e:
            # エンティティが存在しない場合や応答できるエンティティがない場合
            print(f"Error: {e}")

        return redirect("agt:index")
