from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View
from django.views.generic.edit import FormView

from ai_agent.domain.repository.conversation import ConversationRepository
from ai_agent.domain.service.conversation import ConversationService
from ai_agent.forms import SendMessageForm
from ai_agent.models import Message, Entity, ActionHistory


class IndexView(FormView):
    template_name = "ai_agent/index.html"
    form_class = SendMessageForm
    success_url = reverse_lazy("agt:index")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # メッセージ履歴
        context["messages"] = Message.objects.select_related("entity").order_by(
            "created_at"
        )

        # タイムラインデータ
        context["completed_actions"] = ActionHistory.objects.filter(done=True).order_by(
            "acted_at_turn"
        )
        context["future_actions"] = ActionHistory.objects.filter(done=False).order_by(
            "acted_at_turn"
        )
        context["latest_completed_turn"] = (
            context["completed_actions"].last().acted_at_turn
            if context["completed_actions"].exists()
            else 0
        )
        return context

    def form_valid(self, form):
        entity = Entity.objects.get(name="User")
        Message.objects.create(
            entity=entity,
            message_content=form.cleaned_data["user_input"],
        )

        return super().form_valid(form)


class ResetTimelineView(View):
    """
    Resets the timeline and initializes future actions.
    """

    @staticmethod
    def post(request, *args, **kwargs):
        # リセット処理を呼び出し
        ResetTimelineView.reset_timeline()
        return redirect("agt:index")

    @staticmethod
    def reset_timeline():
        """タイムラインをリセット"""
        # メッセージ履歴をクリア
        Message.objects.all().delete()
        print("All messages have been cleared.")  # デバッグログ

        # ActionHistoryをクリア
        ActionHistory.objects.all().delete()
        print("All ActionHistory records have been cleared.")  # デバッグログ

        # タイムラインを初期化
        ConversationService.initialize_timeline()

        # 未来の10ターン分をActionHistoryに登録
        ConversationService.simulate_next_actions(max_steps=10)

        # ActionHistoryのすべての行動を未完了（done=False）にする
        ActionHistory.objects.all().update(done=False)


class NextTurnView(View):
    """
    Handles advancing to the next turn in the conversation.
    """

    @staticmethod
    def post(request, *args, **kwargs):
        # 未完了の最初のアクションを取得。
        next_action = (
            ActionHistory.objects.filter(done=False).order_by("acted_at_turn").first()
        )

        if not next_action:
            # 未完了のアクションがない場合フラッシュメッセージ設定
            messages.info(
                request, "No more actions left to process. Timeline has been reset."
            )

            # リセット処理を直接呼び出し
            ResetTimelineView.reset_timeline()

            return redirect("agt:index")

        # 選択されたアクションを完了済みにする
        next_action.done = True
        next_action.save()

        # `next_action` のエンティティに基づいて次の動作を処理
        # input_text = request.POST.get("input_text", "")  # TODO: ユーザー入力を処理する場合のメモ
        try:
            # 次のエンティティとその処理を取得
            next_entity = next_action.entity

            # 仮の応答を生成
            response = f"{next_entity.name} が行動しました: 仮の応答テキスト"

            # メッセージを作成
            ConversationRepository.create_message(next_entity, response)
        except ValueError as e:
            print(f"Error: {e}")

        return redirect("agt:index")
