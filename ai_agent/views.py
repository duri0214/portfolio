from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View
from django.views.generic.edit import FormView

from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.service.input_processor import InputProcessor
from ai_agent.domain.service.response_generator import ResponseGenerator
from ai_agent.domain.service.thinking_engine_processor import ThinkingEngineProcessor
from ai_agent.domain.service.turn_management import TurnManagementService
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

        処理の流れ：
        1. ユーザーエンティティを取得
        2. 現在の未完了アクションを取得（ユーザーターンとして処理）
        3. メッセージを処理して保存し、同時にアクションを完了状態に更新
        4. 次のエンティティの情報を含むメッセージを表示

        Args:
            form (SendMessageForm): 検証済みのフォームインスタンス

        Returns:
            HttpResponse: 処理後のリダイレクトレスポンス
        """
        try:
            # 1. ユーザーエンティティを取得
            user_entity = Entity.objects.get(name="User")
            user_input = form.cleaned_data["user_input"]

            if not user_input:
                messages.error(self.request, "メッセージが入力されていません")
                return super().form_invalid(form)

            # 2. 現在の未完了アクションを取得（ユーザーターンとして処理）
            current_action_history = (
                ActionHistory.objects.filter(done=False, entity=user_entity)
                .order_by("acted_at_turn")
                .first()
            )
            if not current_action_history:
                messages.error(self.request, "現在はユーザーのターンではありません")
                return super().form_invalid(form)

            # 3. メッセージを処理して保存し、同時にアクションを完了状態に更新
            processor = InputProcessor(user_entity)
            TurnManagementRepository.create_message(
                content=processor.process_input(user_input),
                action_history=current_action_history,
            )

            # 4. 次のエンティティの情報を含むメッセージを表示
            upcoming_action_history = (
                ActionHistory.objects.filter(done=False)
                .order_by("acted_at_turn")
                .first()
            )
            success_msg = f"{user_entity.name} のターンが完了しました。"

            if upcoming_action_history:
                success_msg += f"\n次は {upcoming_action_history.entity.name} のターンです。「1単位時間進める」ボタンをクリックしてください。"
            else:
                success_msg += "\n処理すべきアクションはもうありません。"

            messages.success(self.request, success_msg)

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
        TODO: ai_agent/domain/service/thinking_engine_processor.py に移す issue 322
        """
        # メッセージ履歴をクリア
        Message.objects.all().delete()
        log_service.write("All messages have been cleared.")

        # ActionHistoryをクリア
        ActionHistory.objects.all().delete()
        log_service.write("All ActionHistory records have been cleared.")

        # タイムラインを初期化
        TurnManagementService.initialize_timeline()

        # 未来の10ターン分をActionHistoryに登録
        TurnManagementService.simulate_next_actions(max_steps=10)

        # ActionHistoryのすべての行動を未完了（done=False）にする
        ActionHistory.objects.all().update(done=False)


class NextTurnView(View):
    @staticmethod
    def post(request, *args, **kwargs):
        """
        次のターンに進むPOSTリクエストを処理します。

        処理の流れ：
        1. 現在のターンのアクションを取得
        2. アクションが存在しない場合はタイムラインをリセット
        3. エンティティの基本情報を取得
        4. エンティティに紐づくタイムラインが存在しない場合はシステムエラー（データ不整合）
        5. Userエンティティの場合は操作を拒否（ボタンではなくチャットフォームからの入力が必要なため）
        6. ResponseGeneratorを使用してガードレールを適用し応答を生成
        7. エラーが発生した場合は処理を中断
        8. 次のターンのアクションを確認して、ユーザーに通知

        Returns:
            HttpResponseRedirect: インデックスページへのリダイレクト
        """
        try:
            # 1. 現在のターンのアクションを取得
            current_action_history = (
                ActionHistory.objects.filter(done=False)
                .order_by("acted_at_turn")
                .first()
            )
            if not current_action_history:
                # 2. アクションが存在しない場合はタイムラインをリセット
                reset_message = "処理すべきアクションはもうありません。タイムラインがリセットされました。"
                messages.info(request, reset_message)
                ResetTimelineView.reset_timeline()
                return redirect("agt:index")

            # 3. エンティティの基本情報を取得
            active_entity = current_action_history.entity
            active_entity_timeline = TurnManagementRepository.get_action_timeline(
                active_entity
            )

            # 4. エンティティに紐づくタイムラインが存在しない場合はシステムエラー（データ不整合）
            if not active_entity_timeline:
                error_message = f"重大なエラー: {active_entity.name}のアクションタイムラインが見つかりません。システム管理者に連絡してください。"
                messages.error(request, error_message)
                log_service.write(
                    f"DATA INCONSISTENCY ERROR: Entity {active_entity.id}:{active_entity.name} has ActionHistory but no ActionTimeline"
                )
                # このような状態はシステムの整合性エラーなので、管理者が修正するまでリセットしない
                return redirect("agt:index")

            # 5. Userエンティティの場合は操作を拒否（ボタンではなくチャットフォームからの入力が必要なため）
            if active_entity.name == "User":
                error_message = "Userエンティティのターンは「1単位時間進める」ボタンでは進められません。チャットフォームからメッセージを送信してください。"
                messages.error(request, error_message)
                return redirect("agt:index")

            # 6. ResponseGeneratorを使用してガードレールを適用し応答を生成
            response_text = ResponseGenerator.generate_response(
                action_history=current_action_history,
                context=ThinkingEngineProcessor.get_recent_context(),
            )

            # 7. エラーが発生した場合は処理を中断
            if response_text.startswith("[ERROR]"):
                messages.warning(
                    request,
                    "エンティティがチャットに参加できない状態です。次のターンに進んでください。",
                )
                return redirect("agt:index")

            # 8. 次のターンのアクションを確認して、ユーザーに通知
            upcoming_action_history = (
                ActionHistory.objects.filter(done=False)
                .order_by("acted_at_turn")
                .first()
            )
            success_msg = f"{active_entity.name} のターンが完了しました。"

            if upcoming_action_history:
                success_msg += f"\n次は {upcoming_action_history.entity.name} のターンです。「1単位時間進める」ボタンをクリックしてください。"
                messages.success(request, success_msg)
            else:
                success_msg += "\n処理すべきアクションはもうありません。"
                messages.success(request, success_msg)

        except ValueError:
            # エラー処理: 行動可能なエンティティがない場合はタイムラインをリセット
            reset_message = "処理すべきアクションはもうありません。タイムラインがリセットされました。"
            messages.info(request, reset_message)
            ResetTimelineView.reset_timeline()
        except Exception as e:
            log_service.write(f"次のターン処理中にエラーが発生しました: {e}")
            messages.error(
                request, "処理中にエラーが発生しました。管理者に連絡してください。"
            )

        return redirect("agt:index")
