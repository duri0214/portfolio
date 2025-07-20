from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View
from django.views.generic.edit import FormView

from ai_agent.domain.repository.conversation import ConversationRepository
from ai_agent.domain.service.conversation import ConversationService
from ai_agent.domain.service.input_processor import InputProcessor
from ai_agent.forms import SendMessageForm
from ai_agent.models import Message, Entity, ActionHistory
from lib.log_service import LogService

log_service = LogService("ai_agent_views.log")


class IndexView(FormView):
    """
    メインチャットインターフェースを表示するビュー。

    チャット履歴、エンティティのアクションタイムライン、およびユーザー入力フォームを提供します。
    フォーム送信時にはユーザーメッセージを処理し、データベースに保存します。

    Attributes:
        template_name (str): 使用するテンプレートファイルのパス
        form_class (class): ユーザー入力を処理するフォームクラス
        success_url (str): フォーム送信成功後のリダイレクト先URL
    """

    template_name = "ai_agent/index.html"
    form_class = SendMessageForm
    success_url = reverse_lazy("agt:index")

    def get_context_data(self, **kwargs):
        """
        テンプレートに渡すコンテキストデータを拡張します。

        チャットメッセージ履歴、完了済みアクション、未来のアクション、および
        最新の完了済みターン番号をコンテキストに追加します。

        Args:
            **kwargs: 継承元のget_context_dataから渡される追加のキーワード引数

        Returns:
            dict: 拡張されたコンテキストデータ
        """
        context = super().get_context_data(**kwargs)

        # メッセージ履歴
        context["chat_messages"] = Message.objects.select_related("entity").order_by(
            "created_at"
        )

        # タイムラインデータ
        context["completed_actions"] = ActionHistory.objects.filter(done=True).order_by(
            "acted_at_turn"
        )
        context["future_actions"] = (
            ActionHistory.objects.filter(done=False)
            .order_by("acted_at_turn")
            .select_related("entity")
        )
        context["latest_completed_turn"] = (
            context["completed_actions"].last().acted_at_turn
            if context["completed_actions"].exists()
            else 0
        )
        # ユーザーエンティティの情報を追加
        context["user_entity"] = Entity.objects.filter(name="User").first()
        return context

    def form_valid(self, form):
        """
        ユーザーからの入力フォームが有効な場合の処理を行います。

        ユーザーエンティティを取得し、入力メッセージを処理してデータベースに保存します。
        メッセージが空の場合やエンティティが見つからない場合はエラーメッセージを表示します。

        Args:
            form (SendMessageForm): 検証済みのフォームインスタンス

        Returns:
            HttpResponse: 処理後のリダイレクトレスポンス
        """
        try:
            entity = Entity.objects.get(name="User")
            user_input = form.cleaned_data["user_input"]

            if not user_input:
                messages.error(self.request, "メッセージが入力されていません")
                return super().form_invalid(form)

            processor = InputProcessor(entity)
            processed_message = processor.process_input(user_input)

            Message.objects.create(
                entity=entity,
                message_content=processed_message,
            )

            messages.success(self.request, "メッセージが送信されました")

        except Entity.DoesNotExist:
            log_service.write("User entity not found")
            messages.error(self.request, "ユーザーエンティティが見つかりません")
            return super().form_invalid(form)
        except Exception as e:
            log_service.write(f"Message processing error: {e}")
            messages.error(self.request, "処理中にエラーが発生しました")
            return super().form_invalid(form)

        return super().form_valid(form)


class ResetTimelineView(View):
    """
    会話タイムラインをリセットし、将来のアクションを初期化するビュー。

    すべてのメッセージ履歴とアクション履歴を削除し、エンティティの行動タイムラインを
    初期化します。その後、次の10ターン分のアクションをシミュレーションして
    ActionHistoryに登録します。

    このビューは、会話が行き詰まった場合や新しい会話を開始したい場合に使用されます。
    """

    @staticmethod
    def post(request, *args, **kwargs):
        """
        POSTリクエストを処理し、タイムラインのリセットを実行します。

        リセット処理を実行した後、インデックスページにリダイレクトします。

        Args:
            request (HttpRequest): リクエストオブジェクト
            *args: 可変位置引数
            **kwargs: 可変キーワード引数

        Returns:
            HttpResponseRedirect: インデックスページへのリダイレクト
        """
        # リセット処理を呼び出し
        ResetTimelineView.reset_timeline()
        return redirect("agt:index")

    @staticmethod
    def reset_timeline():
        """
        タイムラインをリセットし、新しい会話の準備をします。

        以下の処理を実行します：
        1. すべてのメッセージ履歴を削除
        2. すべてのActionHistory（行動履歴）レコードを削除
        3. 各エンティティのActionTimelineを初期化（speed属性に基づいて）
        4. 次の10ターン分のアクションをシミュレーションしてActionHistoryに登録
        5. すべてのActionHistoryレコードを未完了状態（done=False）に設定

        この処理により、エンティティのスピード属性に基づいた新しい行動順序が決定されます。
        """
        # メッセージ履歴をクリア
        Message.objects.all().delete()
        log_service.write("All messages have been cleared.")

        # ActionHistoryをクリア
        ActionHistory.objects.all().delete()
        log_service.write("All ActionHistory records have been cleared.")

        # タイムラインを初期化
        ConversationService.initialize_timeline()

        # 未来の10ターン分をActionHistoryに登録
        ConversationService.simulate_next_actions(max_steps=10)

        # ActionHistoryのすべての行動を未完了（done=False）にする
        ActionHistory.objects.all().update(done=False)


