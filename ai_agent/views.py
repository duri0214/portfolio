import asyncio
from hashlib import sha256
import json
from uuid import uuid4

from django.contrib import messages
from django.core import signing
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

from ai_agent.domain.service.game import GameService
from ai_agent.domain.service.game_agent import GameAgentService
from ai_agent.domain.service.skill_tools import GameToolSet
from ai_agent.domain.valueobject.agent_execution import AgentRunStatus
from ai_agent.domain.valueobject.game import (
    GameState,
    Position,
)


class IndexView(TemplateView):
    """問題選択、セリフ決定、Agent実行を扱うゲーム画面アダプター。"""

    template_name = "ai_agent/index.html"
    game_state_session_key = "ai_agent_game_state"
    legacy_state_cookie_name = "ai_agent_game_state"
    legacy_session_keys = (
        "ai_agent_execution_history",
        "ai_agent_board_event_history",
    )
    stream_pending_session_key = "ai_agent_pending_stream_state"
    stream_state_salt = "ai_agent.stream_state"

    def get(self, request, *args, **kwargs):
        """ゲーム画面を表示し、旧ゲーム状態Cookieを破棄する。"""
        response = super().get(request, *args, **kwargs)
        self._delete_legacy_state_cookie(response)
        return response

    def get_context_data(self, **kwargs):
        """現在のゲーム状態と画面操作に必要なSkill定義を渡す。"""
        context = super().get_context_data(**kwargs)
        game = self._load_state()
        context["game"] = game
        context["selected_mondai"] = (
            game.mondai(game.selected_mondai_id) if game.selected_mondai_id else None
        )
        context["board_cells"] = self._board_cells(game)
        return context

    def post(self, request, *args, **kwargs):
        """画面操作をドメインサービスへ渡し、状態を保存する。"""
        game = self._load_state()
        action = request.POST.get("action")
        try:
            if action == "select_mondai":
                game = GameService.select_mondai(game, request.POST["mondai_id"])
                messages.success(
                    request, "対象の問題を選択しました。次にセリフを選んでください。"
                )
            elif action == "select_board_space":
                game = GameService.select_board_space(game, request.POST["space_id"])
                event = game.board_event_history[0]
                messages.success(
                    request,
                    f"{event.space_name}へ移動しました。{event.summary}",
                )
            elif action == "stream_agent":
                if not game.selected_mondai_id:
                    raise ValueError("先に対象の問題を選択してください")
                base_state = game
                game = GameService.select_line(game, request.POST["line_id"])
                return self._stream_agent_response(game, base_state)
            elif action == "save_stream_state":
                payload = self._unsign_stream_state(request.POST["state_token"])
                self._consume_stream_state(payload)
                game = GameState.from_dict(payload["state"])
                self._add_saved_agent_message(request, game)
                response = redirect("agt:index")
                self._save_state(response, game)
                return response
            elif action == "select_line":
                if not game.selected_mondai_id:
                    raise ValueError("先に対象の問題を選択してください")
                game = GameService.select_line(game, request.POST["line_id"])
                game, run = self._run_agent(game)
                game = game.with_execution_record(
                    GameAgentService.create_execution_record(game, run)
                )
                self._add_agent_message(request, game, run)
            elif action == "reset":
                game = GameService.create_game()
                messages.success(request, "ゲームを初期状態へ戻しました。")
            else:
                raise ValueError("unknown game action")
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            signing.BadSignature,
        ) as error:
            if (
                action == "save_stream_state"
                and request.headers.get("Accept") == "application/json"
            ):
                response = JsonResponse({"error": str(error)}, status=409)
                self._delete_legacy_state_cookie(response)
                return response
            messages.error(request, f"操作できません: {error}")

        response = redirect("agt:index")
        self._save_state(response, game)
        return response

    def _stream_agent_response(self, game, base_state):
        """AgentのToolイベントをSSEで逐次配信する。"""
        tools = GameToolSet(game)
        agent = GameAgentService(tools=tools)
        token_id = uuid4().hex
        base_state_digest = self._state_fingerprint(base_state)
        self.request.session[self.stream_pending_session_key] = {
            "token_id": token_id,
            "base_state": base_state_digest,
        }

        def event_stream():
            loop = asyncio.new_event_loop()
            iterator = agent.stream_selected()
            try:
                while True:
                    try:
                        event = loop.run_until_complete(anext(iterator))
                    except StopAsyncIteration:
                        break
                    payload = {
                        key: value for key, value in event.items() if key != "run"
                    }
                    if event["type"] == "report.completed":
                        final_state = tools.state.with_execution_record(
                            GameAgentService.create_execution_record(
                                tools.state, event["run"]
                            )
                        )
                        payload["state_token"] = self._sign_stream_state(
                            final_state, token_id, base_state_digest
                        )
                    yield self._sse(payload)
            finally:
                try:
                    loop.run_until_complete(iterator.aclose())
                finally:
                    loop.close()

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream; charset=utf-8"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        self._delete_legacy_state_cookie(response)
        return response

    @staticmethod
    def _sse(payload):
        return f"event: {payload['type']}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

    def _sign_stream_state(self, game, token_id, base_state_digest):
        return signing.dumps(
            {
                "state": game.to_dict(),
                "token_id": token_id,
                "base_state": base_state_digest,
            },
            salt=self.stream_state_salt,
        )

    def _unsign_stream_state(self, value):
        payload = signing.loads(value, salt=self.stream_state_salt)
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("state"), dict)
            or not all(
                isinstance(payload.get(key), str) for key in ("token_id", "base_state")
            )
        ):
            raise ValueError("ストリーム状態Tokenの形式が不正です")
        return payload

    @staticmethod
    def _state_fingerprint(game):
        serialized = json.dumps(
            game.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return sha256(serialized.encode("utf-8")).hexdigest()

    def _consume_stream_state(self, payload):
        pending = self.request.session.get(self.stream_pending_session_key)
        if not isinstance(pending, dict) or any(
            pending.get(key) != payload[key] for key in ("token_id", "base_state")
        ):
            raise ValueError("ストリーム状態Tokenは期限切れか、すでに使用されています")

        self.request.session.pop(self.stream_pending_session_key, None)
        current_state = self._load_state()
        if self._state_fingerprint(current_state) != payload["base_state"]:
            raise ValueError(
                "ゲーム状態が更新されています。画面を再読み込みしてください"
            )

    def _save_state(self, response, game):
        """ゲーム状態全体をDjangoセッションへ保存する。"""
        self.request.session[self.game_state_session_key] = game.to_dict()
        self._delete_legacy_state_cookie(response)

    def _load_state(self):
        """セッションから状態全体を読み、壊れていれば初期状態へ戻す。"""
        for key in self.legacy_session_keys:
            self.request.session.pop(key, None)
        payload = self.request.session.get(self.game_state_session_key)
        if payload is None:
            return GameService.create_game()
        try:
            return GameState.from_dict(payload)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.request.session.pop(self.game_state_session_key, None)
            return GameService.create_game()

    def _delete_legacy_state_cookie(self, response):
        """旧ゲーム状態Cookieを読み込まず、レスポンスで破棄する。"""
        if self.legacy_state_cookie_name in self.request.COOKIES:
            response.delete_cookie(self.legacy_state_cookie_name)

    @staticmethod
    def _board_cells(game):
        """CSS Gridへ渡す盤面の各マスと駒の情報を作る。"""
        problems_by_position = {
            (problem.position.row, problem.position.column): problem
            for problem in game.mondais
        }
        spaces_by_position = {
            (space.position.row, space.position.column): space
            for space in game.board_spaces
        }
        return [
            {
                "row": row,
                "column": column,
                "is_player": game.player_position == Position(row, column),
                "problem": problems_by_position.get((row, column)),
                "special_space": spaces_by_position.get((row, column)),
                "special_space_used": (
                    spaces_by_position.get((row, column)) is not None
                    and spaces_by_position[(row, column)].space_id
                    in game.used_board_space_ids
                ),
            }
            for row in range(game.board_size)
            for column in range(game.board_size)
        ]

    @staticmethod
    def _run_agent(game):
        """選択状態をAgentへ渡し、Agent実行後のTool状態を返す。"""
        tools = GameToolSet(game)
        agent = GameAgentService(tools=tools)
        run = agent.run_selected()
        return tools.state, run

    @staticmethod
    def _add_agent_message(request, game, run):
        """AgentのTool選択結果または実行失敗を画面通知へ変換する。"""
        if run.status is AgentRunStatus.COMPLETED:
            messages.success(
                request,
                f"Agentが処理を完了しました。経験値は {game.experience} です。"
                "下の実行履歴で判断と結果を確認できます。",
            )
        else:
            messages.error(request, f"Agent実行に失敗しました: {run.report.error}")

    @staticmethod
    def _add_saved_agent_message(request, game):
        """保存済みのストリーミング実行結果を画面通知へ変換する。"""
        if not game.execution_history:
            return
        record = game.execution_history[0]
        if record.status == AgentRunStatus.COMPLETED.value:
            messages.success(
                request,
                f"Agentが{len(record.steps)}つのSkillをチェーンしました。結果を反映しました。",
            )
        else:
            messages.error(
                request,
                f"Agent実行に失敗しました: {record.error or '実行結果を確認できませんでした。'}",
            )
