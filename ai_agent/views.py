from django.urls import reverse
from django.views.generic import TemplateView, RedirectView, DetailView, FormView

from ai_agent.forms import SendMessageForm
from ai_agent.models import ConversationHistory, Entity, Message


class IndexView(TemplateView):
    template_name = "ai_agent/index.html"


class StartConversationView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        # 新しい会話を作成
        conversation = ConversationHistory.objects.create(content="")
        # 作成した会話の詳細ページにリダイレクト
        return conversation.get_absolute_url()


class ConversationDetailView(DetailView):
    model = ConversationHistory
    template_name = "ai_agent/conversation/detail.html"
    context_object_name = "conversation"


class SendMessageView(FormView):
    template_name = "ai_agent/conversation/detail.html"
    form_class = SendMessageForm

    def form_valid(self, form):
        user_input = form.cleaned_data["user_input"]
        conversation = ConversationHistory.objects.get(pk=self.kwargs["pk"])

        # ユーザーのメッセージを保存
        user_entity, _ = Entity.objects.get_or_create(name="User")
        Message.objects.create(
            entity=user_entity,
            conversation=conversation,
            message_content=user_input,
        )

        # ConversationHistory の content を更新
        if conversation.content:
            conversation.content += f"\nUser: {user_input}"
        else:
            conversation.content = f"User: {user_input}"

        # シンプルなAI応答
        agent_response = f"Echo: {user_input}"
        agent_entity, _ = Entity.objects.get_or_create(name="Agent")
        Message.objects.create(
            entity=agent_entity,
            conversation=conversation,
            message_content=agent_response,
        )

        # ConversationHistory の content に AI 応答を追加
        conversation.content += f"\nAgent: {agent_response}"
        conversation.save()

        return super().form_valid(form)

    def get_success_url(self):
        return reverse("agt:conversation_detail", kwargs={"pk": self.kwargs["pk"]})