class NextTurnView(View):
    """
    会話の次のターンに進むための処理を行うビュー。

    このビューは、タイムライン上の次のアクション（未完了の最初のActionHistory）を
    取得し、そのアクションを完了状態に更新します。次に、対応するエンティティが
    行動可能かどうかを確認し、行動可能な場合は次のエンティティを取得して
    メッセージを生成します。

    エンティティが行動できない場合やこれ以上のアクションがない場合は、
    適切なメッセージを表示し、必要に応じてタイムラインをリセットします。

    このビューはチャットシステムのターン制進行を制御する中心的な役割を担っています。
    """

    @staticmethod
    def post(request, *args, **kwargs):
        """
        次のターンに進むPOSTリクエストを処理します。

        処理の流れ：
        1. 未完了の最初のアクションを取得
        2. アクションが存在しない場合はタイムラインをリセット
        3. アクションを完了状態に更新
        4. エンティティが行動可能か確認し、不可能な場合はその旨を通知
        5. 行動可能な場合は次のエンティティを取得してメッセージを生成
        6. 行動可能なエンティティがない場合はタイムラインをリセット

        Args:
            request (HttpRequest): リクエストオブジェクト
            *args: 可変位置引数
            **kwargs: 可変キーワード引数

        Returns:
            HttpResponseRedirect: インデックスページへのリダイレクト
        """
        # 未完了の最初のアクションを取得。
        next_action = (
            ActionHistory.objects.filter(done=False).order_by("acted_at_turn").first()
        )

        if not next_action:
            # 未完了のアクションがない場合フラッシュメッセージ設定
            messages.info(
                request,
                "処理すべきアクションはもうありません。タイムラインがリセットされました。",
            )

            # リセット処理を直接呼び出し
            ResetTimelineView.reset_timeline()

            return redirect("agt:index")

        # 選択されたアクションを完了済みにする
        next_action.done = True
        next_action.save()

        # ActionTimelineのエンティティを取得し、can_actの状態を確認
        timeline = ConversationRepository.get_action_timeline(next_action.entity)
        if timeline and not timeline.can_act:
            # エンティティの種類に基づいて理由を追加
            thinking_type_display = next_action.entity.get_thinking_type_display()

            # エンティティが会話不能状態の場合は、その旨のメッセージを表示
            response = f"（{next_action.entity.name}（{thinking_type_display}）はチャットに参加できませんでした）"
            # 特別なメッセージとしてマークする（テンプレートで赤背景表示用）
            message = ConversationRepository.create_message(
                next_action.entity, response
            )
            message.message_content = f"[ERROR]{message.message_content}"
            message.save()
            messages.warning(
                request,
                f"{next_action.entity.name}（{thinking_type_display}）はチャットに参加できない状態です。",
            )
            return redirect("agt:index")

        try:
            # 次のエンティティとその処理を取得
            # input_text = request.POST.get("input_text")  # TODO: ユーザー入力を処理する場合のメモ
            next_entity = ConversationService.get_next_entity(input_text="")

            # 仮の応答を生成
            response = f"{next_entity.name} が行動しました: 仮の応答テキスト"

            # メッセージを作成
            ConversationRepository.create_message(next_entity, response)

            # フラッシュメッセージを設定
            messages.success(request, f"{next_entity.name} のターンが完了しました。")
        except ValueError:
            # 行動可能なエンティティがない場合、一旦リセット
            messages.info(
                request, "No more actions left to process. Timeline has been reset."
            )
            ResetTimelineView.reset_timeline()

        return redirect("agt:index")
